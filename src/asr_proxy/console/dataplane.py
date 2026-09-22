"""Compose the existing ExtProc protocol with per-stream policy and audit context."""
import asyncio
import json
import time
from dataclasses import replace
from uuid import uuid4
from threading import Lock

from envoy.service.ext_proc.v3 import external_processor_pb2_grpc as rpc
from asr_proxy.inspection.contracts import Verdict
from asr_proxy.inspection.server import ExternalProcessor, InspectionWorkers
from .scenarios import CASES, TOOLS
from .store import now


class StreamInspection:
  def __init__(self,runtime):
    self.runtime=runtime
    with runtime.lock:
      self.engine,self.policy=runtime.stream_snapshot()
    self.config=self.engine.config
    self.message=None
    self.identity={}
    self.verdict=None
    self.response_verdict=None
    self.upstream_received=None
    self.started=time.perf_counter()
    self.completed=False
    self.finished=False
    self.finish_lock=Lock()
    self.run_id=uuid4().hex

  def inspect_request(self,message,*,mode):
    self.message=message
    try:
      self.identity=self.engine.verifier.verify(message,consume=False)
      candidate=self.identity.get('run_id','')
      if isinstance(candidate,str) and len(candidate)==32 and all(c in '0123456789abcdef' for c in candidate):self.run_id=candidate
    except ValueError:self.identity={}
    mode=self.policy['mode']
    result=self.engine.inspect_request(message,mode=mode)
    self.verdict=result
    if mode=='inline' and result.action not in ('allow','redact'):self.upstream_received=False
    # Observation uses the exact unmodified bytes and never creates/consumes approval.
    if mode=='mirror':return Verdict('allow','observation_only','inline')
    return result

  def inspect_metadata(self,message,*,response=False):
    if response:self.upstream_received=True
    if self.policy['mode']=='mirror':return
    return self.engine.inspect_metadata(message,response=response)

  def inspect_response(self,message,*,mode,pii_action=None,pii_policy_scope=None):
    self.response_verdict=self.engine.inspect_response(message,mode=self.policy['mode'],
      pii_action=self.verdict.pii_policy_action if self.verdict else None,
      pii_policy_scope=self.verdict.pii_policy_scope if self.verdict else None)
    if self.policy['mode']=='mirror':return Verdict('allow','observation_only','inline')
    return self.response_verdict

  def record(self,verdict,*,phase):
    if phase=='transport':self.verdict=verdict

  def finish(self):
    # Final replies can race stream cancellation. Persist exactly once.
    with self.finish_lock:
      if self.finished:return
      self.persist()
      self.finished=True

  def persist(self):
    verdict=self.verdict or Verdict('unknown','inspection_stream_failed',self.policy['mode'],coverage='incomplete')
    if self.response_verdict and self.response_verdict.action!='allow':verdict=self.response_verdict
    if not self.completed and verdict.action in ('allow','redact'):
      verdict=Verdict('unknown','inspection_stream_failed',self.policy['mode'],coverage='incomplete')
    case_id=self.identity.get('scenario')
    case=CASES.get(case_id,{}) if not getattr(self.runtime,'deployment',None) else {}
    mapped=next((r for r in self.config.routes if self.message and r.authority==self.message.authority and r.path==self.message.path.split('?')[0] and r.method==self.message.method),None)
    tool=self.verdict.tool if self.verdict and self.verdict.tool else case.get('tool','unmapped')
    mapped_rule=(mapped.tools.get(tool) if mapped.protocol=='mcp' else mapped.rule) if mapped else None
    base=self.verdict or verdict
    event={'ts':now(),'scenario':case_id or 'network','label':case.get('label','Proxy network request'),
      'agent':self.identity.get('agent_id','unverified'),'tool':tool,'resource':mapped_rule.resource if mapped_rule and mapped_rule.resource else TOOLS.get(tool,('','unmapped'))[1],
      'action':verdict.action,'reason':verdict.reason,'mode':self.policy['mode'],
      'latency_ms':round((time.perf_counter()-self.started)*1000,2),'policy_version':self.policy['version'],
      'source':self.identity.get('source_id','unverified') if base.source_verified else 'unverified','synthetic':case_id in CASES,
      'enforcement_applied':self.completed and self.policy['mode']=='inline',
      'authorization_scope':base.authorization_scope,'approval_id':base.approval_id,
      'pii_policy_action':base.pii_policy_action,'pii_policy_scope':base.pii_policy_scope,
      'hypothetical_action':f'would_{verdict.action}' if self.policy['mode']=='mirror' else None,
      'request_digest':base.request_digest,'source_verified':base.source_verified,'identity_verified':False,
      'entities':sorted(set(base.entities+verdict.entities)),'coverage':verdict.coverage,
      'request':{'method':self.message.method if self.message and self.message.method in ('POST','GET','PUT','DELETE','PATCH','HEAD','OPTIONS') else 'unknown',
        'authority':mapped.authority if mapped else '[UNMAPPED]',
        'path':mapped.path if mapped else '[UNMAPPED]','tool':tool,'arguments':'[CONTENT OMITTED]'},
      'transport':{'kind':'envoy_http','run_id':self.run_id,'upstream_received':self.upstream_received,
        'stream_completed':self.completed,'http_status':None},
      'steps':[{'stage':'Envoy → gRPC','status':'actual network stream'},
        {'stage':'Inspection','status':base.reason},
        {'stage':'Destination' if getattr(self.runtime,'deployment',None) else 'Synthetic destination','status':'received' if self.upstream_received else 'not forwarded' if self.upstream_received is False else 'not confirmed'}]}
    self.runtime.store.add_event(event)


class ConsoleProcessor(rpc.ExternalProcessorServicer):
  def __init__(self,runtime):
    self.runtime=runtime
    self.slots=asyncio.Semaphore(16)
    self.workers=InspectionWorkers(maximum=4)

  async def Process(self,request_iterator,context):
    inspection=StreamInspection(self.runtime)
    profile=getattr(getattr(self.runtime,'deployment',None),'llm',None)
    processor=ExternalProcessor(inspection,inspection,stream_timeout=profile.timeout_seconds+5 if profile else 20,
      measure=getattr(getattr(self.runtime,'latency',None),'record',None))
    processor.slots=self.slots
    processor.workers=self.workers
    response_has_no_body=False
    async def observed_requests():
      nonlocal response_has_no_body
      async for request in request_iterator:
        if request.WhichOneof('request')=='response_headers':
          response_has_no_body=request.response_headers.end_of_stream
        yield request
    try:
      async for result in processor.Process(observed_requests(),context):
        kind=result.WhichOneof('response')
        terminal=kind in ('immediate_response','response_body') or (kind=='response_headers' and response_has_no_body)
        if terminal:
          # Envoy may cancel immediately after the final reply; commit evidence first.
          inspection.completed=True
          await asyncio.shield(asyncio.to_thread(inspection.finish))
        yield result
    finally:
      # Cancellation before a final decision retains incomplete evidence.
      await asyncio.shield(asyncio.to_thread(inspection.finish))
