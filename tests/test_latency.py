"""Timing collection is bounded and cannot contain traffic payloads."""
import asyncio
import math
import pytest
import httpx
from fastapi.testclient import TestClient
from asr_proxy.selfhost.latency import LatencyMetrics
from asr_proxy.selfhost.gateway import create_gateway
from asr_proxy.selfhost.config import load
from asr_proxy.inspection.server import ExternalProcessor
from pathlib import Path


def test_bounded_finite_samples_and_empty_state():
  metrics=LatencyMetrics()
  assert all(s['p50_ms'] is None and s['samples']==0 for s in metrics.snapshot()['series'])
  for value in range(300): metrics.record('gateway_total',value)
  for value in (math.nan,math.inf,-1,'secret'):metrics.record('gateway_total',value)
  metrics.record('secret',1)
  series=metrics.snapshot()['series'][0]
  assert series=={'phase':'gateway_total','samples':256,'p50_ms':171.0,'p95_ms':287.0,'max_ms':299.0}


def test_gateway_latency_does_not_expose_headers_or_change_result():
  config=load(Path(__file__).parents[1]/'deploy/selfhost/deployment.yaml')
  metrics=LatencyMetrics()
  async def destination(request):return httpx.Response(200,json={'message':'safe'})
  app=create_gateway(config,'synthetic-client-key',b'x'*32,
    transport=httpx.MockTransport(destination),measure=metrics.record)
  with TestClient(app) as client:
    denied=client.post('/echo',json={'message':'private'})
    assert denied.status_code==401
  samples=metrics.snapshot()['series']
  assert samples[0]['samples']==1 and samples[1]['samples']==0
  assert 'private' not in str(samples) and 'synthetic-client-key' not in str(samples)


def test_inspector_records_failed_and_successful_calls():
  metrics=LatencyMetrics()
  processor=ExternalProcessor(None,None,measure=metrics.record)
  def inspect_request():return 'same verdict'
  def inspect_response():raise ValueError('synthetic')
  async def run():
    import time
    assert await processor._inspect(inspect_request,deadline=time.monotonic()+5)=='same verdict'
    try:await processor._inspect(inspect_response,deadline=time.monotonic()+5)
    except ValueError:pass
    else:raise AssertionError('failure swallowed')
  asyncio.run(run())
  samples={s['phase']:s for s in metrics.snapshot()['series']}
  assert samples['request_inspection']['samples']==samples['response_inspection']['samples']==1


def test_gateway_success_measures_exchange_without_timing_headers():
  config=load(Path(__file__).parents[1]/'deploy/selfhost/deployment.yaml')
  metrics=LatencyMetrics()
  async def destination(request):
    assert 'x-td-attestation' in request.headers
    class Body(httpx.AsyncByteStream):
      async def __aiter__(self):yield b'{"message":"safe"}'
    return httpx.Response(200,stream=Body(),headers={'content-type':'application/json'})
  app=create_gateway(config,'synthetic-client-key',b'x'*32,
    transport=httpx.MockTransport(destination),measure=metrics.record)
  with TestClient(app) as client:
    result=client.post('/api/notes',headers={'x-td-client-key':'synthetic-client-key'},json={'message':'safe'})
  assert result.status_code==200 and result.json()=={'message':'safe'}
  assert 'server-timing' not in result.headers
  samples=metrics.snapshot()['series']
  assert samples[0]['samples']==samples[1]['samples']==1
  assert samples[0]['max_ms']>=samples[1]['max_ms']


def test_benchmark_first_content_excludes_empty_events_and_errors(monkeypatch):
  pytest.importorskip('openai')
  pytest.importorskip('mcp')
  monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))
  from examples.latency.benchmark import sample
  class Chunks(httpx.AsyncByteStream):
    async def __aiter__(self):
      yield b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n'
      await asyncio.sleep(.025)
      yield b'data: {"choices":[{"delta":{"content":"safe"}}]}\n\ndata: [DONE]\n\n'
  async def run():
    async def handler(request):return httpx.Response(200,stream=Chunks())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
      result=await sample(client,'https://fixture.invalid','synthetic','short')
    assert result['first_content_ms']>=20 and result['complete'] and result['status']==200
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(503,json={'error':'busy'}))) as client:
      result=await sample(client,'https://fixture.invalid','synthetic','short')
    assert result['first_content_ms'] is None and not result['complete'] and result['status']==503
  asyncio.run(run())
