from __future__ import annotations

import asyncio
import importlib.util
import json
import time

import pytest

grpc = pytest.importorskip("grpc")
pb = pytest.importorskip("envoy.service.ext_proc.v3.external_processor_pb2")
core = pytest.importorskip("envoy.config.core.v3.base_pb2")

from asr_proxy.inspection.contracts import InspectionConfig, Verdict
from asr_proxy.inspection.engine import InspectionEngine
from asr_proxy.inspection.pii import PresidioScanner
from asr_proxy.inspection.server import ExternalProcessor, immediate
from asr_proxy.selfhost.latency import LatencyMetrics


class Engine:
  def __init__(self, *, request=None, response=None, error=None, metadata_checker=None, delay=0):
    self.request_verdict = request or Verdict("allow", "test_allowed", "inline")
    self.response_verdict = response or Verdict("allow", "test_clean", "inline")
    self.error, self.metadata_checker, self.delay = error, metadata_checker, delay
    self.calls = []

  def inspect_request(self, message, *, mode):
    self.calls.append(("request", message, mode))
    if self.delay:
      time.sleep(self.delay)
    if self.error:
      raise self.error
    return self.request_verdict

  def inspect_response(self, message, *, mode, pii_action=None, pii_policy_scope=None):
    self.calls.append(("response", message, mode))
    assert pii_action == self.request_verdict.pii_policy_action
    assert pii_policy_scope == self.request_verdict.pii_policy_scope
    if self.error:
      raise self.error
    return self.response_verdict

  def inspect_metadata(self, message, *, response=False):
    self.calls.append(("metadata", message, response))
    if self.metadata_checker:
      return self.metadata_checker(message, response=response)


class Audit:
  def __init__(self, *, error=None):
    self.records, self.error = [], error

  def record(self, verdict, *, phase, applied=False):
    if self.error:
      raise self.error
    event = verdict.evidence(phase=phase, applied=applied)
    self.records.append(event)
    return event


class Context:
  def __init__(self):
    self.aborts = []

  async def abort(self, code, details):
    self.aborts.append((code, details))
    # Match the real grpc.aio exception hierarchy (AbortError inherits Exception).
    raise grpc.aio.AbortError(details)


def headers(kind="request_headers", *, end=False, values=None):
  pairs = values if values is not None else (
    [(":method", "POST"), (":authority", "example.test"), (":path", "/mcp"),
     ("content-type", "application/json")]
    if kind == "request_headers" else [(":status", "200"), ("content-type", "application/json")]
  )
  message = pb.HttpHeaders(headers=core.HeaderMap(headers=[
    core.HeaderValue(key=key, raw_value=value.encode("latin-1")) for key, value in pairs
  ]), end_of_stream=end)
  return pb.ProcessingRequest(**{kind: message})


def body(kind="request_body", *, end=True, value=b"{}"):
  return pb.ProcessingRequest(**{kind: pb.HttpBody(body=value, end_of_stream=end)})


async def event_stream(events, *, stall=False):
  for event in events:
    yield event
  if stall:
    await asyncio.Event().wait()


async def collect(processor, events, *, stall=False):
  context, output = Context(), []
  try:
    async for result in processor.Process(event_stream(events, stall=stall), context):
      # The real generated schema must accept every response, including ImmediateResponse.body.
      result.SerializeToString()
      output.append(result)
  except grpc.aio.AbortError:
    pass
  return output, context


def run(events, *, engine=None, audit=None, timeout=0.5, stall=False):
  processor = ExternalProcessor(engine or Engine(), audit or Audit(), stream_timeout=timeout)
  return asyncio.run(collect(processor, events, stall=stall))


def decision(response):
  assert response.WhichOneof("response") == "immediate_response"
  return json.loads(response.immediate_response.body)


def test_complete_buffered_exchange_uses_real_proto_and_original_bytes():
  engine, audit = Engine(), Audit()
  output, context = run([headers(), body(value=b'{"value":1}'),
                         headers("response_headers"), body("response_body", value=b'{"ok":true}')],
                        engine=engine, audit=audit)
  assert context.aborts == []
  assert [item.WhichOneof("response") for item in output] == [
    "request_headers", "request_body", "response_headers", "response_body",
  ]
  assert engine.calls[0][1].body == b'{"value":1}'
  assert engine.calls[-1][1].body == b'{"ok":true}'
  assert [item["phase"] for item in audit.records] == ["request", "response"]
  assert not output[1].request_body.response.HasField("body_mutation")


