from __future__ import annotations

import argparse
import asyncio
import base64
import os
import time
from pathlib import Path

import grpc
import uvicorn
import yaml
from envoy.config.core.v3.base_pb2 import HeaderValue, HeaderValueOption
from envoy.service.ext_proc.v3 import external_processor_pb2 as pb
from envoy.service.ext_proc.v3 import external_processor_pb2_grpc as rpc
from envoy.type.v3.http_status_pb2 import HttpStatus
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .audit import InspectionAudit
from .authorization import load_authorizer
from .budget import INSPECTION_DEADLINE
from .contracts import HttpMessage, InspectionConfig, InspectionError, Verdict
from .engine import InspectionEngine
from .identity import IDENTITY_FIELDS, AttestationVerifier, reserved_header
from .protocol import encode_json, strict_json, route_for


def normalized_headers(values) -> dict[str, str]:
  result = {}
  for key, value in values:
    key = key.lower()
    if key in result or any(c in key + value for c in "\r\n\x00"):
      raise InspectionError("ambiguous_headers")
    result[key] = value
  if ":authority" in result and "host" in result and result[":authority"] != result["host"]:
    raise InspectionError("authority_host_mismatch")
  if "content-length" in result and "transfer-encoding" in result:
    raise InspectionError("ambiguous_framing")
  if "connection" in result:
    # Do not let hop-by-hop nomination remove a signed application credential downstream.
    tokens = {name.strip().lower() for name in result["connection"].split(",")}
    if tokens - {"keep-alive", "close"}:
      raise InspectionError("unsupported_connection_tokens")
  return result


def proto_headers(headers):
  return normalized_headers((item.key, (item.raw_value.decode("latin-1") if item.raw_value
                                        else item.value)) for item in headers.headers)


def remove_context(headers):
  return [key for key in headers if reserved_header(key)]


def immediate(verdict: Verdict, status: int | None = None):
  malformed = verdict.reason in {"mcp_header_body_mismatch", "unsupported_mcp_version",
                                "missing_mcp_headers", "invalid_mcp_header_encoding"}
  code = status or (428 if verdict.action == "approval_required" else
                    503 if verdict.reason in {"inspection_unavailable", "inspection_deadline", "signature_timeout"}
                    else 400 if malformed else 403)
  return pb.ProcessingResponse(immediate_response=pb.ImmediateResponse(
    status=HttpStatus(code=code), details="trapdefense_policy",
    headers=pb.HeaderMutation(set_headers=[HeaderValueOption(
      header=HeaderValue(key="content-type", raw_value=b"application/json"))]),
    body=encode_json({"error": verdict.reason, "decision": verdict.action,
                      "approval_id": verdict.approval_id}),
  ))


class InspectionWorkers:
  """Timeout does not release a worker slot while its blocking scanner is still running."""
  def __init__(self, maximum: int = 4):
    self.slots = asyncio.Semaphore(maximum)

  async def run(self, callback, *args, deadline=None, on_timing=None, **kwargs):
    queued = time.perf_counter()
    await self.slots.acquire()
    acquired = time.perf_counter()
    async def invoke():
      token = INSPECTION_DEADLINE.set(deadline or time.monotonic() + 10)
      try:
        return await asyncio.to_thread(callback, *args, **kwargs)
      finally:
        INSPECTION_DEADLINE.reset(token)
        if on_timing is not None:
          on_timing((acquired-queued)*1000, (time.perf_counter()-acquired)*1000)
    task = asyncio.create_task(invoke())
    def finished(result):
      self.slots.release()
      if not result.cancelled():
        result.exception()  # Retrieve late failure after caller cancellation without logging data.
    task.add_done_callback(finished)
    return await asyncio.shield(task)


