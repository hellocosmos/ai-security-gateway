"""Persistent console policies and inspection without host Docker/process control."""
from pathlib import Path
from threading import RLock
import socket
from asr_proxy.console.runtime import Runtime
from asr_proxy.console.store import Store
from asr_proxy.console.scenarios import Policy
from asr_proxy.inspection.contracts import InspectionConfig
from asr_proxy.inspection.authorization import load_authorizer
from asr_proxy.inspection.engine import InspectionEngine
from asr_proxy.inspection.identity import IDENTITY_FIELDS, AttestationVerifier
from asr_proxy.inspection.pii import PresidioScanner


def inspection_config(deployment, policy, directory):
  """Compile one deployment and saved policy into the engine contract (control and data plane)."""
  entries = list(deployment.entries())
  keys = {key for key,_,_ in entries}
  if set(policy['rules']) != keys or set(policy['pii_rules']) != keys:
    raise ValueError('Route mappings changed. Migrate the saved policy explicitly before startup.')
  routes = [route.model_copy(deep=True) for route in deployment.routes]
  for index, route in enumerate(routes):
    rules = route.tools if route.protocol=='mcp' else {route.tool:route.rule}
    for name, rule in rules.items():
      key = f'{index}:{name}'
      rule.effect = policy['rules'][key]
      rule.pii_action = None if policy['pii_rules'][key]=='inherit' else policy['pii_rules'][key]
  credential_headers=([deployment.target_auth.header]
    if deployment.target_auth.mode=='static_api_key' else [])
  directory=Path(directory)
  return InspectionConfig(access_broker_enabled=deployment.access_broker.enabled,
    trusted_sources=['selfhost-adapter'],routes=routes,
    credential_headers=credential_headers,
    max_body_bytes=deployment.max_body_bytes,pii_action=policy['pii_action'],
    nonce_db=str(directory/'nonces.sqlite'),
    broker_store=str(directory/'broker.json'),
    audit_path=str(directory/'inspection.jsonl'))


def build_engine(config, key, scanner):
  fields=('tenant_id','agent_id') if config.access_broker_enabled else ('source_id',)
  verifier=AttestationVerifier(key,config.nonce_db,required_fields=fields)
  return InspectionEngine(config,scanner,verifier,load_authorizer(config))


def seed_policy(store, deployment):
  if store.get('policy') is None:
    entries = list(deployment.entries())
    store.set('policy',Policy(rules={key:rule.effect for key,_,rule in entries},
      pii_rules={key:rule.pii_action or 'inherit' for key,_,rule in entries}).model_dump())
  return Policy.model_validate(store.get('policy')).model_dump()


def read_signing_key(directory):
  key_path=Path(directory)/'attestation.key'
  if key_path.stat().st_mode & 0o077:raise ValueError('Signing key permissions must be 0600')
  return key_path.read_bytes()


