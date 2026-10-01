"""Process separation: supervision, admission and operator status across the plane boundary."""
import sys
import time
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from asr_proxy.selfhost.config import envoy_config, load
from asr_proxy.selfhost.dataplane import DataplaneRuntime, create_status_app
from asr_proxy.selfhost.gateway import create_gateway
from asr_proxy.selfhost.main import initialize, plane_paths, publisher
from asr_proxy.selfhost.operations import Operations
from asr_proxy.selfhost.runtime import SelfhostRuntime
from asr_proxy.selfhost.snapshot import SnapshotLoader
from asr_proxy.selfhost.supervisor import Supervisor

CONFIG=Path(__file__).parents[1]/'deploy/selfhost/deployment.yaml'
KEY='synthetic-client-'+'x'*32
SIGN=b'synthetic-signing-key-'+b'x'*32


def python(code):
  return [sys.executable,'-c',code]


def test_control_exit_restarts_only_control(tmp_path):
  marker=tmp_path/'control-starts'
  control=python(f"import pathlib,time;p=pathlib.Path({str(marker)!r});n=int(p.read_text() or 0) if p.exists() else 0;"
    "p.write_text(str(n+1));time.sleep(.2 if n==0 else 60)")
  supervisor=Supervisor(control,python('import time;time.sleep(60)'),max_backoff=.1,poll=.05)
  import threading
  result={}
  thread=threading.Thread(target=lambda:result.update(code=supervisor.run(install_signals=False)))
  thread.start()
  try:
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and not (marker.exists() and marker.read_text()=='2'):time.sleep(.05)
    dataplane=supervisor.processes['dataplane']
    assert marker.read_text()=='2' and dataplane.poll() is None
  finally:
    supervisor.stop();thread.join(15)
  assert result['code']==0 and dataplane.poll() is not None


def test_dataplane_exit_stops_the_container(tmp_path):
  supervisor=Supervisor(python('import time;time.sleep(60)'),python('import sys;sys.exit(3)'),poll=.05)
  assert supervisor.run(install_signals=False)==3
  assert supervisor.processes['control'].poll() is not None


@pytest.fixture
def state(tmp_path):
  state=tmp_path/'state'
  initialize(state,tmp_path/'generated',load(CONFIG),'synthetic-password-047')
  return state


def plane(state):
  paths=plane_paths(state)
  return DataplaneRuntime(state,SnapshotLoader(paths.policy,paths.trust))


@pytest.mark.parametrize('reason',['policy_snapshot_unavailable','inspector_unavailable','evidence_unavailable'])
def test_gateway_admission_closes_before_forward_without_leaking_reason(reason):
  def forbidden(request):raise AssertionError('Must not reach Envoy')
  outcomes=[]
  app=create_gateway(load(CONFIG),KEY,SIGN,transport=httpx.MockTransport(forbidden),
    observe=lambda phase,status:outcomes.append((phase,status)),admission_check=lambda:reason)
  with TestClient(app) as client:
    unauthenticated=client.post('/api/notes',json={})
    response=client.post('/api/notes',headers={'x-td-client-key':KEY},json={'message':'safe'})
  assert unauthenticated.status_code==401
  assert response.status_code==503 and response.json()=={'error':'dataplane_unavailable'}
  assert reason not in response.text and outcomes[-1]==('dataplane_admission',503)


def test_status_app_reports_readiness_and_never_policy_content(state):
  runtime=plane(state)
  with TestClient(create_status_app(runtime)) as client:
    assert client.get('/_trapdefense/ready').status_code==503
    runtime.inspector_ready=True
    ready=client.get('/_trapdefense/ready')
    status=client.get('/_trapdefense/status').json()
  assert ready.status_code==200 and ready.json()=={'ready':True,'admission':'open'}
  assert status['snapshot']['revision']==1 and status['evidence']['healthy'] is True
  assert 'rules' not in str(status) and 'notes.read' not in str(status)


