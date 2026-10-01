"""Signed, immutable policy snapshots: the only policy channel into the data plane.

The control plane holds the Ed25519 private key and publishes. The data plane
holds only the public key, verifies every snapshot and keeps the last known
good one when a newer file is missing, partial, unsigned or regressed.
"""
import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from asr_proxy.console.scenarios import Policy
from asr_proxy.inspection.pool import atomic_write
from .config import Deployment

FORMAT = 1
CURRENT = 'current.json'
MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024


class SnapshotError(Exception):
  """Stable reason codes only; never include snapshot content."""


@dataclass(frozen=True)
class Snapshot:
  revision: int
  connection_digest: str
  deployment: Deployment
  policy: dict
  created_at: str
  key_id: str


def canonical(value):
  return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def connection_digest(deployment):
  return hashlib.sha256(canonical(deployment.model_dump(mode='json', exclude_none=True))).hexdigest()


def key_id(public_key):
  raw = public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
  return hashlib.sha256(raw).hexdigest()[:16]


def ensure_signing_key(private_path, public_path):
  """Create the control-plane key once; always (re)export the public key."""
  private_path, public_path = Path(private_path), Path(public_path)
  if private_path.exists():
    if private_path.stat().st_mode & 0o077: raise ValueError('Policy signing key permissions must be 0600')
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey): raise ValueError('Policy signing key must be Ed25519')
  else:
    key = Ed25519PrivateKey.generate()
    private_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write(private_path, key.private_bytes(serialization.Encoding.PEM,
      serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
  public_path.parent.mkdir(parents=True, exist_ok=True)
  atomic_write(public_path, key.public_key().public_bytes(serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo), mode=0o644)
  return key


def load_public_key(path):
  try:
    key = serialization.load_pem_public_key(Path(path).read_bytes())
  except (OSError, ValueError):
    raise SnapshotError('policy_trust_key_unavailable') from None
  if not isinstance(key, Ed25519PublicKey): raise SnapshotError('policy_trust_key_unavailable')
  return key


class SnapshotPublisher:
  def __init__(self, directory, private_key):
    self.directory = Path(directory)
    self.key = private_key
    self.key_id = key_id(private_key.public_key())

  def _latest(self):
    revisions = [int(path.stem) for path in (self.directory / 'history').glob('*.json') if path.stem.isdigit()]
    return max(revisions, default=0)

  def _current_payload(self):
    try:
      return json.loads((self.directory / CURRENT).read_text())['payload']
    except (OSError, ValueError, KeyError, TypeError):
      return None

  def publish(self, deployment, policy):
    """Publish only when content changed. Returns the effective revision."""
    policy = Policy.model_validate(policy).model_dump()
    digest = connection_digest(deployment)
    current = self._current_payload()
    if current and current.get('connection_digest') == digest and current.get('policy') == policy:
      return current['revision']
    revision = self._latest() + 1
    payload = {'format': FORMAT, 'revision': revision, 'connection_digest': digest,
      'created_at': datetime.now(timezone.utc).isoformat(), 'key_id': self.key_id,
      'deployment': deployment.model_dump(mode='json', exclude_none=True), 'policy': policy}
    envelope = canonical({'payload': payload,
      'signature': base64.b64encode(self.key.sign(canonical(payload))).decode('ascii')})
    if len(envelope) > MAX_SNAPSHOT_BYTES: raise ValueError('Policy snapshot is too large.')
    (self.directory / 'history').mkdir(parents=True, exist_ok=True, mode=0o755)
    # History first, pointer last: a crash in between leaves the previous current.json intact.
    atomic_write(self.directory / 'history' / f'{revision:010d}.json', envelope, mode=0o644)
    atomic_write(self.directory / CURRENT, envelope, mode=0o644)
    return revision


class SnapshotLoader:
  def __init__(self, directory, public_key_path):
    self.directory = Path(directory)
    self.public_key_path = Path(public_key_path)

  def fingerprint(self):
    """Cheap change detector for polling; None when no snapshot exists."""
    try:
      status = os.stat(self.directory / CURRENT)
    except FileNotFoundError:
      return None
    return (status.st_ino, status.st_size, status.st_mtime_ns)

  def read(self):
    key = load_public_key(self.public_key_path)
    try:
      with open(self.directory / CURRENT, 'rb') as handle:
        raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
    except FileNotFoundError:
      raise SnapshotError('policy_snapshot_missing') from None
    except OSError:
      raise SnapshotError('policy_snapshot_unreadable') from None
    if len(raw) > MAX_SNAPSHOT_BYTES: raise SnapshotError('policy_snapshot_too_large')
    try:
      envelope = json.loads(raw)
      payload = envelope['payload']
      signature = base64.b64decode(envelope['signature'], validate=True)
    except (ValueError, KeyError, TypeError):
      raise SnapshotError('policy_snapshot_malformed') from None
    if not isinstance(payload, dict): raise SnapshotError('policy_snapshot_malformed')
    try:
      key.verify(signature, canonical(payload))
    except InvalidSignature:
      raise SnapshotError('policy_snapshot_signature_invalid') from None
    if payload.get('format') != FORMAT: raise SnapshotError('policy_snapshot_format_unsupported')
    try:
      deployment = Deployment.model_validate(payload['deployment'])
      policy = Policy.model_validate(payload['policy']).model_dump()
      revision = payload['revision']
      if not isinstance(revision, int) or revision < 1: raise ValueError()
    except (ValueError, KeyError, TypeError):
      raise SnapshotError('policy_snapshot_invalid') from None
    if payload.get('connection_digest') != connection_digest(deployment):
      raise SnapshotError('policy_snapshot_invalid')
    return Snapshot(revision, payload['connection_digest'], deployment, policy,
      str(payload.get('created_at', '')), key_id(key))