class ExternalProcessor(rpc.ExternalProcessorServicer):
  def __init__(self, engine: InspectionEngine, audit: InspectionAudit, *, stream_timeout: float = 20,
               measure=None, timeline=None):
    self.engine, self.audit, self.stream_timeout = engine, audit, stream_timeout
    self.measure = measure
    self.timeline = timeline
    self.stream_wait_ms = None
    self.slots = asyncio.Semaphore(16)
    self.workers = InspectionWorkers()

  async def _inspect(self, callback, *args, deadline, **kwargs):
    # Both shipped proxies use a two-second message timeout; leave transport headroom.
    phase = {'inspect_request': 'request_inspection', 'inspect_metadata': 'response_metadata_inspection',
             'inspect_response': 'response_inspection'}.get(callback.__name__)
    def completed(queue_ms, work_ms):
      if self.measure is not None and phase:
        self.measure(phase, queue_ms+work_ms)
      if self.timeline is not None and phase:
        run_id = getattr(self.engine, 'run_id', None)
        self.timeline.inspection(run_id, phase,
                                 queue_ms=queue_ms, work_ms=work_ms)
        if phase == 'request_inspection' and self.stream_wait_ms is not None:
          self.timeline.stream_wait(run_id, self.stream_wait_ms)
    return await self.workers.run(callback, *args,
      deadline=min(deadline, time.monotonic() + 1.5), on_timing=completed, **kwargs)

  async def Process(self, request_iterator, context):
    request_headers = response_headers = None
    request_checked = response_checked = False
    request_verdict = None
    method = authority = path = ""
    deadline = time.monotonic() + self.stream_timeout
    stream_queued = time.perf_counter()
    try:
      async with asyncio.timeout(self.stream_timeout):
        async with self.slots:
          self.stream_wait_ms = (time.perf_counter()-stream_queued)*1000
          async for event in request_iterator:
            kind = event.WhichOneof("request")
            if event.observability_mode:
              raise InspectionError("extproc_observability_not_supported")
            if kind == "request_headers":
              if request_headers is not None:
                raise InspectionError("unexpected_protocol_sequence")
              request_headers = proto_headers(event.request_headers.headers)
              method = request_headers.get(":method", "")
              authority = request_headers.get(":authority", request_headers.get("host", ""))
              path = request_headers.get(":path", "")
              # Strip untrusted identity/context headers from the destination, not from inspection.
              mutation = pb.HeaderMutation(remove_headers=remove_context(request_headers))
              if event.request_headers.end_of_stream:
                verdict = await self._inspect(self.engine.inspect_request,
                  HttpMessage(method, authority, path, request_headers, b""), mode="inline", deadline=deadline)
                request_verdict = verdict
                self.audit.record(verdict, phase="request")
                request_checked = True
                if self.timeline is not None:
                  self.timeline.mark(getattr(self.engine, 'run_id', None), 'request_checked')
                if verdict.action not in ("allow", "redact"):
                  yield immediate(verdict)
                  return
              yield pb.ProcessingResponse(request_headers=pb.HeadersResponse(
                response=pb.CommonResponse(header_mutation=mutation)))
            elif kind == "request_body":
              if request_headers is None or request_checked:
                raise InspectionError("unexpected_protocol_sequence")
              message = HttpMessage(method, authority, path, request_headers,
                                    bytes(event.request_body.body), event.request_body.end_of_stream)
              verdict = await self._inspect(self.engine.inspect_request, message, mode="inline", deadline=deadline)
              request_verdict = verdict
              self.audit.record(verdict, phase="request")
              request_checked = True
              if self.timeline is not None:
                self.timeline.mark(getattr(self.engine, 'run_id', None), 'request_checked')
              if verdict.action not in ("allow", "redact"):
                yield immediate(verdict)
                return
              common = pb.CommonResponse()
              if verdict.body is not None:
                common.body_mutation.body = verdict.body
                common.header_mutation.remove_headers.append("content-length")
              yield pb.ProcessingResponse(request_body=pb.BodyResponse(response=common))
            elif kind == "response_headers":
              if not request_checked or response_headers is not None:
                raise InspectionError("unexpected_protocol_sequence")
              if self.timeline is not None:
                self.timeline.mark(getattr(self.engine, 'run_id', None), 'response_headers_received')
              # Native model APIs do not establish browser sessions. Discard their
              # cookies before scanning and forwarding; never exempt forwarded data.
              remove_cookie = False
              config = getattr(self.engine, "config", None)
              if config is not None and getattr(self.engine, "policy", {}).get("mode") != "mirror":
                route = route_for(HttpMessage(method, authority, path, request_headers, b""), config)
                remove_cookie = bool(route.llm_provider)
              header_values = event.response_headers.headers
              if remove_cookie:
                header_values = type(header_values)(headers=[h for h in header_values.headers
                  if h.key.lower() != "set-cookie"])
              response_headers = proto_headers(header_values)
              if response_headers.get("content-encoding", "identity").lower() != "identity":
                raise InspectionError("unsupported_content_encoding")
              await self._inspect(self.engine.inspect_metadata,
                HttpMessage(method, authority, path, response_headers, b""), response=True, deadline=deadline)
              if self.timeline is not None:
                self.timeline.mark(getattr(self.engine, 'run_id', None), 'response_headers_checked')
              if event.response_headers.end_of_stream:
                response_checked = True
                if self.timeline is not None:
                  self.timeline.mark(getattr(self.engine, 'run_id', None), 'response_checked')
              common = pb.CommonResponse()
              if remove_cookie:
                common.header_mutation.remove_headers.append("set-cookie")
              yield pb.ProcessingResponse(response_headers=pb.HeadersResponse(response=common))
            elif kind == "response_body":
              if response_headers is None or response_checked:
                raise InspectionError("unexpected_protocol_sequence")
              if self.timeline is not None:
                self.timeline.mark(getattr(self.engine, 'run_id', None), 'response_body_received')
              message = HttpMessage(method, authority, path, response_headers,
                                    bytes(event.response_body.body), event.response_body.end_of_stream)
              verdict = await self._inspect(self.engine.inspect_response, message, mode="inline",
                pii_action=request_verdict.pii_policy_action,
                pii_policy_scope=request_verdict.pii_policy_scope, deadline=deadline)
              self.audit.record(verdict, phase="response")
              response_checked = True
              if self.timeline is not None:
                self.timeline.mark(getattr(self.engine, 'run_id', None), 'response_checked')
              if verdict.action not in ("allow", "redact"):
                yield immediate(verdict)
                return
              common = pb.CommonResponse()
              if verdict.body is not None:
                common.body_mutation.body = verdict.body
                common.header_mutation.remove_headers.append("content-length")
              yield pb.ProcessingResponse(response_body=pb.BodyResponse(response=common))
            else:
              raise InspectionError("unsupported_extproc_message")
          if not request_checked or not response_checked:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "incomplete_inspection_stream")
    except InspectionError as exc:
      verdict = Verdict("block", str(exc), "inline", coverage="incomplete")
      self.audit.record(verdict, phase="transport")
      yield immediate(verdict)
    except TimeoutError:
      await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "inspection_deadline")
    except asyncio.CancelledError:
      raise
    except grpc.aio.AbortError:
      raise
    except Exception:  # noqa: BLE001 - clean closure on failure would permit forwarding
      # A clean gRPC close means fail-open in ExtProc; always abort on unexpected failure.
      await context.abort(grpc.StatusCode.INTERNAL, "inspection_unavailable")


