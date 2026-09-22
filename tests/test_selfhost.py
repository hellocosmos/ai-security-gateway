"""Self-hosted trust boundaries; all credentials and targets are synthetic."""
import json
from pathlib import Path
from types import SimpleNamespace
import time
import httpx
import jwt
import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from asr_proxy.selfhost.config import Deployment, load, envoy_config
from asr_proxy.selfhost.auth import GatewayAuthenticator
from asr_proxy.selfhost.gateway import create_gateway
from asr_proxy.selfhost.main import initialize
from asr_proxy.selfhost.runtime import SelfhostRuntime
from asr_proxy.console.store import Store
from asr_proxy.inspection.contracts import HttpMessage
from asr_proxy.inspection.identity import AttestationVerifier

KEY='synthetic-client-'+'x'*32
SIGN=b'synthetic-signing-key-'+b'x'*32

@pytest.fixture
def config():return load(Path(__file__).parents[1]/'deploy/selfhost/deployment.yaml')


def jwt_auth(**updates):
  value={
    'mode':'jwt',
    'issuer':'https://issuer.example/tenant',
    'audience':'https://firewall.example/mcp',
    'jwks_uri':'https://issuer.example/jwks',
    'resource':'https://firewall.example/mcp',
    'authorization_servers':['https://issuer.example/tenant'],
    'required_scopes':['mcp.invoke'],
  }
  value.update(updates)
  return value


def deployment_data(config):
  return config.model_dump(exclude_none=True)


def test_structured_auth_defaults_and_public_boundary(config):
  assert config.gateway_auth.mode=='client_key'
  assert config.target_auth.mode=='passthrough_bearer'
  public=config.public()
  assert public['gateway_auth']=={'mode':'client_key'}
  assert public['target_auth']=={'mode':'passthrough_bearer'}
  assert 'secret_file' not in public['target_auth']


def test_legacy_auth_is_normalized(config):
  data=deployment_data(config)
  data.pop('target_auth')
  data.update(destination_auth='static_bearer',bearer_file='/state/target.token')
  parsed=Deployment.model_validate(data)
  assert parsed.target_auth.mode=='static_bearer'
  assert parsed.target_auth.secret_file=='/state/target.token'
  assert parsed.destination_auth is None and parsed.bearer_file is None


def test_jwt_gateway_requires_separate_target_credential(config):
  data=deployment_data(config)
  data['gateway_auth']=jwt_auth()
  data['target_auth']={'mode':'passthrough_bearer'}
  with pytest.raises(ValueError,match='passthrough'):
    Deployment.model_validate(data)


def test_access_broker_requires_explicit_jwt_identity_mapping(config):
  data=deployment_data(config)
  data['access_broker']={'enabled':True,'tenant_id':'tenant-a'}
  with pytest.raises(ValueError,match='identity_claims'):
    Deployment.model_validate(data)
  data.update(gateway_auth=jwt_auth(),target_auth={'mode':'none'})
  with pytest.raises(ValueError,match='identity_claims'):
    Deployment.model_validate(data)
  data['gateway_auth']['identity_claims']={}
  parsed=Deployment.model_validate(data)
  assert parsed.access_broker.enabled is True
  assert parsed.public()['access_broker']=={
    'enabled':True,'tenant_id':'tenant-a','maturity':'experimental'}


@pytest.mark.parametrize('auth',[
  jwt_auth(issuer='http://issuer.example/tenant'),
  jwt_auth(jwks_uri='http://issuer.example/jwks'),
  jwt_auth(resource='http://firewall.example/mcp'),
  jwt_auth(authorization_servers=['http://issuer.example/tenant']),
  jwt_auth(authorization_servers=['https://other.example/tenant']),
  jwt_auth(required_scopes=['mcp.invoke','mcp.invoke']),
  jwt_auth(authorized_parties=['duplicate','duplicate']),
  jwt_auth(authorized_parties=['contains whitespace']),
])
def test_jwt_gateway_rejects_unsafe_contract(config,auth):
  data=deployment_data(config)
  data.update(gateway_auth=auth,target_auth={'mode':'none'})
  with pytest.raises(ValueError):Deployment.model_validate(data)


def test_synthetic_loopback_jwt_requires_explicit_opt_in(config):
  auth=jwt_auth(
    issuer='http://127.0.0.1:9190',jwks_uri='http://127.0.0.1:9190/jwks',
    resource='http://127.0.0.1:18084/mcp',authorization_servers=['http://127.0.0.1:9190'])
  data=deployment_data(config)
  data.update(gateway_auth=auth,target_auth={'mode':'none'})
  with pytest.raises(ValueError):Deployment.model_validate(data)
  auth['allow_insecure_loopback']=True
  parsed=Deployment.model_validate({**data,'gateway_auth':auth})
  assert parsed.gateway_auth.metadata_path=='/.well-known/oauth-protected-resource/mcp'
  assert parsed.gateway_auth.metadata_url=='http://127.0.0.1:18084/.well-known/oauth-protected-resource/mcp'


