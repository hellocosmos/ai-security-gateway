"""Operator changes must be staged, authenticated, isolated and recoverable."""
from pathlib import Path
import json
import pytest
from fastapi.testclient import TestClient
from asr_proxy.selfhost.config import load
from asr_proxy.selfhost.main import initialize
from asr_proxy.selfhost.runtime import SelfhostRuntime
from asr_proxy.selfhost.operations import Operations, SettingsInput, PreviewInput, RestoreInput, activate, active_config
from asr_proxy.console.app import create_app

@pytest.fixture
def runtime(tmp_path):
  config=load(Path(__file__).parents[1]/'deploy/selfhost/deployment.yaml')
  initialize(tmp_path/'state', tmp_path/'generated', config, 'synthetic-password-043')
  return SelfhostRuntime(tmp_path/'state', config)


def test_stage_persist_activate_and_restore(runtime):
  operations=Operations(runtime)
  config=runtime.deployment.model_dump(exclude_none=True)
  config['max_body_bytes']=32768
  config['gateway_max_inflight']=16
  staged=operations.stage(SettingsInput(version=0,config=config))
  assert staged['restart_required'] and runtime.deployment.max_body_bytes==1048576
  with pytest.raises(ValueError,match='changed'):
    operations.stage(SettingsInput(version=0,config=config))
  assert Operations(runtime).snapshot()['pending']['config']['max_body_bytes']==32768
  assert activate(runtime.store,runtime.deployment).max_body_bytes==32768
  assert active_config(runtime.store,runtime.deployment).max_body_bytes==32768
  assert active_config(runtime.store,runtime.deployment).gateway_max_inflight==16
  saved=operations.snapshot()
  operations.restore(RestoreInput(version=saved['version'],revision=saved['history'][0]['revision']))
  assert activate(runtime.store,runtime.deployment).max_body_bytes==1048576
  assert active_config(runtime.store,runtime.deployment).gateway_max_inflight==32


def test_secrets_never_returned_or_audited(runtime):
  operations=Operations(runtime)
  config=runtime.deployment.model_dump(exclude_none=True)
  config['target_auth']={'mode':'static_bearer','secret_file':'/state/new-key'}
  token='synthetic-secret-043'
  result=operations.stage(SettingsInput(version=0,config=config,target_secret=token))
  assert token not in json.dumps(result)
  assert token not in runtime.store.path.read_bytes().decode(errors='ignore')
  path=Path(result['pending']['config']['target_auth']['secret_file'])
  assert path.read_text()==token and path.stat().st_mode & 0o777==0o600
  config['target_auth']['secret_file']='/etc/passwd'
  with pytest.raises(ValueError):operations.stage(SettingsInput(version=result['version'],config=config))


def test_preview_isolated_allow_redact_deny(runtime):
  operations=Operations(runtime)
  before=runtime.policy()
  for body,route,decision in [({'message':'Hello'},0,'allow'),
      ({'message':'Contact alex@example.com'},0,'redact'),
      ({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'notes.delete','arguments':{'message':'Delete'}}},1,'block')]:
    verdict=operations.preview(PreviewInput(route=route,body=body,policy=before))
    assert verdict['decision']==decision,verdict
    assert verdict['upstream_called'] is False
    assert verdict['agent_authorization']=='not_tested'
  assert runtime.policy()==before
  assert not (runtime.store.directory/'inspection.jsonl').exists()


def test_api_requires_auth_csrf_admin(runtime):
  app=create_app(runtime.store.directory,seed=False,runtime_factory=lambda *a,**k:runtime,
                 console_origin='http://localhost:18080')
  with TestClient(app) as client:
    assert client.get('/demo-api/operations').status_code==401
    headers={'Origin':'http://localhost:18080','X-TD-Demo':'1'}
    assert client.post('/demo-api/login',headers=headers,json={'username':'admin','password':'synthetic-password-043'}).status_code==200
    assert client.get('/demo-api/operations').status_code==200
    data={'version':0,'config':runtime.deployment.model_dump(exclude_none=True)}
    assert client.post('/demo-api/operations/stage',json=data).status_code==403
    assert client.post('/demo-api/operations/stage',headers=headers,json=data).status_code==200
    viewer=runtime.store.create_session({'username':'viewer','role':'viewer','authentication':'local'})
    client.cookies.set('td_demo_session',viewer)
    assert client.post('/demo-api/operations/stage',headers=headers,json=data).status_code==403


