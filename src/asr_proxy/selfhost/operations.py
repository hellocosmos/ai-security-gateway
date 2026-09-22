"""Staged operator settings and isolated diagnostics; never controls Docker."""
import json
import secrets
import tempfile
import time
from asr_proxy.inspection.budget import INSPECTION_DEADLINE
from dataclasses import replace
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from asr_proxy.console.scenarios import Policy
from asr_proxy.inspection.contracts import HttpMessage
from asr_proxy.inspection.engine import InspectionEngine
from asr_proxy.inspection.identity import AttestationVerifier, sign_attestation
from asr_proxy.inspection.pool import atomic_write
from .config import Deployment

KEY = 'operations.config'


class SettingsInput(BaseModel):
  model_config = ConfigDict(extra='forbid')
  version: int = Field(ge=0)
  config: dict
  target_secret: str | None = Field(default=None, min_length=1, max_length=4096, repr=False)


class RestoreInput(BaseModel):
  model_config = ConfigDict(extra='forbid')
  version: int = Field(ge=0)
  revision: int = Field(ge=1)


class PreviewInput(BaseModel):
  model_config = ConfigDict(extra='forbid')
  route: int = Field(ge=0)
  body: dict
  policy: Policy


def state(store):
  return store.get(KEY) or {'version': 0, 'pending': None, 'active': None, 'history': []}


def active_config(store, fallback):
  saved = state(store)['active']
  if not saved: return fallback
  config = dict(saved['config'])
  for key in ('console_origin', 'gateway_auth', 'access_broker'):
    value = getattr(fallback, key)
    config[key] = value.model_dump() if hasattr(value, 'model_dump') else value
  return Deployment.model_validate(config)