async def bounded_body(request: Request, limit: int) -> bytes:
  body = bytearray()
  async with asyncio.timeout(10):
    async for chunk in request.stream():
      if len(body) + len(chunk) > limit:
        raise InspectionError("body_limit_exceeded")
      body.extend(chunk)
  return bytes(body)


def create_mirror_app(engine: InspectionEngine, audit: InspectionAudit) -> FastAPI:
  """No upstream HTTP client and no forwarding route exist in this application."""
  app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
  workers = InspectionWorkers()

  @app.get("/_trapdefense/health")
  async def health():
    return {"status": "ok", "mode": "mirror", "enforcement_applied": False}

  @app.post("/_trapdefense/observe")
  async def observe(request: Request):
    # Transcript transport includes request plus optional response, with explicit completeness.
    try:
      raw = await bounded_body(request, engine.config.max_body_bytes * 3)
      value = strict_json(raw)
      if not isinstance(value, dict):
        raise TypeError()
      incoming = value["request"]
      if not isinstance(incoming, dict) or not isinstance(incoming.get("headers"), dict):
        raise TypeError()
      message = HttpMessage(incoming["method"], incoming["authority"], incoming["path"],
        normalized_headers(incoming["headers"].items()),
        base64.b64decode(incoming["body_base64"], validate=True),
        complete=incoming.get("complete") is True)
      async with asyncio.timeout(10):
        verdict = await workers.run(engine.inspect_request, message, mode="mirror")
      event = audit.record(verdict, phase="request")
      response = value.get("response")
      response_event = None
      if response is not None:
        if not isinstance(response, dict) or not isinstance(response.get("headers"), dict):
          raise ValueError()
        response_message = HttpMessage(message.method, message.authority, message.path,
          normalized_headers(response["headers"].items()),
          base64.b64decode(response["body_base64"], validate=True),
          complete=response.get("complete") is True)
        async with asyncio.timeout(10):
          result = await workers.run(engine.inspect_response, response_message, mode="mirror",
            pii_action=verdict.pii_policy_action, pii_policy_scope=verdict.pii_policy_scope)
        response_event = audit.record(result, phase="response")
      return {"request": event, "response": response_event,
              "visibility": "request_response" if response else "request_only",
              "enforcement_applied": False}
    except (InspectionError, ValueError, TypeError, KeyError, TimeoutError):
      verdict = Verdict("unknown", "invalid_or_oversized_transcript", "mirror", coverage="incomplete")
      return JSONResponse(audit.record(verdict, phase="capture"), status_code=400)

  @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
  async def mirror_raw(path: str, request: Request):
    try:
      headers = normalized_headers((k.decode("latin-1"), v.decode("latin-1"))
                                   for k, v in request.scope["headers"])
      body = await bounded_body(request, engine.config.max_body_bytes)
      raw_path = request.scope["raw_path"].decode("ascii")
      if request.scope["query_string"]:
        raw_path += "?" + request.scope["query_string"].decode("ascii")
      message = HttpMessage(request.method, headers.get("host", ""), raw_path, headers, body)
      async with asyncio.timeout(10):
        verdict = await workers.run(engine.inspect_request, message, mode="mirror")
    except (InspectionError, UnicodeError, TimeoutError):
      verdict = Verdict("unknown", "invalid_or_oversized_capture", "mirror", coverage="incomplete")
    event = audit.record(verdict, phase="request")
    return {**event, "visibility": "request_only"}

  return app