def test_invalid_trust_change_and_secret_error_do_not_modify_state(runtime):
  operations=Operations(runtime)
  config=runtime.deployment.model_dump(exclude_none=True)
  config['console_origin']='https://unexpected.example'
  with pytest.raises(ValueError,match='Invalid connection'):
    operations.stage(SettingsInput(version=0,config=config))
  assert operations.snapshot()['version']==0
  config['console_origin']=runtime.deployment.console_origin
  config['target_auth']={'mode':'static_bearer','secret_file':'/state/new-key'}
  with pytest.raises(ValueError) as error:
    operations.stage(SettingsInput(version=0,config=config,target_secret='secret with space'))
  assert 'secret with space' not in str(error.value)
  assert operations.snapshot()['pending'] is None


def test_policy_snapshot_restores_previous_rules(runtime):
  operations=Operations(runtime)
  old=runtime.policy();old['rules']['0:notes.read']='block';old['pii_action']='block';runtime.apply(old)
  config=runtime.deployment.model_dump(exclude_none=True)
  config['routes'][0]['rule']['action']='lookup'
  first=operations.stage(SettingsInput(version=0,config=config))
  activated=activate(runtime.store,runtime.deployment)
  assert runtime.policy()['rules']['0:notes.read']=='allow'
  assert runtime.policy()['pii_action']=='block'
  recreated=SelfhostRuntime(runtime.store.directory,activated)
  operations=Operations(recreated)
  saved=operations.snapshot()
  operations.restore(RestoreInput(version=saved['version'],revision=first['history'][0]['revision']))
  activate(runtime.store,activated)
  assert runtime.policy()['rules']['0:notes.read']=='block'


def test_diagnostics_respect_egress_boundary(runtime, monkeypatch):
  runtime.observe_gateway('gateway_authentication',401)
  monkeypatch.setattr(runtime,'network_status',lambda:{'inspector_ready':True,'proxy_ready':False})
  result=Operations(runtime).diagnose()
  assert result['status']=='proxy_unavailable'
  assert result['destination']=='not_probed'
  assert result['recent_gateway_outcomes'][0]['phase']=='gateway_authentication'
  assert set(result['recent_gateway_outcomes'][0])=={'phase','http_status','count','last_seen'}


@pytest.mark.parametrize('provider',['openai','anthropic','google','openrouter'])
def test_provider_wizard_uses_separate_managed_secret(runtime,provider):
  candidate={'console_origin':runtime.deployment.console_origin,
    'llm':{'provider':provider,'models':['synthetic-model']}}
  result=Operations(runtime).stage(SettingsInput(version=0,config=candidate,target_secret='synthetic-provider-key'))
  config=activate(runtime.store,runtime.deployment)
  assert config.llm.provider==provider
  assert config.upstream.startswith('https://')
  assert config.target_auth.secret_file.startswith(str(runtime.store.directory))
  assert 'synthetic-provider-key' not in json.dumps(result)


def test_gateway_observer_separates_admission_failure(runtime):
  from asr_proxy.selfhost.gateway import create_gateway
  gateway=create_gateway(runtime.deployment,'synthetic-gateway-key',runtime.key,
                         observe=runtime.observe_gateway)
  with TestClient(gateway) as client:
    assert client.post('/api/notes',json={'message':'secret-not-retained'}).status_code==401
  outcomes=Operations(runtime).snapshot()['recent_gateway_outcomes']
  assert outcomes[0]['phase']=='gateway_authentication' and outcomes[0]['http_status']==401
  assert 'secret-not-retained' not in json.dumps(outcomes)