@pytest.mark.parametrize('target_auth',[
  {'mode':'static_api_key','secret_file':'relative.key','header':'x-api-key'},
  {'mode':'static_api_key','secret_file':'/state/key','header':'x-td-secret'},
  {'mode':'static_api_key','secret_file':'/state/key','header':'authorization'},
  {'mode':'static_api_key','secret_file':'/state/key','header':'x-api-key','prefix':'bad\nvalue'},
  {'mode':'static_bearer'},
  {'mode':'none','secret_file':'/state/key'},
])
def test_target_auth_rejects_unsafe_contract(config,target_auth):
  with pytest.raises(ValueError):
    Deployment.model_validate({**deployment_data(config),'target_auth':target_auth})


def test_static_api_key_public_contract_excludes_secret_path(config):
  data=deployment_data(config)
  data['target_auth']={'mode':'static_api_key','secret_file':'/state/key','header':'Ocp-Apim-Subscription-Key'}
  parsed=Deployment.model_validate(data)
  assert parsed.public()['target_auth']=={
    'mode':'static_api_key','header':'ocp-apim-subscription-key','prefix':''}

@pytest.mark.parametrize('update',[
 {'upstream':'https://user:secret@example.com'}, {'upstream':'https://example.com/path'},
 {'upstream':'http://fixture:8080','allow_plaintext_upstream':False},
 {'console_origin':'https://example.com/path'}, {'destination_auth':'static_bearer'},
 {'bearer_file':'/secret'}, {'upstream':'https://127.0.0.1'},
])
def test_invalid_contract(config,update):
  with pytest.raises(ValueError):Deployment.model_validate({**config.model_dump(),**update})

def test_tls_and_private_inspector(config):
  data=config.model_dump();data['upstream']='https://api.example.com'
  for route in data['routes']:route['authority']='api.example.com'
  rendered=yaml.safe_load(envoy_config(Deployment.model_validate(data)))
  clusters=rendered['static_resources']['clusters']
  tls=clusters[1]['transport_socket']['typed_config']
  assert tls['sni']=='api.example.com'
  assert tls['common_tls_context']['validation_context']['match_typed_subject_alt_names'][0]['matcher']['exact']=='api.example.com'
  assert clusters[0]['load_assignment']['endpoints'][0]['lb_endpoints'][0]['endpoint']['address']['socket_address']['address']=='app'


def test_optional_inspector_processes_render_only_healthy_endpoints(config):
  data=deployment_data(config)
  for invalid in (0,3,5,'2',True):
    with pytest.raises(ValueError):Deployment.model_validate({**data,'inspector_replicas':invalid})
  for replicas in (2,4):
    selected=Deployment.model_validate({**data,'inspector_replicas':replicas})
    rendered=yaml.safe_load(envoy_config(selected))
    inspector=rendered['static_resources']['clusters'][0]
    endpoints=inspector['load_assignment']['endpoints'][0]['lb_endpoints']
    assert [item['endpoint']['address']['socket_address']['port_value'] for item in endpoints]==[
      18120+index for index in range(replicas)]
    assert [item['endpoint']['health_check_config']['port_value'] for item in endpoints]==[
      18130+index for index in range(replicas)]
    assert inspector['lb_policy']=='ROUND_ROBIN'
    assert inspector['common_lb_config']['healthy_panic_threshold']['value']==0
    assert inspector['health_checks'][0]['http_health_check']['path']=='/_trapdefense/health'
    assert selected.public()['inspector_replicas']==replicas

def test_initialization_preserves_account(tmp_path,config):
  state=tmp_path/'state';generated=tmp_path/'generated'
  initialize(state,generated,config,'synthetic-password-036')
  store=Store(state,require_existing=True)
  assert store.check_password('synthetic-password-036') and not store.check_password('1234')
  assert store.changed()
  before=(state/'attestation.key').read_bytes()
  with pytest.raises(ValueError):initialize(state,generated,config,'another-password')
  assert (state/'attestation.key').read_bytes()==before
  assert (state/'client.key').stat().st_mode & 0o077 == 0
  with pytest.raises(ValueError):Store(tmp_path/'empty',require_existing=True)


