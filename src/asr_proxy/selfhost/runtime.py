"""Persistent console policies and inspection without host Docker/process control."""
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


class SelfhostRuntime(Runtime):
  integrated = False  # Do not expose demo host-network or worker-management APIs.

  def __init__(self, directory, deployment, *, seed=False):
    self.deployment = deployment
    self.broker_tenant = deployment.access_broker.tenant_id or ''
    self.store = Store(directory, require_existing=True)
    self.lock = RLock()
    key_path=self.store.directory/'attestation.key'
    if key_path.stat().st_mode & 0o077:raise ValueError('Signing key permissions must be 0600')
    self.key = key_path.read_bytes()
    self.scanner = PresidioScanner()
    if self.store.get('policy') is None:
      entries = list(deployment.entries())
      self.store.set('policy',Policy(rules={key:rule.effect for key,_,rule in entries},
        pii_rules={key:rule.pii_action or 'inherit' for key,_,rule in entries}).model_dump())
    self.configure(self.policy())
    self.inspector_ready = False
    self.gateway_outcomes = {}
    from .latency import LatencyMetrics
    self.latency = LatencyMetrics(inspector_processes=deployment.inspector_replicas)

  def config(self, policy):
    entries = list(self.deployment.entries())
    keys = {key for key,_,_ in entries}
    if set(policy['rules']) != keys or set(policy['pii_rules']) != keys:
      raise ValueError('Route mappings changed. Migrate the saved policy explicitly before startup.')
    routes = [route.model_copy(deep=True) for route in self.deployment.routes]
    for index, route in enumerate(routes):
      rules = route.tools if route.protocol=='mcp' else {route.tool:route.rule}
      for name, rule in rules.items():
        key = f'{index}:{name}'
        rule.effect = policy['rules'][key]
        rule.pii_action = None if policy['pii_rules'][key]=='inherit' else policy['pii_rules'][key]
    credential_headers=([self.deployment.target_auth.header]
      if self.deployment.target_auth.mode=='static_api_key' else [])
    return InspectionConfig(access_broker_enabled=self.deployment.access_broker.enabled,
      trusted_sources=['selfhost-adapter'],routes=routes,
      credential_headers=credential_headers,
      max_body_bytes=self.deployment.max_body_bytes,pii_action=policy['pii_action'],
      nonce_db=str(self.store.directory/'nonces.sqlite'),
      broker_store=str(self.store.directory/'broker.json'),
      audit_path=str(self.store.directory/'inspection.jsonl'))

  def build_engine(self,policy):
    config=self.config(policy)
    fields=('tenant_id','agent_id') if config.access_broker_enabled else ('source_id',)
    verifier=AttestationVerifier(self.key,config.nonce_db,required_fields=fields)
    self.broker=load_authorizer(config)
    return InspectionEngine(config,self.scanner,verifier,self.broker)

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
