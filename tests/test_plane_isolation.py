"""Data-plane inspection must not depend on control-plane console storage."""
import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from asr_proxy.console.dataplane import StreamInspection
from asr_proxy.inspection.contracts import InspectionError
from asr_proxy.selfhost import snapshot as snapshots
from asr_proxy.selfhost.config import Deployment, load
from asr_proxy.selfhost.dataplane import DataplaneRuntime
from asr_proxy.selfhost.main import initialize, plane_paths, publisher
from asr_proxy.selfhost.runtime import SelfhostRuntime
from asr_proxy.selfhost.snapshot import SnapshotLoader, SnapshotPublisher, ensure_signing_key

CONFIG=Path(__file__).parents[1]/'deploy/selfhost/deployment.yaml'


@pytest.fixture
def state(tmp_path):
  state=tmp_path/'state'
  initialize(state,tmp_path/'generated',load(CONFIG),'synthetic-password-047')
  return state


def dataplane(state,**kwargs):
  paths=plane_paths(state)
  return DataplaneRuntime(state,SnapshotLoader(paths.policy,paths.trust),**kwargs)


def control(state):
  return SelfhostRuntime(state,load(CONFIG),publisher=publisher(plane_paths(state)))


def current(state):
  return plane_paths(state).policy/'current.json'


def test_console_database_lock_does_not_delay_new_streams(state):
  runtime=dataplane(state)
  holder=sqlite3.connect(state/'console.sqlite')
  holder.execute('BEGIN EXCLUSIVE')
  try:
    started=time.monotonic()
    worker=threading.Thread(target=lambda:StreamInspection(runtime),daemon=True)
    worker.start()
    worker.join(1)
    assert not worker.is_alive() and time.monotonic()-started<1
  finally:
    holder.rollback();holder.close()
    worker.join(15)


def test_damaged_console_database_does_not_stop_new_streams(state):
  runtime=dataplane(state)
  (state/'console.sqlite').write_bytes(b'not a database'*64)
  inspection=StreamInspection(runtime)
  assert inspection.policy['mode'] in ('inline','mirror')


def test_dataplane_never_opens_console_database(state):
  (state/'console.sqlite').unlink()
  runtime=dataplane(state)
  assert runtime.snapshot.revision==1 and runtime.engine is not None
  assert not (state/'console.sqlite').exists()


def test_missing_snapshot_keeps_dataplane_closed(state):
  current(state).unlink()
  runtime=dataplane(state)
  runtime.inspector_ready=True
  assert runtime.admission()=='policy_snapshot_unavailable'
  with pytest.raises(InspectionError,match='policy_snapshot_unavailable'):runtime.stream_snapshot()
  assert runtime.status()['ready'] is False


def policy_update(runtime,rule='block'):
  policy=runtime.policy();policy['rules']['0:notes.read']=rule
  return runtime.apply(policy)


def test_policy_apply_hot_swaps_new_streams_only(state):
  plane=dataplane(state)
  before=StreamInspection(plane)
  applied=policy_update(control(state))
  assert plane.refresh()
  after=StreamInspection(plane)
  assert before.policy['rules']['0:notes.read']=='allow' and before.engine is not after.engine
  assert after.policy['version']==applied['version'] and after.policy['rules']['0:notes.read']=='block'
  assert plane.snapshot.revision==2


def tamper(state,change):
  path=current(state)
  envelope=json.loads(path.read_text())
  change(envelope)
  path.write_text(json.dumps(envelope))


