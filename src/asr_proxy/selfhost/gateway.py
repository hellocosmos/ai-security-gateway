"""Bounded authenticated adapter. Never retries or bypasses Envoy."""
import asyncio
import time
from uuid import uuid4
from urllib.parse import urlsplit
from .providers import gateway_headers
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from asr_proxy.inspection.contracts import HttpMessage, InspectionError
from asr_proxy.inspection.identity import sign_attestation, reserved_header, TRANSPORT_HEADERS
from asr_proxy.inspection.server import bounded_body
from .auth import AuthError, GatewayAuthenticator
from .credentials import CredentialError, TargetCredentialProvider


def create_gateway(config, client_key, signing_key, *, target_secret=None, authenticator=None,
                   transport=None, observe=None, measure=None, timeline=None):
  app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
  if observe is not None or measure is not None or timeline is not None:
    @app.middleware('http')
    async def record_outcome(request, call_next):
      started = time.perf_counter()
      request.state.started = started
      request.state.outcome = 'gateway_validation'
      status = None
      try:
        response = await call_next(request)
        status = response.status_code
        if observe is not None: observe(request.state.outcome, response.status_code)
        return response
      finally:
        if measure is not None:
          measure('gateway_total', (time.perf_counter()-started)*1000)
        if timeline is not None:
          timeline.finish(getattr(request.state, 'run_id', None), status)
  authority = urlsplit(config.upstream).netloc
  slots = asyncio.Semaphore(config.gateway_max_inflight)
  authenticator=authenticator or GatewayAuthenticator(config.gateway_auth,client_key=client_key)
  credentials=TargetCredentialProvider(config.target_auth,gateway_mode=config.gateway_auth.mode,
    secret=target_secret)

  if metadata:=authenticator.metadata():
    async def protected_resource_metadata():return JSONResponse(metadata)
    app.add_api_route(config.gateway_auth.metadata_path,protected_resource_metadata,methods=['GET'])

  @app.api_route('/{path:path}', methods=['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS','CONNECT'])
  async def forward(request: Request):
    # Do not echo submitted values, URLs, credentials or transport exception details.
    headers = {}
    for key, value in request.scope['headers']:
      name = key.decode('latin1').lower()
      if name in headers: return JSONResponse({'error':'duplicate_header'}, status_code=400)
      headers[name] = value.decode('latin1')
    outbound_headers=headers
    auth_headers=headers
    if config.llm:
      try:outbound_headers,auth_headers=gateway_headers(headers,config.llm,config.gateway_auth.mode)
      except ValueError as error:return JSONResponse({'error':str(error)},status_code=401)
      query=request.scope.get('query_string',b'').decode('ascii')
      if query and not (config.llm.provider=='google' and query=='alt=sse'
          and request.url.path.endswith(':streamGenerateContent')):
        return JSONResponse({'error':'unsupported_provider_query'},status_code=400)
    request.state.outcome = 'gateway_authentication'
    try:auth_result=await asyncio.to_thread(authenticator.authenticate,auth_headers)
    except AuthError as error:
      response_headers={}
      if challenge:=authenticator.challenge(error):response_headers['WWW-Authenticate']=challenge
      return JSONResponse({'error':error.code},status_code=error.status_code,headers=response_headers)
    request.state.outcome = 'gateway_validation'
    if slots.locked(): return JSONResponse({'error':'gateway_busy'}, status_code=503)
    raw_path = request.scope.get('raw_path', b'/').decode('ascii')
    mapped_routes={(r.method,r.path) for r in config.routes}
    if (request.method,raw_path) not in mapped_routes:
      if request.method in ('GET','DELETE') and any(
          route.path==raw_path and route.protocol=='mcp' for route in config.routes):
        return JSONResponse({'error':'method_not_supported'},status_code=405,headers={'Allow':'POST'})
      return JSONResponse({'error':'unmapped_route'}, status_code=403)
    if any(name in headers for name in ('upgrade','cookie','mcp-session-id','proxy-authorization')):
      return JSONResponse({'error':'unsupported_session_or_upgrade'}, status_code=400)
    if headers.get('content-encoding','identity').lower() != 'identity':
      return JSONResponse({'error':'unsupported_content_encoding'}, status_code=415)
    try:
      clean = {k:v for k,v in outbound_headers.items() if k not in TRANSPORT_HEADERS and not reserved_header(k)}
      try:clean=credentials.apply(clean,None if config.llm else headers.get('authorization'))
      except CredentialError as error:
        return JSONResponse({'error':str(error)},status_code=400)
      duration=config.llm.timeout_seconds+5 if config.llm else 12
      async with slots, asyncio.timeout(duration):
        body = await bounded_body(request, config.max_body_bytes)
        if body and headers.get('content-type','').split(';')[0].strip() not in ('application/json','application/json-rpc'):
          return JSONResponse({'error':'unsupported_request_media_type'},status_code=415)
        # Reject connection-nominated application headers rather than silently changing semantics.
        nominated = {s.strip().lower() for s in headers.get('connection','').split(',')}
        if nominated - {'','close','keep-alive'}:
          return JSONResponse({'error':'unsupported_connection_header'}, status_code=400)
        clean['host'] = authority
        clean['accept-encoding'] = 'identity'
        query = request.scope.get('query_string', b'')
        target = raw_path + ('?' + query.decode('ascii') if query else '')
        async with httpx.AsyncClient(timeout=config.llm.timeout_seconds+2 if config.llm else 8, trust_env=False, follow_redirects=False, transport=transport) as client:
          outgoing = client.build_request(request.method, 'http://envoy:18082'+target, headers=clean, content=body)
          # Sign the actual serialized target and defaults added by the HTTP client.
          message = HttpMessage(request.method, authority, outgoing.url.raw_path.decode('ascii'), dict(outgoing.headers), body)
          run_id = uuid4().hex
          request.state.run_id = run_id
          if timeline is not None:
            timeline.begin(run_id, at=request.state.started)
          outgoing.headers['x-td-attestation'] = sign_attestation(message,
            {'source_id':'selfhost-adapter','run_id':run_id,**auth_result.identity},
            signing_key, nonce=uuid4().hex)
          request.state.outcome = 'inspection_path_transport'
          if timeline is not None:
            timeline.mark(run_id, 'envoy_sent')
          exchange_started = time.perf_counter()
          response = None
          try:
            response = await client.send(outgoing, stream=True)
          except BaseException:
            if measure is not None: measure('envoy_exchange', (time.perf_counter()-exchange_started)*1000)
            raise
          request.state.outcome = 'inspection_path_response'
          try:
            if 300 <= response.status_code < 400:
              return JSONResponse({'error':'upstream_redirect_not_supported'}, status_code=502)
            if response.headers.get('content-type','').split(';')[0] == 'text/event-stream' and not config.llm:
              return JSONResponse({'error':'streaming_not_supported'}, status_code=502)
            if 'set-cookie' in response.headers or 'mcp-session-id' in response.headers:
              return JSONResponse({'error':'upstream_session_not_supported'}, status_code=502)
            data = bytearray()
            async for chunk in response.aiter_raw():
              if len(data)+len(chunk)>config.max_body_bytes:
                return JSONResponse({'error':'response_limit_exceeded'}, status_code=502)
              data.extend(chunk)
            output = {k:v for k,v in response.headers.items() if k not in TRANSPORT_HEADERS and not reserved_header(k)
                      and k not in ('server','www-authenticate')}
            return Response(bytes(data),status_code=response.status_code,headers=output)
          finally:
            await response.aclose()
            if measure is not None: measure('envoy_exchange', (time.perf_counter()-exchange_started)*1000)
    except InspectionError:
      return JSONResponse({'error':'request_limit_exceeded'}, status_code=413)
    except (httpx.HTTPError, TimeoutError):
      return JSONResponse({'error':'inspection_path_unavailable'}, status_code=503)
  return app