def test_selfhost_runtime_uses_built_in_broker_when_enabled(tmp_path,config):
  data=deployment_data(config)
  data.update(gateway_auth=jwt_auth(identity_claims={}),target_auth={'mode':'none'},
    access_broker={'enabled':True,'tenant_id':'tenant-a'})
  secured=Deployment.model_validate(data)
  state=tmp_path/'state';initialize(state,tmp_path/'generated',secured,'synthetic-password-039')
  runtime=SelfhostRuntime(state,secured)
  assert runtime.broker is not None and runtime.config(runtime.policy()).access_broker_enabled
  agent=runtime.register_agent({'agent_id':'agent-a','owner_id':'owner-a','risk_tier':'medium',
    'allowed_tools':['initialize']},{'principal_id':'admin','tenant_id':'tenant-a','authentication':'local'})
  delegation=runtime.create_delegation({'agent_id':'agent-a','user_id':'user-a','task_id':'task-a',
    'purpose':'Initialize MCP','ttl_seconds':3600},
    {'principal_id':'admin','tenant_id':'tenant-a','authentication':'local'})
  assert agent['tenant_id']=='tenant-a' and agent['allowed_tools']==['initialize']
  assert delegation['tenant_id']=='tenant-a' and delegation['allowed_actions']==['initialize']
  assert any(tool['name']=='initialize' for tool in runtime.broker_snapshot()['tools'])

def test_gateway_signs_actual_request_and_separates_auth(config,tmp_path):
  calls=[]
  def upstream(request):
    calls.append(request)
    message=HttpMessage(request.method,request.headers['host'],request.url.raw_path.decode(),dict(request.headers),request.content)
    verifier=AttestationVerifier(SIGN,str(tmp_path/'nonces'),required_fields=('source_id',))
    assert verifier.verify(message,consume=True)['source_id']=='selfhost-adapter'
    assert request.headers['authorization']=='Bearer synthetic-service-token'
    assert request.headers['x-api-key']=='synthetic-api-key'
    assert 'x-td-client-key' not in request.headers
    assert 'x-forwarded-for' not in request.headers
    return httpx.Response(200,headers={'content-type':'application/json'},stream=httpx.ByteStream(b'{}'))
  app=create_gateway(config,KEY,SIGN,transport=httpx.MockTransport(upstream))
  with TestClient(app) as client:
    result=client.post('/api/notes?q=hello',headers={'x-td-client-key':KEY,'authorization':'Bearer synthetic-service-token','x-api-key':'synthetic-api-key','x-forwarded-for':'spoofed'},json={'message':'safe'})
  assert result.status_code==200 and len(calls)==1
  assert calls[0].url.host=='envoy'

@pytest.mark.parametrize('headers,path,status',[
 ({},'/api/notes',401), ({'x-td-client-key':'bad'},'/api/notes',401),
 ({'x-td-client-key':KEY},'/unknown',403),
 ({'x-td-client-key':KEY,'cookie':'session=x'},'/api/notes',400),
 ({'x-td-client-key':KEY,'mcp-session-id':'session'},'/api/notes',400),
 ({'x-td-client-key':KEY,'content-encoding':'gzip'},'/api/notes',415),
 ({'x-td-client-key':KEY,'connection':'authorization'},'/api/notes',400),
])
def test_gateway_rejects_before_forward(config,headers,path,status):
  def forbidden(request):raise AssertionError('Must not reach Envoy')
  app=create_gateway(config,KEY,SIGN,transport=httpx.MockTransport(forbidden))
  assert TestClient(app).post(path,headers=headers,json={}).status_code==status

def test_static_bearer_and_conflict(config):
  seen=[]
  def target(request):
    seen.append(request.headers['authorization'])
    return httpx.Response(200,stream=httpx.ByteStream(b'{}'))
  data=deployment_data(config)
  data['target_auth']={'mode':'static_bearer','secret_file':'/state/target.token'}
  static=Deployment.model_validate(data)
  client=TestClient(create_gateway(static,KEY,SIGN,target_secret='synthetic-static',
    transport=httpx.MockTransport(target)))
  assert client.post('/api/notes',headers={'x-td-client-key':KEY},json={}).status_code==200
  assert seen==['Bearer synthetic-static']
  assert client.post('/api/notes',headers={'x-td-client-key':KEY,'authorization':'Bearer other'},json={}).status_code==400
  assert len(seen)==1