@pytest.mark.parametrize('case,reason',[
  ('signature','policy_snapshot_signature_invalid'),
  ('partial','policy_snapshot_malformed'),
  ('garbage_signature','policy_snapshot_malformed'),
  ('format','policy_snapshot_signature_invalid'),
])
def test_invalid_snapshot_keeps_last_known_good(state,case,reason):
  plane=dataplane(state)
  policy_update(control(state))
  if case=='signature':
    tamper(state,lambda e:e['payload']['policy']['rules'].update({'0:notes.read':'allow'}))
  elif case=='partial':
    raw=current(state).read_bytes();current(state).write_bytes(raw[:len(raw)//2])
  elif case=='garbage_signature':
    tamper(state,lambda e:e.update(signature='%%%'))
  else:
    tamper(state,lambda e:e['payload'].update(format=2))
  assert plane.refresh() is False
  assert plane.snapshot.revision==1 and plane.policy['rules']['0:notes.read']=='allow'
  assert plane.last_rejection['reason']==reason and plane.last_rejection['kept_revision']==1


def test_snapshot_signed_by_another_key_is_rejected(state,tmp_path):
  plane=dataplane(state)
  rogue=SnapshotPublisher(plane_paths(state).policy,ensure_signing_key(tmp_path/'rogue.key',tmp_path/'rogue.pub'))
  config=load(CONFIG);policy=control(state).policy();policy['rules']['0:notes.read']='block'
  rogue.publish(config,policy)
  assert plane.refresh() is False and plane.last_rejection['reason']=='policy_snapshot_signature_invalid'
  assert plane.policy['rules']['0:notes.read']=='allow'


def test_revision_regression_is_rejected(state):
  plane=dataplane(state)
  first=current(state).read_bytes()
  policy_update(control(state))
  assert plane.refresh() and plane.snapshot.revision==2
  current(state).write_bytes(first)
  assert plane.refresh() is False
  assert plane.snapshot.revision==2 and plane.last_rejection['reason']=='policy_snapshot_revision_regressed'


def test_connection_change_requires_restart(state):
  plane=dataplane(state)
  data=load(CONFIG).model_dump(mode='json',exclude_none=True);data['max_body_bytes']=4096
  runtime=SelfhostRuntime(state,Deployment.model_validate(data),publisher=publisher(plane_paths(state)))
  runtime.publish()
  assert plane.refresh() is False
  assert plane.restart_required and plane.last_rejection['reason']=='connection_changed_restart_required'
  assert plane.deployment.max_body_bytes!=4096
  restarted=dataplane(state)
  assert restarted.deployment.max_body_bytes==4096 and not restarted.restart_required


def test_interrupted_publish_keeps_previous_pointer(state,monkeypatch):
  plane=dataplane(state)
  original=snapshots.atomic_write
  def crash(path,*args,**kwargs):
    if path.name=='current.json':raise OSError('simulated crash before pointer swap')
    return original(path,*args,**kwargs)
  monkeypatch.setattr(snapshots,'atomic_write',crash)
  with pytest.raises(OSError):policy_update(control(state))
  monkeypatch.undo()
  assert plane.refresh(force=True) is False and plane.snapshot.revision==1
  # The next publish still advances past the orphaned history entry.
  runtime=control(state);runtime.publish()
  assert plane.refresh() and plane.snapshot.revision==3


def test_publish_is_idempotent_for_unchanged_content(state):
  runtime=control(state)
  assert runtime.publish()==1 and runtime.publish()==1


def failing_fsync(*args):
  raise OSError(28,'No space left on device')


def test_inline_evidence_failure_fails_stream_and_closes_admission(state,monkeypatch):
  plane=dataplane(state);plane.inspector_ready=True
  assert plane.admission() is None
  monkeypatch.setattr('asr_proxy.selfhost.spool.os.fsync',failing_fsync)
  with pytest.raises(OSError):plane.record_event({'mode':'inline','action':'allow'})
  assert plane.admission()=='evidence_unavailable'
  assert plane.spool.probe() is False
  monkeypatch.undo()
  assert plane.spool.probe() is True and plane.admission() is None


def test_mirror_evidence_failure_does_not_fail_observation(state,monkeypatch):
  plane=dataplane(state)
  policy=control(state);value=policy.policy();value['mode']='mirror';policy.apply(value)
  plane.refresh();plane.inspector_ready=True
  monkeypatch.setattr('asr_proxy.selfhost.spool.os.fsync',failing_fsync)
  plane.record_event({'mode':'mirror','action':'allow'})
  assert plane.admission() is None


def test_spool_ingest_survives_rotation_partial_lines_and_restart(state):
  plane=dataplane(state)
  plane.spool.max_bytes=160
  for index in range(12):plane.record_event({'mode':'inline','action':'allow','index':index})
  writer=plane.spool.directory
  assert len(list(writer.glob('events-*.jsonl')))>=2
  with open(writer/'events.jsonl','ab') as handle:handle.write(b'{"partial":')
  runtime=control(state)
  assert runtime.ingest_events()==12
  assert sorted(event['index'] for event in runtime.store.events())==list(range(12))
  assert not list(writer.glob('events-*.jsonl'))
  assert control(state).ingest_events()==0
  with open(writer/'events.jsonl','ab') as handle:handle.write(b'"done"}\n')
  assert control(state).ingest_events()==1
  assert len(runtime.store.events())==13


def test_multiple_writers_are_ingested_independently(state):
  first=dataplane(state,writer='inspector-0');second=dataplane(state,writer='inspector-1')
  first.record_event({'mode':'inline','writer':0});second.record_event({'mode':'inline','writer':1})
  runtime=control(state)
  assert runtime.ingest_events()==2
  assert {event['writer'] for event in runtime.store.events()}=={0,1}