def test_envoy_dials_the_dataplane_inspector_host():
  config=load(CONFIG)
  rendered=yaml.safe_load(envoy_config(config,'dataplane'))
  address=rendered['static_resources']['clusters'][0]['load_assignment']['endpoints'][0]['lb_endpoints'][0]['endpoint']['address']['socket_address']
  assert address['address']=='dataplane'
  pooled=yaml.safe_load(envoy_config(config.model_copy(update={'inspector_replicas':2}),'dataplane'))
  members=pooled['static_resources']['clusters'][0]['load_assignment']['endpoints'][0]['lb_endpoints']
  assert {member['endpoint']['address']['socket_address']['address'] for member in members}=={'dataplane'}


def test_unreachable_dataplane_is_reported_not_guessed(state):
  runtime=SelfhostRuntime(state,load(CONFIG),publisher=publisher(plane_paths(state)),
    dataplane_url='http://127.0.0.1:9')
  network=runtime.network_status()
  assert network['dataplane']['reachable'] is False and network['inspector_ready'] is False
  result=Operations(runtime).diagnose()
  assert result['status']=='dataplane_unreachable' and result['outcome_scope']=='dataplane'


def test_control_reads_outcomes_from_dataplane_status(state,monkeypatch):
  runtime=SelfhostRuntime(state,load(CONFIG),dataplane_url='http://dataplane:18085')
  monkeypatch.setattr(runtime,'dataplane_status',lambda:{'ready':True,'inspector_ready':True,'proxy_ready':True,
    'gateway_outcomes':[{'phase':'gateway_authentication','http_status':401,'count':2,'last_seen':'t'}],
    'latency':{'requests':[]}})
  snapshot=Operations(runtime).snapshot()
  assert snapshot['outcome_scope']=='dataplane' and snapshot['recent_gateway_outcomes'][0]['count']==2
  assert Operations(runtime).diagnose()['status']=='listeners_ready'


def test_apply_answers_after_dataplane_acknowledges_revision(state,monkeypatch):
  runtime=SelfhostRuntime(state,load(CONFIG),publisher=publisher(plane_paths(state)),dataplane_url='http://dataplane:18085')
  dataplane=plane(state)
  def status():
    dataplane.refresh()
    return {'applied_revision':dataplane.snapshot.revision}
  monkeypatch.setattr(runtime,'dataplane_status',status)
  policy=runtime.policy();policy['rules']['0:notes.read']='block'
  runtime.apply(policy)
  assert dataplane.policy['rules']['0:notes.read']=='block'
  assert not any(row['event']=='policy.dataplane_pending' for row in runtime.store.audits())


def test_unacknowledged_apply_is_saved_and_audited(state,monkeypatch):
  runtime=SelfhostRuntime(state,load(CONFIG),publisher=publisher(plane_paths(state)),dataplane_url='http://dataplane:18085')
  monkeypatch.setattr(runtime,'dataplane_status',lambda:{'reachable':False})
  monkeypatch.setattr(runtime,'wait_applied',lambda revision,timeout=5.0:False)
  policy=runtime.policy();policy['rules']['0:notes.read']='block'
  assert runtime.apply(policy)['rules']['0:notes.read']=='block'
  assert any(row['event']=='policy.dataplane_pending' for row in runtime.store.audits())


def test_applied_revision_waits_for_every_worker(state):
  runtime=plane(state)
  runtime.worker_revisions=lambda:[1,None]
  assert runtime.status()['applied_revision'] is None
  runtime.worker_revisions=lambda:[1,1]
  assert runtime.status()['applied_revision']==1


def test_operations_snapshot_reports_dataplane_without_policy_content(state,monkeypatch):
  runtime=SelfhostRuntime(state,load(CONFIG),dataplane_url='http://dataplane:18085')
  dataplane=plane(state);dataplane.inspector_ready=True
  monkeypatch.setattr(runtime,'dataplane_status',dataplane.status)
  summary=Operations(runtime).snapshot()['dataplane']
  assert summary['reachable'] and summary['ready'] and summary['snapshot']['revision']==1
  assert summary['applied_revision']==1 and 'gateway_outcomes' not in summary
  assert 'rules' not in str(summary) and 'notes.read' not in str(summary)
  monkeypatch.setattr(runtime,'dataplane_status',lambda:{'reachable':False})
  assert Operations(runtime).snapshot()['dataplane']=={'reachable':False}