class SelfhostRuntime(Runtime):
  integrated = False  # Do not expose demo host-network or worker-management APIs.

  def __init__(self, directory, deployment, *, seed=False, publisher=None, dataplane_url=None):
    self.deployment = deployment
    self.publisher = publisher
    self.dataplane_url = dataplane_url
    self.broker_tenant = deployment.access_broker.tenant_id or ''
    self.store = Store(directory, require_existing=True)
    self.lock = RLock()
    self.key = read_signing_key(self.store.directory)
    self.scanner = PresidioScanner()
    seed_policy(self.store, deployment)
    self.configure(self.policy())
    self.inspector_ready = False
    self.gateway_outcomes = {}
    from .latency import LatencyMetrics
    self.latency = LatencyMetrics(inspector_processes=deployment.inspector_replicas)

  def config(self, policy):
    return inspection_config(self.deployment, policy, self.store.directory)

  def build_engine(self,policy):
    engine=build_engine(self.config(policy),self.key,self.scanner)
    self.broker=engine.broker
    return engine

  def apply(self,payload):
    candidate=super().apply(payload)
    revision=self.publish()
    # Preserve apply-then-enforce: answer after the data plane acknowledges the revision.
    if revision and self.dataplane_url and not self.wait_applied(revision):
      self.store.audit('policy.dataplane_pending',f'r{revision} not yet acknowledged by the data plane')
    return candidate

  def wait_applied(self,revision,timeout=5.0):
    import time
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
      if (self.dataplane_status().get('applied_revision') or 0)>=revision:return True
      time.sleep(.1)
    return False

  def events(self):
    # Read-your-evidence: drain the spool before answering so a just-finished request is visible.
    self.ingest_events()
    return self.store.events()

  def publish(self):
    """Control plane only: republish the signed data-plane snapshot when content changed."""
    if self.publisher is None:return None
    with self.lock:return self.publisher.publish(self.deployment,self.policy())

  def ingest_events(self):
    from .spool import read_pending
    with self.lock:
      cursor=self.store.get('event_spool_cursor',{})
      events,cursor,drained=read_pending(self.store.directory/'dataplane'/'events',cursor)
      if not events and cursor==self.store.get('event_spool_cursor',{}):return 0
      self.store.ingest_events(events,cursor)
    for path in drained:path.unlink(missing_ok=True)
    return len(events)

  def observed(self,status=None):
    """Gateway outcomes and latency are owned by the data plane process."""
    if self.dataplane_url:
      status=status if status is not None else self.dataplane_status()
      return status.get('gateway_outcomes',[]),status.get('latency'),'dataplane'
    return list(self.gateway_outcomes.values()),self.latency.snapshot(),'current_process'

  def dataplane_summary(self,status):
    """Operator-facing data-plane state: no policy content, request data or credentials."""
    if status.get('reachable') is False:return {'reachable':False}
    keys=('ready','admission','snapshot','applied_revision','last_rejection','restart_required','evidence')
    return {'reachable':True,**{key:status.get(key) for key in keys}}

  def dataplane_status(self):
    import httpx
    try:
      with httpx.Client(timeout=.5,trust_env=False) as client:
        response=client.get(self.dataplane_url+'/_trapdefense/status')
      value=response.json()
      if response.status_code==200 and isinstance(value,dict):return value
    except (httpx.HTTPError,ValueError):pass
    return {'reachable':False}

  def broker_resources(self,tools):
    if self.deployment.llm:return list(self.deployment.llm.models)
    return super().broker_resources(tools)

  def broker_tool_map(self):
    if self.deployment.llm:
      return {name:(rule.action,", ".join(self.deployment.llm.models))
        for _,name,rule in self.deployment.entries()}
    # Dynamic resource pointers cannot be safely converted into registry scope
    # from the console. Operators can manage fixed-resource routes here and use
    # the broker API/store integration for resource instances discovered later.
    return {name:(rule.action,rule.resource) for _,name,rule in self.deployment.entries()
      if rule.resource is not None}

  def configure(self, policy):
    self.engine = self.build_engine(policy)
    self.engine_revision = policy['version']

  def stream_snapshot(self):
    with self.lock:
      policy = self.policy()
      if self.engine_revision != policy['version']:self.configure(policy)
      return self.engine, policy

  def network_status(self):
    if self.dataplane_url:
      status=self.dataplane_status()
      return {'inspector_ready':bool(status.get('inspector_ready')),'proxy_ready':bool(status.get('proxy_ready')),
              'destination_ready':None,'probe':'listener_only','dataplane':{
                'reachable':status.get('reachable',True),'ready':bool(status.get('ready')),
                'snapshot':status.get('snapshot'),'evidence':status.get('evidence')}}
    try:
      with socket.create_connection(('envoy',18082),timeout=.3):proxy=True
    except OSError:proxy=False
    return {'inspector_ready':self.inspector_ready,'proxy_ready':proxy,
            'destination_ready':None,'probe':'listener_only'}

  def observe_gateway(self, phase, status):
    from datetime import datetime, timezone
    # Finite dimensions only: never retain request paths, bodies or credentials.
    with self.lock:
      key = f'{phase}:{status}'
      record = self.gateway_outcomes.setdefault(key, {'phase': phase, 'http_status': status, 'count': 0})
      record['count'] += 1
      record['last_seen'] = datetime.now(timezone.utc).isoformat()