class Operations:
  def __init__(self, runtime):
    self.runtime = runtime
    self.store = runtime.store

  def snapshot(self):
    with self.runtime.lock:
      saved = state(self.store)
      return {'version': saved['version'], 'active': self.runtime.deployment.model_dump(exclude_none=True),
              'pending': saved['pending'],
              'history': [{'revision': h['revision']} for h in saved['history']],
              'restart_required': saved['pending'] is not None,
              'recent_gateway_outcomes': list(self.runtime.gateway_outcomes.values()),
              'outcome_scope': 'current_process', 'latency': self.runtime.latency.snapshot()}

  def candidate(self, payload):
    try:
      candidate = Deployment.model_validate(payload.config)
      # Console origin and gateway/IdP/broker trust changes remain explicit file operations.
      current = self.runtime.deployment
      if any(getattr(candidate, key) != getattr(current, key) for key in
             ('console_origin', 'gateway_auth', 'access_broker')):
        raise ValueError()
      if payload.target_secret is not None:
        if not candidate.target_auth.secret_file or any(c.isspace() for c in payload.target_secret):
          raise ValueError()
      elif candidate.target_auth.secret_file:
        allowed = {current.target_auth.secret_file}
        saved = state(self.store)
        for item in [saved['pending'], saved['active'], *saved['history']]:
          if item: allowed.add(item['config']['target_auth'].get('secret_file'))
        if candidate.target_auth.secret_file not in allowed: raise ValueError()
      return candidate
    except (ValueError, KeyError, TypeError):
      raise ValueError('Invalid connection settings. Check mappings, authentication and credential selection.') from None

  def stage(self, payload):
    with self.runtime.lock:
      saved = state(self.store)
      if payload.version != saved['version']: raise ValueError('Settings changed. Refresh before saving.')
      candidate = self.candidate(payload)
      if payload.target_secret is not None:
        name = self.store.directory / ('target-' + secrets.token_hex(16) + '.key')
        atomic_write(name, payload.target_secret.encode())
        candidate.target_auth.secret_file = str(name)
      # Keep a bounded rollback history. Secrets are never copied into SQLite or responses.
      revision = saved['version'] + 1
      previous = saved['pending'] or saved['active'] or {
        'revision': revision, 'config': self.runtime.deployment.model_dump(exclude_none=True), 'policy': self.runtime.policy()}
      if saved['pending'] is None and saved['active']:
        previous = {**previous, 'policy': self.runtime.policy()}
      saved['history'] = [*saved['history'], previous][-10:]
      saved.update(version=revision, pending={'revision': revision + 1,
                   'config': candidate.model_dump(exclude_none=True)})
      self.store.set(KEY, saved)
      self.store.audit('connection.staged', 'Restart and explicit activation required')
      return self.snapshot()

  def restore(self, payload):
    with self.runtime.lock:
      saved = state(self.store)
      if payload.version != saved['version']: raise ValueError('Settings changed. Refresh before saving.')
      item = next((h for h in reversed(saved['history']) if h['revision'] == payload.revision), None)
      if not item: raise ValueError('Saved revision not found.')
      self.stage(SettingsInput(version=payload.version, config=item['config']))
      saved = state(self.store)
      if item.get('policy'):
        saved['pending']['policy'] = item['policy']
        self.store.set(KEY, saved)
      return self.snapshot()

  def diagnose(self):
    # The app intentionally cannot reach the isolated egress network directly.
    # Never add a bypass probe or interpret network isolation as destination failure.
    network = self.runtime.network_status()
    status = ('inspector_unavailable' if not network['inspector_ready'] else
              'proxy_unavailable' if not network['proxy_ready'] else 'listeners_ready')
    with self.runtime.lock:
      return {'scope': 'inspection_listeners_and_observed_requests', 'status': status,
              'authentication': 'not_tested', 'destination': 'not_probed',
              'network': network, 'recent_gateway_outcomes': list(self.runtime.gateway_outcomes.values()),
              'outcome_scope': 'current_process', 'latency': self.runtime.latency.snapshot()}

  def preview(self, payload):
    with self.runtime.lock:
      config = self.runtime.config(payload.policy.model_dump())
      if payload.route >= len(config.routes): raise ValueError('Select a configured route.')
      route = config.routes[payload.route]
      raw = json.dumps(payload.body).encode()
      if len(raw) > 8192: raise ValueError('Preview body must be at most 8 KiB.')
      # Never authorize agents, create approvals, or touch live replay/audit stores.
      with tempfile.TemporaryDirectory(prefix='td-preview-') as directory:
        config = config.model_copy(update={'access_broker_enabled': False,
          'nonce_db': directory + '/nonces.sqlite', 'audit_path': directory + '/audit.jsonl'})
        verifier = AttestationVerifier(self.runtime.key, config.nonce_db, required_fields=('source_id',))
        engine = InspectionEngine(config, self.runtime.scanner, verifier, None)
        message = HttpMessage(route.method, route.authority, route.path,
          {'content-type': 'application/json', **route.required_headers}, raw)
        headers = {'x-td-attestation': sign_attestation(message, {'source_id': 'selfhost-adapter'}, self.runtime.key, nonce=secrets.token_hex(16))}
        token = INSPECTION_DEADLINE.set(time.monotonic() + 1)
        try: verdict = engine.inspect_request(replace(message, headers={**message.headers, **headers}), mode='inline')
        finally: INSPECTION_DEADLINE.reset(token)
        return {'scope': 'local_policy_only', 'decision': verdict.action, 'reason': verdict.reason,
                'entities': verdict.entities, 'body_changed': verdict.body is not None,
                'agent_authorization': 'not_tested', 'upstream_called': False}


def activate(store, fallback):
  """Called only with the stack stopped, under an exclusive process lock."""
  saved = state(store)
  if not saved['pending']: raise ValueError('No staged connection settings.')
  config = Deployment.model_validate(saved['pending']['config'])
  if config.target_auth.secret_file:
    from .main import secret
    secret(config.target_auth.secret_file)
  old = active_config(store, fallback)
  policy = store.get('policy')
  if saved['pending'].get('policy'):
    policy = Policy.model_validate(saved['pending']['policy']).model_dump()
    policy['version'] = (store.get('policy') or {}).get('version', 0) + 1
  elif config.routes != old.routes:
    entries = list(config.entries())
    policy = Policy(version=(policy or {}).get('version', 0) + 1,
      mode=(policy or {}).get('mode', 'inline'),
      pii_action=(policy or {}).get('pii_action', 'redact'),
      rules={key: rule.effect for key, _, rule in entries},
      pii_rules={key: rule.pii_action or 'inherit' for key, _, rule in entries}).model_dump()
  saved['active'], saved['pending'] = saved['pending'], None
  saved['version'] += 1
  with store.connect() as db:
    for key, value in [(KEY, saved), ('policy', policy)]:
      if value is not None:
        db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', (key, json.dumps(value)))
  store.audit('connection.activated', 'Staged connection activated while service stopped')
  return config