async def watch_parent(web, parent_pid):
  while os.getppid() == parent_pid:
    await asyncio.sleep(.25)
  web.should_exit = True


async def run(args):
  parent_pid = getattr(args, "parent_pid", None)
  if parent_pid is not None and os.getppid() != parent_pid:
    raise RuntimeError("inspector_parent_unavailable")
  from .pii import PresidioScanner
  config = InspectionConfig.model_validate(yaml.safe_load(Path(args.config).read_text()))
  authorizer = load_authorizer(config)
  key_path = Path(args.key_file)
  if key_path.stat().st_mode & 0o077:
    raise ValueError("key_file_must_be_owner_only")
  verifier = AttestationVerifier(key_path.read_bytes(), config.nonce_db,
    max_age=config.attestation_max_age_seconds,
    required_fields=IDENTITY_FIELDS if config.access_broker_enabled else ("source_id",))
  engine = InspectionEngine(config, PresidioScanner(score_threshold=config.pii_min_score), verifier,
                            authorizer)
  audit = InspectionAudit(config.audit_path)
  server = grpc.aio.server(options=[("grpc.max_receive_message_length", config.max_body_bytes + 65536)],
                           maximum_concurrent_rpcs=32)
  rpc.add_ExternalProcessorServicer_to_server(ExternalProcessor(engine, audit,
    stream_timeout=args.stream_timeout), server)
  if not server.add_insecure_port(f"{args.grpc_host}:{args.grpc_port}"):
    raise RuntimeError("grpc_bind_failed")
  await server.start()
  web = uvicorn.Server(uvicorn.Config(create_mirror_app(engine, audit), host=args.mirror_host,
    port=args.mirror_port, access_log=False, limit_concurrency=32, timeout_keep_alive=5,
    timeout_graceful_shutdown=3 if parent_pid is not None else None))
  watcher = asyncio.create_task(watch_parent(web, parent_pid)) if parent_pid is not None else None
  try:
    await web.serve()
  finally:
    if watcher is not None:
      watcher.cancel()
      await asyncio.gather(watcher, return_exceptions=True)
    await server.stop(grace=2)


def main():
  parser = argparse.ArgumentParser(description="TrapDefense inline ExtProc and mirror inspector")
  parser.add_argument("--config", required=True)
  parser.add_argument("--key-file", required=True)
  parser.add_argument("--grpc-host", default="127.0.0.1")
  parser.add_argument("--grpc-port", type=int, default=18081)
  parser.add_argument("--mirror-host", default="127.0.0.1")
  parser.add_argument("--mirror-port", type=int, default=18083)
  parser.add_argument("--stream-timeout", type=float, default=20)
  parser.add_argument("--parent-pid", type=int, help=argparse.SUPPRESS)
  asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
  main()
