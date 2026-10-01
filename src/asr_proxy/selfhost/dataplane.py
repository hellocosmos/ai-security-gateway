"""Self-hosted data plane: inspects with the last known good signed snapshot.

This runtime never opens console.sqlite. Policy arrives only through signed
snapshots, and evidence leaves only through the append-only spool.
"""
import asyncio
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from asr_proxy.inspection.contracts import InspectionError
from asr_proxy.inspection.pii import PresidioScanner
from .latency import LatencyMetrics
from .runtime import build_engine, inspection_config, read_signing_key
from .snapshot import SnapshotError
from .spool import EventSpool


def now():
  return datetime.now(timezone.utc).isoformat()


def log(event, **fields):
  # Stable codes only: never log policy content, request data or credentials.
  print(json.dumps({'ts': now(), 'event': event, **fields}, separators=(',', ':')), file=sys.stderr, flush=True)


class DataplaneRuntime:
  integrated = False

  def __init__(self, state, loader, *, writer='gateway', scanner=None, proxy_host='envoy',
               expected_connection=None):
    self.directory = Path(state)
    # Inspector workers pin the gateway's connection so a respawn never mixes route mappings.
    self.expected_connection = expected_connection
    self.loader = loader
    self.key = read_signing_key(self.directory)
    self.scanner = scanner or PresidioScanner()
    self.lock = RLock()
    self.spool = EventSpool(self.directory / 'dataplane' / 'events', writer)
    self.proxy_host = proxy_host
    self.snapshot = None
    self.engine = None
    self.policy = None
    self.fingerprint = None
    self.loaded_at = None
    self.last_rejection = None
    self.restart_required = False
    self.inspector_ready = False
    self.gateway_outcomes = {}
    self.latency = LatencyMetrics()
    self.worker_revisions = None
    self.refresh()

  @property
  def deployment(self):
    snapshot = self.snapshot
    return snapshot.deployment if snapshot else None

  def _reject(self, reason, fingerprint):
    with self.lock:
      self.fingerprint = fingerprint
      repeated = self.last_rejection and self.last_rejection['reason'] == reason
      self.last_rejection = {'reason': reason, 'at': now(),
        'kept_revision': self.snapshot.revision if self.snapshot else None}
    if not repeated:
      log('policy.snapshot_rejected', reason=reason, kept_revision=self.last_rejection['kept_revision'])
    return False

  def refresh(self, *, force=False):
    """Load a newer valid snapshot. Any failure keeps the last known good engine."""
    fingerprint = self.loader.fingerprint()
    with self.lock:
      if not force and self.snapshot is not None and fingerprint == self.fingerprint:
        return False
      if not force and self.snapshot is None and fingerprint is not None and fingerprint == self.fingerprint:
        return False
      current = self.snapshot
    try:
      snapshot = self.loader.read()
    except SnapshotError as error:
      return self._reject(str(error), fingerprint)
    if self.expected_connection and snapshot.connection_digest != self.expected_connection:
      self.restart_required = True
      return self._reject('connection_changed_restart_required', fingerprint)
    if current is not None:
      if snapshot.revision == current.revision:
        with self.lock: self.fingerprint = fingerprint
        return False
      if snapshot.revision < current.revision:
        return self._reject('policy_snapshot_revision_regressed', fingerprint)
      if snapshot.connection_digest != current.connection_digest:
        self.restart_required = True
        return self._reject('connection_changed_restart_required', fingerprint)
    try:
      engine = build_engine(inspection_config(snapshot.deployment, snapshot.policy, self.directory),
        self.key, self.scanner)
    except (ValueError, OSError):
      return self._reject('policy_snapshot_invalid', fingerprint)
    with self.lock:
      if current is None:
        self.latency = LatencyMetrics(inspector_processes=snapshot.deployment.inspector_replicas)
      # New streams take the new engine; in-flight streams keep the one they started with.
      self.snapshot, self.engine, self.policy = snapshot, engine, snapshot.policy
      self.fingerprint, self.loaded_at = fingerprint, now()
    log('policy.snapshot_loaded', revision=snapshot.revision, key_id=snapshot.key_id)
    return True

  def stream_snapshot(self):
    with self.lock:
      if self.engine is None: raise InspectionError('policy_snapshot_unavailable')
      return self.engine, self.policy

  def record_event(self, event):
    try:
      self.spool.append(event)
    except OSError:
      log('evidence.spool_write_failed', failures=self.spool.failures)
      # Inline enforcement without evidence breaks the audit contract: fail this stream closed.
      if event.get('mode') != 'mirror': raise
    return event

  def admission(self):
    """None when a new request may enter the inspection path, else a stable reason."""
    with self.lock:
      if self.engine is None: return 'policy_snapshot_unavailable'
      mode = self.policy['mode']
    if not self.inspector_ready: return 'inspector_unavailable'
    if mode == 'inline' and not self.spool.healthy: return 'evidence_unavailable'
    return None

  def observe_gateway(self, phase, status):
    # Finite dimensions only: never retain request paths, bodies or credentials.
    with self.lock:
      key = f'{phase}:{status}'
      record = self.gateway_outcomes.setdefault(key, {'phase': phase, 'http_status': status, 'count': 0})
      record['count'] += 1
      record['last_seen'] = now()

  def proxy_ready(self):
    try:
      with socket.create_connection((self.proxy_host, 18082), timeout=.3): return True
    except OSError:
      return False

  def status(self):
    reason = self.admission()
    with self.lock:
      snapshot = self.snapshot
      value = {'ready': reason is None, 'admission': reason or 'open',
        'inspector_ready': self.inspector_ready,
        'snapshot': {'revision': snapshot.revision, 'key_id': snapshot.key_id,
          'connection': snapshot.connection_digest[:12], 'created_at': snapshot.created_at,
          'loaded_at': self.loaded_at, 'mode': self.policy['mode']} if snapshot else None,
        'last_rejection': self.last_rejection, 'restart_required': self.restart_required,
        'evidence': {'healthy': self.spool.healthy, 'failures': self.spool.failures},
        'gateway_outcomes': list(self.gateway_outcomes.values())}
    # Applied = every process inspecting traffic has loaded at least this revision.
    applied = snapshot.revision if snapshot else None
    if applied is not None and self.worker_revisions is not None:
      workers = self.worker_revisions()
      applied = None if None in workers else min([applied, *workers])
    value['applied_revision'] = applied
    value['latency'] = self.latency.snapshot()
    value['proxy_ready'] = self.proxy_ready()
    return value


def create_status_app(runtime):
  """Internal-only readiness and status for the control plane and Compose healthchecks."""
  from fastapi import FastAPI
  from fastapi.responses import JSONResponse
  app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

  @app.get('/_trapdefense/ready')
  def ready():
    reason = runtime.admission()
    return JSONResponse({'ready': reason is None, 'admission': reason or 'open'},
      status_code=200 if reason is None else 503)

  @app.get('/_trapdefense/status')
  def status():
    return runtime.status()

  return app


async def maintain(runtime, *, interval=.25, probe_every=20):
  """Poll for snapshots and re-check evidence storage; never stops on errors."""
  tick = 0
  while True:
    try:
      await asyncio.to_thread(runtime.refresh)
      if not runtime.spool.healthy or tick % probe_every == 0:
        await asyncio.to_thread(runtime.spool.probe)
    except Exception as error:  # Keep the last known good state; report only the type.
      log('dataplane.maintenance_failed', error=type(error).__name__)
    tick += 1
    await asyncio.sleep(interval)
