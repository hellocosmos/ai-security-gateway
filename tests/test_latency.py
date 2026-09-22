"""Timing collection is bounded and cannot contain traffic payloads."""
import asyncio
import math
import pytest
import httpx
from fastapi.testclient import TestClient
from asr_proxy.selfhost.latency import LatencyMetrics
from asr_proxy.selfhost.gateway import create_gateway
from asr_proxy.selfhost.config import load
from asr_proxy.selfhost.config import Deployment
from asr_proxy.inspection.server import ExternalProcessor, InspectionWorkers
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
    transport=httpx.MockTransport(destination),measure=metrics.record,timeline=metrics)
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
    transport=httpx.MockTransport(destination),measure=metrics.record,timeline=metrics)
  with TestClient(app) as client:
    result=client.post('/api/notes',headers={'x-td-client-key':'synthetic-client-key'},json={'message':'safe'})
  assert result.status_code==200 and result.json()=={'message':'safe'}
  assert 'server-timing' not in result.headers
  samples=metrics.snapshot()['series']
  assert samples[0]['samples']==samples[1]['samples']==1
  assert samples[0]['max_ms']>=samples[1]['max_ms']
  request=metrics.snapshot()['requests'][0]
  assert request['http_status']==200 and request['before_envoy_ms'] is not None
  assert 'synthetic-client-key' not in str(request)


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


def test_correlated_timeline_is_bounded_sanitized_and_does_not_sum_overlaps():
  metrics=LatencyMetrics()
  identity='a'*32
  metrics.begin(identity, at=1.0)
  for stage, at in [('envoy_sent',1.01),('request_checked',1.02),
                    ('response_headers_received',1.10),('response_headers_checked',1.11),
                    ('response_body_received',1.30),('response_checked',1.32)]:
    metrics.mark(identity,stage,at=at)
  metrics.inspection(identity,'request_inspection',queue_ms=2,work_ms=8)
  metrics.inspection(identity,'response_inspection',queue_ms=3,work_ms=17)
  metrics.stream_wait(identity,7)
  metrics.finish(identity,200,at=1.34)
  report=metrics.snapshot()['requests'][0]
  assert report['gateway_total_ms']==340.0
  assert report['upstream_headers_wait_ms']==80.0
  assert report['response_body_wait_ms']==190.0
  assert report['inspection_queue_ms']==5.0
  assert report['inspection_work_ms']==25.0
  assert report['inspector_stream_wait_ms']==7.0
  assert identity not in str(metrics.snapshot())
  assert not metrics.pending
  for i in range(300):
    key=f'{i:032x}'
    metrics.begin(key,at=2.0)
    metrics.finish(key,503,at=2.01)
  assert len(metrics.snapshot()['requests'])==64
  assert all(set(item)<=set(report) for item in metrics.snapshot()['requests'])


def test_admission_setting_has_strict_bounds_and_public_shape():
  base=load(Path(__file__).parents[1]/'deploy/selfhost/deployment.yaml').model_dump(exclude_none=True)
  assert Deployment.model_validate(base).gateway_max_inflight==32
  for invalid in (0,3,65,'16',True):
    with pytest.raises(ValueError):Deployment.model_validate({**base,'gateway_max_inflight':invalid})
  selected=Deployment.model_validate({**base,'gateway_max_inflight':16})
  assert selected.public()['gateway_max_inflight']==16


def test_incomplete_timeline_does_not_invent_inspection_time():
  metrics=LatencyMetrics()
  metrics.begin('b'*32,at=1.0)
  metrics.finish('b'*32,503,at=1.01)
  row=metrics.snapshot()['requests'][0]
  assert row['complete'] is False and row['gateway_total_ms']==10.0
  assert row['inspection_queue_ms'] is None and row['inspection_work_ms'] is None
  assert row['response_body_wait_ms'] is None and row['inspector_stream_wait_ms'] is None
  assert 'b'*32 not in str(metrics.snapshot())


def test_header_only_response_is_complete_without_fabricated_body_wait():
  metrics=LatencyMetrics()
  key='c'*32
  metrics.begin(key,at=1.0)
  for stage, at in [('request_checked',1.01),('response_headers_checked',1.02),
                    ('response_checked',1.02)]:
    metrics.mark(key,stage,at=at)
  metrics.finish(key,204,at=1.03)
  row=metrics.snapshot()['requests'][0]
  assert row['complete'] is True and row['response_body_wait_ms'] is None


def test_cancelled_inspection_records_actual_worker_completion():
  import threading
  import time
  calls=[]
  workers=InspectionWorkers(maximum=1)
  started=threading.Event()
  release=threading.Event()
  def blocking():
    started.set();release.wait(2)
    return 'completed'
  async def run():
    task=asyncio.create_task(workers.run(blocking,on_timing=lambda queue,work:calls.append((queue,work))))
    assert await asyncio.to_thread(started.wait,1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert workers.slots.locked() and not calls
    release.set()
    for _ in range(100):
      if calls and not workers.slots.locked():break
      await asyncio.sleep(.01)
    assert len(calls)==1 and not workers.slots.locked()
    assert calls[0][1]>=0
  asyncio.run(run())