def test_complete_header_only_exchange_is_inspected():
  engine = Engine()
  engine.run_id='c'*32
  timeline=LatencyMetrics();timeline.begin(engine.run_id)
  processor=ExternalProcessor(engine,Audit(),stream_timeout=.5,timeline=timeline)
  output, context = asyncio.run(collect(processor,
    [headers(end=True), headers("response_headers", end=True)]))
  timeline.finish(engine.run_id,204)
  assert context.aborts == [] and len(output) == 2
  assert [(phase, message.body) for phase, message, _ in engine.calls] == [("request", b""), ("metadata", b"")]
  row=timeline.snapshot()['requests'][0]
  assert row['complete'] is True and row['response_body_wait_ms'] is None


@pytest.mark.parametrize("events", [
  [], [headers()], [headers(end=True)], [headers(), body()],
  [headers(), body(), headers("response_headers")],
])
def test_premature_eof_aborts_instead_of_clean_close(events):
  _, context = run(events)
  assert context.aborts == [(grpc.StatusCode.INVALID_ARGUMENT, "incomplete_inspection_stream")]


def test_headers_without_eof_hit_deadline():
  output, context = run([headers()], stall=True, timeout=0.02)
  assert len(output) == 1
  assert context.aborts == [(grpc.StatusCode.DEADLINE_EXCEEDED, "inspection_deadline")]


def test_waiting_for_admission_also_hits_deadline():
  async def exercise():
    engine = Engine()
    processor = ExternalProcessor(engine, Audit(), stream_timeout=0.02)
    processor.slots = asyncio.Semaphore(0)
    result = await collect(processor, [headers(end=True)])
    assert engine.calls == []
    return result

  output, context = asyncio.run(exercise())
  assert output == []
  assert context.aborts == [(grpc.StatusCode.DEADLINE_EXCEEDED, "inspection_deadline")]


def test_slow_inspection_cannot_emit_late_allow():
  output, context = run([headers(end=True)], engine=Engine(delay=0.05), timeout=0.01)
  assert output == []
  assert context.aborts == [(grpc.StatusCode.DEADLINE_EXCEEDED, "inspection_deadline")]


@pytest.mark.parametrize("error", [RuntimeError("synthetic private payload"), OSError("synthetic private payload")])
def test_runtime_failure_always_aborts_without_payload(error):
  output, context = run([headers(end=True)], engine=Engine(error=error))
  assert output == []
  assert context.aborts == [(grpc.StatusCode.INTERNAL, "inspection_unavailable")]
  assert "private payload" not in repr(context.aborts)


def test_audit_failure_does_not_permit_forwarding():
  output, context = run([headers(end=True)], audit=Audit(error=OSError("audit unavailable")))
  assert output == []
  assert context.aborts == [(grpc.StatusCode.INTERNAL, "inspection_unavailable")]


def test_blocked_request_emits_one_immediate_and_never_inspects_response():
  engine = Engine(request=Verdict("block", "pii_block_policy", "inline"))
  output, context = run([headers(), body(), headers("response_headers", end=True)], engine=engine)
  assert context.aborts == []
  assert decision(output[-1])["error"] == "pii_block_policy"
  assert output[-1].immediate_response.status.code == 403
  assert [phase for phase, _, _ in engine.calls] == ["request"]


def test_actual_body_mutations_remove_stale_length():
  engine = Engine(request=Verdict("redact", "pii_redacted", "inline", body=b'{"v":"safe"}'),
                  response=Verdict("redact", "response_pii_redacted", "inline", body=b'{"r":"safe"}'))
  output, context = run([headers(), body(), headers("response_headers"), body("response_body")], engine=engine)
  assert context.aborts == []
  request, response = output[1].request_body.response, output[3].response_body.response
  assert request.body_mutation.body == b'{"v":"safe"}' and response.body_mutation.body == b'{"r":"safe"}'
  assert "content-length" in request.header_mutation.remove_headers
  assert "content-length" in response.header_mutation.remove_headers


def test_incomplete_body_is_passed_to_engine_as_incomplete_and_blocked():
  engine = Engine(request=Verdict("block", "incomplete_capture", "inline", coverage="incomplete"))
  output, context = run([headers(), body(end=False)], engine=engine)
  assert context.aborts == [] and engine.calls[0][1].complete is False
  assert decision(output[-1])["error"] == "incomplete_capture"