def test_jwt_metadata_challenge_and_separate_target_credential(config,tmp_path):
  signing_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  class Keys:
    def get_signing_key_from_jwt(self,token):return SimpleNamespace(key=signing_key.public_key())
  data=deployment_data(config)
  data.update(gateway_auth=jwt_auth(identity_claims={}),
    target_auth={'mode':'static_bearer','secret_file':'/state/target.token'})
  secured=Deployment.model_validate(data)
  authenticator=GatewayAuthenticator(secured.gateway_auth,client_key=KEY,jwk_client=Keys())
  calls=[]
  def target(request):
    calls.append(request)
    assert request.headers['authorization']=='Bearer synthetic-target-token'
    assert 'x-td-client-key' not in request.headers
    message=HttpMessage(request.method,request.headers['host'],request.url.raw_path.decode(),
      dict(request.headers),request.content)
    identity=AttestationVerifier(SIGN,str(tmp_path/'jwt-nonces')).verify(message,consume=True)
    assert identity['tenant_id']=='tenant-a' and identity['agent_id']=='agent-a'
    assert identity['delegation_id']=='delegation-a' and identity['task_id']=='task-a'
    return httpx.Response(200,headers={'content-type':'application/json'},stream=httpx.ByteStream(b'{}'))
  client=TestClient(create_gateway(secured,KEY,SIGN,target_secret='synthetic-target-token',
    authenticator=authenticator,transport=httpx.MockTransport(target)))
  metadata=client.get('/.well-known/oauth-protected-resource/mcp')
  assert metadata.status_code==200 and metadata.json()['resource']=='https://firewall.example/mcp'
  assert calls==[]
  missing=client.post('/api/notes',json={})
  assert missing.status_code==401 and 'resource_metadata=' in missing.headers['www-authenticate']
  assert calls==[]
  now=int(time.time())
  token=jwt.encode({'iss':'https://issuer.example/tenant','aud':'https://firewall.example/mcp',
    'sub':'synthetic-agent','iat':now,'exp':now+300,'scope':'mcp.invoke',
    'tid':'tenant-a','agent_id':'agent-a','delegation_id':'delegation-a','task_id':'task-a'},signing_key,
    algorithm='RS256',headers={'kid':'synthetic'})
  response=client.post('/api/notes',headers={'authorization':'Bearer '+token},json={})
  assert response.status_code==200 and len(calls)==1
  assert token not in calls[0].headers.values()


def test_jwt_insufficient_scope_returns_gateway_challenge(config):
  signing_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
  class Keys:
    def get_signing_key_from_jwt(self,token):return SimpleNamespace(key=signing_key.public_key())
  data=deployment_data(config)
  data.update(gateway_auth=jwt_auth(required_scopes=['mcp.invoke','notes.write']),
    target_auth={'mode':'none'})
  secured=Deployment.model_validate(data)
  authenticator=GatewayAuthenticator(secured.gateway_auth,client_key=KEY,jwk_client=Keys())
  def forbidden(request):raise AssertionError('Must not reach Envoy')
  client=TestClient(create_gateway(secured,KEY,SIGN,authenticator=authenticator,
    transport=httpx.MockTransport(forbidden)))
  now=int(time.time())
  token=jwt.encode({'iss':'https://issuer.example/tenant','aud':'https://firewall.example/mcp',
    'sub':'synthetic-agent','iat':now,'exp':now+300,'scope':'mcp.invoke'},signing_key,
    algorithm='RS256',headers={'kid':'synthetic'})
  response=client.post('/api/notes',headers={'authorization':'Bearer '+token},json={})
  assert response.status_code==403 and response.json()=={'error':'insufficient_scope'}
  assert 'scope="mcp.invoke notes.write"' in response.headers['www-authenticate']

@pytest.mark.parametrize('status,headers,content,expected',[
 (302,{'location':'https://example.com'},b'',502),
 (200,{'content-type':'text/event-stream'},b'data: hello',502),
 (200,{'set-cookie':'session=x'},b'{}',502),
 (200,{'mcp-session-id':'x'},b'{}',502),
 (200,{},b'x'*1048577,502),
 (401,{'www-authenticate':'Bearer realm="target"'},b'{}',401),
],ids=['redirect','sse','cookie','session','large','unauthorized'])
def test_response_contract(config,status,headers,content,expected):
  transport=httpx.MockTransport(lambda request:httpx.Response(status,headers=headers,stream=httpx.ByteStream(content)))
  client=TestClient(create_gateway(config,KEY,SIGN,transport=transport))
  response=client.post('/api/notes',headers={'x-td-client-key':KEY},json={})
  assert response.status_code==expected
  assert 'www-authenticate' not in response.headers

def test_no_fallback(config):
  def unavailable(request):raise httpx.ConnectError('synthetic connection failure')
  client=TestClient(create_gateway(config,KEY,SIGN,transport=httpx.MockTransport(unavailable)))
  assert client.post('/api/notes',headers={'x-td-client-key':KEY},json={}).status_code==503

def test_body_limit(config):
  def forbidden(request):raise AssertionError('Must not forward large body')
  client=TestClient(create_gateway(config,KEY,SIGN,transport=httpx.MockTransport(forbidden)))
  assert client.post('/api/notes',headers={'x-td-client-key':KEY},content=b'x'*1048577).status_code==413
