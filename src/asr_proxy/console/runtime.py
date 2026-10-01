"""Management runtime which sends actual network traffic; no engine-only fallback."""
import asyncio
import json
import threading
import time
from dataclasses import replace
from uuid import uuid4

import grpc
import httpx
from envoy.service.ext_proc.v3 import external_processor_pb2_grpc as rpc
from asr_proxy.inspection.contracts import HttpMessage
from asr_proxy.inspection.identity import sign_attestation
from .store import Store
from .scenarios import Policy, CASES, TOOLS
from threading import RLock
import secrets
from asr_proxy.inspection.contracts import InspectionConfig
from asr_proxy.inspection.engine import InspectionEngine
from asr_proxy.inspection.identity import AttestationVerifier
from asr_proxy.inspection.pii import PresidioScanner
from asr_proxy.inspection.authorization import load_authorizer
from asr_proxy.inspection.identity import IDENTITY_FIELDS
from asr_proxy.access_broker import AgentRecord,ApprovalDecisionRequest,DelegationCreateRequest
from .network import NetworkManager
from .dataplane import ConsoleProcessor
from .destination import create_destination


class Runtime:
  integrated=True
  broker_tenant='synthetic-tenant'
  broker_user='synthetic-user'
  def __init__(self,directory,seed=False):
    self.store=Store(directory)
    self.lock=RLock()
    self.key=secrets.token_bytes(48)
    self.scanner=PresidioScanner()
    stored_policy=self.store.get('policy')
    if stored_policy is None:
      self.store.set('policy',Policy().model_dump())
    elif set(stored_policy.get('rules',{}))=={'notes.read','notes.delete'} and set(stored_policy.get('pii_rules',{}))=={'notes.read','notes.delete'}:
      # The local synthetic console is disposable demo state. Preserve 0.38
      # choices while adding the 0.39 approval scenario on first startup.
      stored_policy['rules']['infra.deploy']='allow'
      stored_policy['pii_rules']['infra.deploy']='inherit'
      self.store.set('policy',stored_policy)
    self.network=NetworkManager(self.store)
    self.configure(self.policy())
    self.grpc_server=None
    self.destination=None
    self.inspector_ready=False
    from .workers import WorkerManager
    self.workers=WorkerManager(self)

  def config(self,policy):
    if set(policy['rules'])!=set(TOOLS):raise ValueError('Every mapped tool must have an explicit rule')
    if set(policy['pii_rules'])!=set(TOOLS):raise ValueError('Every mapped tool must have a PII rule')
    def tool_rule(name,action,resource):
      result={'action':action,'resource':resource,'effect':policy['rules'][name]}
      if policy['pii_rules'][name]!='inherit':result['pii_action']=policy['pii_rules'][name]
      return result
    config=InspectionConfig(access_broker_enabled=True,trusted_sources=['demo-decryptor'],pii_action=policy['pii_action'],
      nonce_db=str(self.store.directory/'nonces.sqlite'),audit_path=str(self.store.directory/'inspection.jsonl'),
      broker_store=str(self.store.directory/'broker.json'),
      routes=[{'authority':'tools.demo.test','path':'/mcp','tools':{
        name:tool_rule(name,action,resource) for name,(action,resource) in TOOLS.items()},
        'redact_fields':['/params/arguments/message']}])
    network=self.store.get('network')
    if network:config.max_body_bytes=network['max_body_bytes']
    return config

  def policy(self):return Policy.model_validate(self.store.get('policy')).model_dump()

  def record_event(self,event):return self.store.add_event(event)

  def events(self):return self.store.events()

  def build_engine(self,policy):
    config=self.config(policy)
    fields=IDENTITY_FIELDS if config.access_broker_enabled else ('source_id',)
    verifier=AttestationVerifier(self.key,config.nonce_db,required_fields=fields)
    self.broker=load_authorizer(config)
    if self.broker is not None and not self.broker.store.list_agents():self.seed_broker()
    return InspectionEngine(config,self.scanner,verifier,self.broker)

  def seed_broker(self):
    by_agent={}
    for case in CASES.values():
      action,resource=TOOLS[case['tool']]
      entry=by_agent.setdefault(case['agent'],{'tools':set(),'resources':set(),'actions':set()})
      entry['tools'].add(case['tool']);entry['resources'].add(resource);entry['actions'].add(action)
    for agent_id,scope in by_agent.items():
      self.broker.register_agent(AgentRecord(agent_id=agent_id,tenant_id=self.broker_tenant,
        owner_id='synthetic-operator',runtime='synthetic-console',
        allowed_tools=sorted(scope['tools']),allowed_resources=sorted(scope['resources']),
        risk_tier='high' if agent_id=='deployment-agent' else 'medium'))
      self.broker.create_delegation(DelegationCreateRequest(
        delegation_id=f'demo-{agent_id}',tenant_id=self.broker_tenant,user_id=self.broker_user,
        agent_id=agent_id,task_id=f'task-{agent_id}',purpose='Synthetic console scenario',
        allowed_resources=sorted(scope['resources']),allowed_actions=sorted(scope['actions']),
        ttl_seconds=86400))

  def broker_snapshot(self):
    tools=[{'name':name,'action':action,'resource':resource}
      for name,(action,resource) in sorted(self.broker_tool_map().items())]
    if self.broker is None:return {'agents':[],'delegations':[],'approvals':[],'tools':tools}
    with self.broker.store.read_transaction():
      tenant=self.broker_tenant
      return {
        'agents':[item.model_dump(mode='json') for item in self.broker.store.list_agents()
          if item.tenant_id==tenant],
        'delegations':[item.model_dump(mode='json') for item in self.broker.store.list_delegations()
          if item.tenant_id==tenant],
        'approvals':[item.model_dump(mode='json') for item in self.broker.store.list_approvals()
          if item.tenant_id==tenant],
        'tools':tools,
      }

  def broker_tool_map(self):
    return TOOLS

  def broker_resources(self,tools):
    tool_map=self.broker_tool_map()
    return sorted({tool_map[tool][1] for tool in tools})

  def register_agent(self,payload,actor):
    if self.broker is None:raise ValueError('Access Broker is disabled.')
    tool_map=self.broker_tool_map()
    tools=payload['allowed_tools']
    if not tools or any(tool not in tool_map for tool in tools):raise ValueError('Unknown tool mapping.')
    with self.broker.store.read_transaction():
      if self.broker.store.get_agent(payload['agent_id']) is not None:
        raise ValueError('Agent ID is already registered.')
    resources=self.broker_resources(tools)
    record=AgentRecord(**payload,tenant_id=self.broker_tenant,runtime='console',
      allowed_resources=resources,allowed_actions=sorted({tool_map[tool][0] for tool in tools}))
    return self.broker.register_agent(record,actor=actor).model_dump(mode='json')

  def create_delegation(self,payload,actor):
    if self.broker is None:raise ValueError('Access Broker is disabled.')
    with self.broker.store.read_transaction():
      agent=self.broker.store.get_agent(payload['agent_id'])
    if agent is None or agent.tenant_id!=self.broker_tenant:raise ValueError('Agent was not found.')
    tool_map=self.broker_tool_map()
    actions=sorted({tool_map[tool][0] for tool in agent.allowed_tools if tool in tool_map})
    if not actions:raise ValueError('Agent has no manageable tool mappings.')
    request=DelegationCreateRequest(delegation_id='dlg-'+uuid4().hex[:12],
      tenant_id=self.broker_tenant,allowed_resources=agent.allowed_resources,
      allowed_actions=actions,**payload)
    return self.broker.create_delegation(request,actor=actor).model_dump(mode='json')

  def review_approval(self,approval_id,payload,actor,approved):
    if self.broker is None:raise ValueError('Access Broker is disabled.')
    with self.broker.store.read_transaction():approval=self.broker.store.get_approval(approval_id)
    if approval is None or approval.tenant_id!=self.broker_tenant:raise ValueError('Approval was not found.')
    request=ApprovalDecisionRequest(approver_id=actor['principal_id'],comment=payload.get('comment'))
    result=self.broker.approve(approval_id,request) if approved else self.broker.deny(approval_id,request)
    return result.model_dump(mode='json')

  def renew_demo_delegation(self,actor):
    if self.broker is None:raise ValueError('Access Broker is disabled.')
    agent_id='deployment-agent'
    return self.broker.create_delegation(DelegationCreateRequest(
      delegation_id=f'demo-{agent_id}',tenant_id=self.broker_tenant,user_id=self.broker_user,
      agent_id=agent_id,task_id=f'task-{agent_id}',purpose='Synthetic deployment approval',
      allowed_resources=['environment:staging'],allowed_actions=['deploy'],ttl_seconds=86400),
      actor=actor).model_dump(mode='json')

  def configure(self,policy):
    self.engine=self.build_engine(policy)
    self.engine_revision=(policy['version'],self.network.current()['version'])

  def stream_snapshot(self):
    with self.lock:
      policy=self.policy()
      revision=(policy['version'],self.network.current()['version'])
      if revision!=self.engine_revision:self.configure(policy)
      return self.engine,policy

  def inspector_control(self,action,replicas=None):
    with self.network.lock:
      if action=='stop':
        self.workers.stop()
      else:
        previous=self.store.get('inspectors') or {'replicas':1}
        candidate=replicas if replicas is not None else previous['replicas']
        self.store.audit('inspectors.applying',f'{candidate} same-host processes; proxy interruption expected')
        self.workers.stop()
        try:
          self.workers.start(candidate)
          self.network.replicas=candidate
          self.network.start()
          self.store.set('inspectors',{'replicas':candidate})
        except Exception:
          self.workers.stop()
          self.network.replicas=previous['replicas']
          try:
            self.workers.start(previous['replicas'])
            self.network.start()
            self.store.audit('inspectors.rolled_back',f'Restored {previous["replicas"]} processes')
          except Exception:
            self.workers.stop()
            self.store.audit('inspectors.rollback_failed','Inspectors unavailable; inline traffic fails closed')
          raise
      result=self.workers.status()
      self.store.audit('inspectors.'+action,f'{result["state"]} · {len(result["replicas"])} processes')
      return result

  def apply(self,payload):
    with self.lock:
      candidate=Policy.model_validate(payload).model_dump()
      self.config(candidate)
      if candidate['version']!=self.policy()['version']:raise ValueError('Policy changed; refresh before applying')
      candidate['version']+=1
      engine=self.build_engine(candidate)
      self.store.save_policy(candidate)
      self.engine=engine
      return candidate

  async def start(self):
    self.destination=create_destination()
    self.destination_thread=threading.Thread(target=self.destination.serve_forever,daemon=True)
    self.destination_thread.start()
    replicas=(self.store.get('inspectors') or {'replicas':1})['replicas']
    self.network.replicas=replicas
    try:
      await asyncio.to_thread(self.workers.start,replicas)
      await asyncio.to_thread(self.network.start)
    except Exception:
      await self.stop()
      raise
    self.store.audit('installation.started','Envoy + gRPC inspector + synthetic HTTP destination')

  async def stop(self):
    try:
      await asyncio.to_thread(self.network.stop)
    finally:
      self.inspector_ready=False
      await asyncio.to_thread(self.workers.stop)
      if self.destination:
        await asyncio.to_thread(self.destination.shutdown)
        self.destination.server_close()

  def update_network(self,payload):
    # No traffic generator runs across a listener replacement.
    with self.network.lock:
      result=self.network.apply(payload)
      with self.lock:self.configure(self.policy())
      return result

  def network_status(self):
    result=self.network.status()
    result['inspectors']=self.workers.status()
    result['inspector_ready']=result['inspectors']['state']=='healthy'
    try:
      with httpx.Client(timeout=.5,trust_env=False) as c:
        response=c.get('http://127.0.0.1:18090/_demo/stats')
      result['destination_ready']=response.status_code==200
      result['destination_count']=response.json().get('count',0)
    except (httpx.HTTPError,ValueError):result['destination_ready']=False
    return result

  def signed_request(self,client,name,approval_id=None):
    case=CASES[name]
    arguments={'message':case['message']}
    if name=='response':arguments['demo_response_pii']=True
    body=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':case['tool'],'arguments':arguments}}).encode()
    port=self.network.current()['listen_port']
    request=client.build_request('POST',f'http://127.0.0.1:{port}/mcp',
      headers={'host':'tools.demo.test','content-type':'application/json'},content=body)
    message=HttpMessage('POST','tools.demo.test','/mcp',dict(request.headers),body)
    run_id=uuid4().hex
    identity={'source_id':'demo-decryptor','tenant_id':self.broker_tenant,'user_id':self.broker_user,
      'agent_id':case['agent'],'delegation_id':f'demo-{case["agent"]}',
      'task_id':f'task-{case["agent"]}','agent_instance_id':'synthetic-console',
      'scenario':name,'run_id':run_id}
    if approval_id:identity['approval_id']=approval_id
    request.headers['x-td-attestation']=sign_attestation(message,identity,self.key,nonce=uuid4().hex)
    return request,run_id

  def run(self,name,**kwargs):
    with self.network.lock:
      started=time.perf_counter()
      with httpx.Client(timeout=35,trust_env=False,follow_redirects=False) as client:
        request,run_id=self.signed_request(client,name,kwargs.get('approval_id'))
        try:response=client.send(request)
        except httpx.HTTPError:
          self.store.audit('proxy.transport_failed',f'{name} · proxy unavailable; no direct fallback')
          raise ValueError('Proxy connection failed. Check Connections / System.') from None
      event=None
      for _ in range(50):
        event=next((e for e in self.store.events() if e.get('transport',{}).get('run_id')==run_id),None)
        if event:break
        time.sleep(.02)
      if event is None:
        self.store.audit('proxy.evidence_missing',f'{name} · HTTP {response.status_code}')
        raise ValueError(f'Proxy HTTP {response.status_code}: inspection evidence is missing; no direct-engine fallback was used.')
      receipt=None
      try:
        body=response.json()
        raw=body.get('receipt')
        if isinstance(raw,dict) and self.destination and raw.get('id') in self.destination.receipts:
          receipt=self.destination.receipts[raw['id']]
      except ValueError:body={}
      event['transport'].update(http_status=response.status_code,round_trip_ms=round((time.perf_counter()-started)*1000,2),
        receipt=receipt,response_redacted='[REDACTED]' in response.text)
      self.store.update_event(event)
      self.store.audit('proxy.scenario_completed',f'{name} → HTTP {response.status_code} · {event["action"]} · event {event["id"]}')
      return event