def test_response_header_only_pii_cannot_bypass_body_inspection():
  if importlib.util.find_spec("presidio_analyzer") is None:
    pytest.skip("optional Presidio dependency is not installed")
  real_engine = InspectionEngine(InspectionConfig(routes=[]), PresidioScanner(), None, None)
  engine = Engine(metadata_checker=real_engine.inspect_metadata)
  output, context = run([headers(end=True), headers("response_headers", end=True,
    values=[(":status", "204"), ("x-note", "synthetic@example.com")])], engine=engine)
  assert context.aborts == []
  assert decision(output[-1])["decision"] == "block"
  assert "synthetic@example.com" not in output[-1].immediate_response.body.decode()


@pytest.mark.parametrize("events,reason", [
  ([headers(), headers()], "unexpected_protocol_sequence"),
  ([body()], "unexpected_protocol_sequence"),
  ([headers(), headers("response_headers")], "unexpected_protocol_sequence"),
  ([headers(end=True), body()], "unexpected_protocol_sequence"),
  ([headers(end=True), headers("response_headers", end=True), body("response_body")], "unexpected_protocol_sequence"),
  ([pb.ProcessingRequest(request_trailers=pb.HttpTrailers())], "unsupported_extproc_message"),
  ([pb.ProcessingRequest()], "unsupported_extproc_message"),
  ([headers(values=[(":method", "POST"), ("x-test", "one"), ("X-Test", "two")])], "ambiguous_headers"),
  ([headers(values=[(":authority", "one.test"), ("host", "two.test")])], "authority_host_mismatch"),
  ([headers(values=[("content-length", "1"), ("transfer-encoding", "chunked")])], "ambiguous_framing"),
])
def test_protocol_errors_emit_immediate_block(events, reason):
  output, context = run(events)
  assert context.aborts == []
  assert decision(output[-1])["error"] == reason


def test_observability_mode_is_rejected_not_treated_as_inline():
  event = headers()
  event.observability_mode = True
  output, context = run([event])
  assert context.aborts == []
  assert decision(output[-1])["error"] == "extproc_observability_not_supported"


def test_context_headers_removed_from_destination_but_remain_available_to_inspection():
  pairs = [(":method", "GET"), (":authority", "example.test"), (":path", "/mcp"),
           ("x-td-attestation", "test-only"), ("x-asr-mode", "test-only"),
           ("x-forwarded-user", "test-only"), ("x-normal", "safe")]
  engine = Engine()
  output, context = run([headers(end=True, values=pairs), headers("response_headers", end=True)], engine=engine)
  assert context.aborts == []
  removed = set(output[0].request_headers.response.header_mutation.remove_headers)
  assert {"x-td-attestation", "x-asr-mode", "x-forwarded-user"} <= removed
  assert "x-normal" not in removed
  assert engine.calls[0][1].headers["x-td-attestation"] == "test-only"


@pytest.mark.parametrize("action,reason,status", [
  ("block", "pii_block_policy", 403),
  ("approval_required", "high_risk_action_requires_approval", 428),
  ("block", "inspection_unavailable", 503),
  ("block", "mcp_header_body_mismatch", 400),
])
def test_immediate_payload_schema_and_status(action, reason, status):
  response = immediate(Verdict(action, reason, "inline"))
  assert response.immediate_response.status.code == status
  assert decision(response) == {"error": reason, "decision": action, "approval_id": None}
  assert isinstance(response.immediate_response.body, bytes)


def test_cancellation_is_propagated():
  async def cancelled_stream():
    raise asyncio.CancelledError()
    yield

  async def exercise():
    context = Context()
    processor = ExternalProcessor(Engine(), Audit())
    with pytest.raises(asyncio.CancelledError):
      async for _ in processor.Process(cancelled_stream(), context):
        pass
    assert context.aborts == []

  asyncio.run(exercise())


@pytest.mark.parametrize("provider,mirror,removed", [("openai",False,True),(None,False,False),("openai",True,False)])
def test_model_response_cookies_are_removed_not_exempted(provider,mirror,removed):
  engine=Engine()
  engine.config=InspectionConfig(routes=[{"authority":"example.test","path":"/mcp","llm_provider":provider}])
  engine.policy={"mode":"mirror" if mirror else "inline"}
  output,_=run([headers(),body(),headers("response_headers",values=[
    (":status","200"),("content-type","application/json"),("set-cookie","opaque=1234567890"),
    ("x-business-data","alex@example.com")]),body("response_body")],engine=engine)
  mutation=output[2].response_headers.response.header_mutation
  assert ("set-cookie" in mutation.remove_headers)==removed
  response_metadata=[c[1] for c in engine.calls if c[0]=="metadata" and c[2]][0]
  assert ("set-cookie" not in response_metadata.headers)==removed
  assert response_metadata.headers["x-business-data"]=="alex@example.com"
