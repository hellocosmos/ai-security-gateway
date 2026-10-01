"""Loopback-only demo service. Never attached to the production API application."""
import os
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI,APIRouter,Depends,HTTPException,Request,Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field

from .runtime import Runtime
from .scenarios import Policy,CASES

COOKIE='td_demo_session'
ORIGINS={'http://127.0.0.1:5176','http://localhost:5176'}

class Login(BaseModel):
  username:str=Field(min_length=1,max_length=80)
  password:str=Field(min_length=1,max_length=128)
class Password(BaseModel):
  current_password:str=Field(min_length=1,max_length=128)
  new_password:str=Field(min_length=8,max_length=128)
class Inspectors(BaseModel):
  model_config=ConfigDict(extra='forbid')
  action:Literal['start','stop','apply']
  replicas:Literal[1,2,4]=1

class Run(BaseModel):
  model_config=ConfigDict(extra='forbid')
  approval_id:str|None=Field(default=None,pattern=r'^apv_[a-f0-9]{12}$')

class AgentCreate(BaseModel):
  model_config=ConfigDict(extra='forbid')
  agent_id:str=Field(pattern=r'^[A-Za-z0-9_-]{2,60}$')
  owner_id:str=Field(min_length=2,max_length=80)
  risk_tier:Literal['low','medium','high']='medium'
  allowed_tools:list[str]=Field(min_length=1,max_length=32)
  allow_autonomous:bool=False

class CredentialCreate(BaseModel):
  model_config=ConfigDict(extra='forbid')
  ttl_seconds:int=Field(default=86400,ge=60,le=2592000)
  rotate_id:str|None=Field(default=None,pattern=r'^key_[a-f0-9]{32}$')

class AgentStatus(BaseModel):
  model_config=ConfigDict(extra='forbid')
  enabled:bool

class DelegationCreate(BaseModel):
  model_config=ConfigDict(extra='forbid')
  agent_id:str=Field(pattern=r'^[A-Za-z0-9_-]{2,60}$')
  user_id:str=Field(min_length=1,max_length=256)
  task_id:str=Field(pattern=r'^[A-Za-z0-9_-]{2,60}$')
  purpose:str=Field(min_length=3,max_length=160)
  ttl_seconds:int=Field(default=3600,ge=60,le=86400)

class ApprovalReview(BaseModel):
  model_config=ConfigDict(extra='forbid')
  comment:str=Field(min_length=3,max_length=300)



def create_app(directory,seed=True,*,runtime_factory=Runtime,lifespan=None,identity=None,local_login=True,console_origin=None):
  runtime=runtime_factory(directory,seed=seed)
  app=FastAPI(title='TrapDefense AI Firewall Console',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
  app.state.runtime=runtime
  deployment=getattr(runtime,'deployment',None)
  origins=({console_origin} if console_origin else ORIGINS) | ({identity.origin} if identity else set())
  secure_cookie=bool((console_origin or (identity.origin if identity else '')).startswith('https:'))
  if identity:
    from .sso import install_sso
    install_sso(app,identity,runtime.store,COOKIE)

  @app.middleware('http')
  async def boundaries(request,call_next):
    # Reject cross-origin writes, including login CSRF; no permissive CORS middleware.
    if request.method not in ('GET','HEAD','OPTIONS'):
      if request.headers.get('origin') not in origins or request.headers.get('x-td-demo')!='1':
        return JSONResponse({'detail':'Cross-origin or missing CSRF request rejected'},status_code=403)
      if request.headers.get('content-type','').split(';')[0]!='application/json':
        return JSONResponse({'detail':'JSON required'},status_code=415)
      size=0
      chunks=[]
      async for chunk in request.stream():
        size+=len(chunk)
        if size>16384:return JSONResponse({'detail':'Request too large'},status_code=413)
        chunks.append(chunk)
      request._body=b''.join(chunks)
    response=await call_next(request)
    actor=getattr(request.state,'principal',None)
    if actor and request.method=='POST' and request.url.path!='/demo-api/logout':
      runtime.store.audit('console.write',request.url.path+' / '+str(response.status_code),actor=(actor.get('tenant_id','local')+'/'+actor['username']))
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

  @app.exception_handler(ValueError)
  async def invalid(request,exc):return JSONResponse({'detail':str(exc)},status_code=400)

  @app.exception_handler(RequestValidationError)
  async def validation(request,exc):
    # Never echo invalid password or arbitrary request input from Pydantic errors.
    return JSONResponse({'detail':'Check the format and length of the input.'},status_code=422)

  def authenticated(request:Request):
    principal=runtime.store.principal(request.cookies.get(COOKIE))
    if not principal:raise HTTPException(401,'Sign in to continue.')
    if principal['authentication']=='local' and not local_login:raise HTTPException(401,'Local login is disabled.')
    if principal['authentication']!='local':
      expected='synthetic_entra' if identity and identity.synthetic else 'entra'
      if not identity or principal['authentication']!=expected or principal.get('tenant_id')!=identity.tenant or principal.get('client_id')!=identity.client:raise HTTPException(401,'Identity configuration changed. Sign in again.')
    request.state.principal=principal
    if request.method not in ('GET','HEAD','OPTIONS') and request.url.path!='/demo-api/logout' and principal['role']!='admin':raise HTTPException(403,'Viewer access is read-only.')
    return principal

  @app.get('/demo-api/auth/config')
  def auth_config():return {'enabled':identity is not None,'synthetic':bool(identity and identity.synthetic),'local_login':local_login,'origin':identity.origin if identity else console_origin,**({'deployment':True} if deployment else {})}

  @app.get('/demo-api/health')
  def health():return {'status':'ready','synthetic':not bool(deployment),'integrated':getattr(runtime,'integrated',False)}

  @app.post('/demo-api/login')
  def login(payload:Login,request:Request,response:Response):
    if not local_login:raise HTTPException(403,'Local login is disabled.')
    with runtime.lock:
      login_identity='local-admin'
      if runtime.store.login_attempt(login_identity):raise HTTPException(429,'Too many login attempts. Try again in 60 seconds.')
      valid=runtime.store.check_password(payload.password) and payload.username=='admin'
      runtime.store.login_attempt(login_identity,valid)
      if not valid:
        runtime.store.audit('account.login_failed','Invalid local credential',actor='anonymous')
        raise HTTPException(401,'Incorrect username or password.')
      runtime.store.logout(request.cookies.get(COOKIE))
      token=runtime.store.create_session()
      response.set_cookie(COOKIE,token,httponly=True,samesite='strict',secure=secure_cookie,path='/demo-api',max_age=8*3600)
      runtime.store.audit('account.login','Local console session started',actor='local/admin')
      return {'username':'admin','role':'admin','authentication':'local','password_changed':runtime.store.changed()}

  router=APIRouter(prefix='/demo-api',dependencies=[Depends(authenticated)])

  def actor(principal):
    return {'principal_id':principal['username'],'tenant_id':runtime.broker_tenant,
      'authentication':principal['authentication']}

  @router.get('/session')
  def session(request:Request):return {**request.state.principal,'password_changed':runtime.store.changed() if request.state.principal['authentication']=='local' else True}

  @router.post('/logout')
  def logout(request:Request,response:Response):
    runtime.store.logout(request.cookies.get(COOKIE));response.delete_cookie(COOKIE,path='/demo-api')
    runtime.store.audit('account.logout','Console session ended',actor=request.state.principal.get('tenant_id','local')+'/'+request.state.principal['username'])
    return {'ok':True}

  @router.post('/password')
  def password(payload:Password,response:Response,request:Request):
    if request.state.principal['authentication']!='local':raise HTTPException(403,'Manage your password in Entra.')
    if payload.current_password==payload.new_password:raise HTTPException(400,'The new password must differ from the current password.')
    if not runtime.store.change_password(payload.current_password,payload.new_password):raise HTTPException(400,'The current password is incorrect.')
    response.delete_cookie(COOKIE,path='/demo-api')
    return {'ok':True,'reauthenticate':True}

  @router.get('/overview')
  def overview():
    network=runtime.network_status() if getattr(runtime,'integrated',False) or deployment else None
    broker_enabled=getattr(runtime,'broker',None) is not None
    return {'events':runtime.events(),'broker':runtime.broker_snapshot(),
      'product':'open_source','capabilities':{'broker':broker_enabled,'broker_maturity':'experimental','local_agent_credentials':broker_enabled and (not deployment or deployment.gateway_auth.mode=='agent_key')},'policy':runtime.policy(),
      'scenarios':[{'id':key,'label':value['label']} for key,value in CASES.items()] if not deployment else [],
      'system':{'inspector':('ready' if network and network['inspector_ready'] else 'unavailable'),
        'broker':'experimental' if broker_enabled else 'disabled','database':'ready',
        'proxy':('ready' if network['proxy_ready'] else 'unavailable') if network else 'not_connected',
        'iam':('synthetic_entra' if identity.synthetic else 'entra') if identity else 'not_configured',
        'tls':'configured_upstream' if deployment else 'synthetic'},'synthetic':not bool(deployment),'integrated':getattr(runtime,'integrated',False),
      'network':network,'deployment':deployment.public() if deployment else None}

  @router.get('/events')
  def events():return runtime.events()

  @router.get('/audit')
  def audit():return runtime.store.audits()

  if deployment:
    from asr_proxy.selfhost.operations import Operations, SettingsInput, RestoreInput, PreviewInput
    operations = Operations(runtime)

    @router.get('/operations')
    def operation_status(): return operations.snapshot()

    @router.post('/operations/validate')
    def operation_validate(payload: SettingsInput):
      operations.candidate(payload)
      return {'valid': True}

    @router.post('/operations/stage')
    def operation_stage(payload: SettingsInput): return operations.stage(payload)

    @router.post('/operations/restore')
    def operation_restore(payload: RestoreInput): return operations.restore(payload)

    @router.post('/operations/diagnose')
    def operation_diagnose(): return operations.diagnose()

    @router.post('/operations/preview')
    def operation_preview(payload: PreviewInput): return operations.preview(payload)

  @router.get('/policy')
  def policy():return runtime.policy()

  @router.post('/policy/validate')
  def validate(payload:Policy):
    runtime.config(payload.model_dump())
    return {'valid':True,'scope':'selfhost' if deployment else 'local-demo'}

  @router.post('/policy')
  def apply(payload:Policy):return runtime.apply(payload.model_dump())

  @router.post('/scenarios/{name}')
  def scenario(name:str,payload:Run):
    if deployment:raise HTTPException(404,'Synthetic scenarios are not enabled in self-hosted mode')
    if name not in CASES:raise HTTPException(404,'Scenario not found')
    return runtime.run(name,approval_id=payload.approval_id)

  @router.post('/agents')
  def register_agent(payload:AgentCreate,request:Request):
    return runtime.register_agent(payload.model_dump(),actor(request.state.principal))

  def credentials():
    if runtime.broker is None:raise HTTPException(409,'Access Broker is disabled.')
    if deployment and deployment.gateway_auth.mode!='agent_key':
      raise HTTPException(409,'Configure gateway_auth.mode: agent_key to use local agent credentials.')
    from asr_proxy.selfhost.agent_credentials import AgentCredentials
    return AgentCredentials(runtime.store.directory/'agent-credentials.sqlite',runtime.broker,runtime.broker_tenant)

  @router.get('/agents/{agent_id}/credentials')
  def list_credentials(agent_id:str):return credentials().list(agent_id)

  @router.post('/agents/{agent_id}/credentials')
  def issue_credential(agent_id:str,payload:CredentialCreate):
    return credentials().issue(agent_id,payload.ttl_seconds,rotate_id=payload.rotate_id)

  @router.post('/agents/{agent_id}/credentials/{credential_id}/revoke')
  def revoke_credential(agent_id:str,credential_id:str):
    credentials().revoke(agent_id,credential_id)
    return {'ok':True}

  @router.post('/agents/{agent_id}/status')
  def agent_status(agent_id:str,payload:AgentStatus,request:Request):
    if runtime.broker is None:raise HTTPException(409,'Access Broker is disabled.')
    with runtime.broker.store.transaction():
      agent=runtime.broker.store.get_agent(agent_id)
      if agent is None or agent.tenant_id!=runtime.broker_tenant:raise HTTPException(404,'Agent was not found.')
      return runtime.broker.register_agent(agent.model_copy(update={'enabled':payload.enabled}),
        actor=actor(request.state.principal)).model_dump(mode='json')

  @router.post('/delegations')
  def create_delegation(payload:DelegationCreate,request:Request):
    return runtime.create_delegation(payload.model_dump(),actor(request.state.principal))

  @router.post('/approvals/{approval_id}/approve')
  def approve(approval_id:str,payload:ApprovalReview,request:Request):
    return runtime.review_approval(approval_id,payload.model_dump(),actor(request.state.principal),True)

  @router.post('/approvals/{approval_id}/deny')
  def deny(approval_id:str,payload:ApprovalReview,request:Request):
    return runtime.review_approval(approval_id,payload.model_dump(),actor(request.state.principal),False)

  @router.post('/demo/renew-delegation')
  def renew_demo(request:Request):
    if deployment:raise HTTPException(404,'Synthetic demo operation is unavailable')
    return runtime.renew_demo_delegation(actor(request.state.principal))

  if getattr(runtime,'integrated',False):
    from .network import NetworkConfig
    @router.post('/inspectors')
    def inspectors(payload:Inspectors):return runtime.inspector_control(payload.action,payload.replicas)
    @router.get('/network')
    def network_status():return runtime.network_status()
    @router.post('/network/validate')
    def validate_network(payload:NetworkConfig):
      runtime.network.validate(payload.model_dump())
      return {'valid':True}
    @router.post('/network')
    def apply_network(payload:NetworkConfig):return runtime.update_network(payload.model_dump())

  app.include_router(router)
  return app

from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifecycle(app):
  await app.state.runtime.start()
  try:yield
  finally:await app.state.runtime.stop()


def from_env():
  repository=Path(__file__).resolve().parents[3]
  directory=Path(os.environ.get('TD_CONSOLE_STATE',str(repository/'.runtime-state/console')))
  assets=Path(os.environ.get('TD_CONSOLE_ASSETS',str(repository/'console/dist')))
  if not (assets/'index.html').is_file():raise RuntimeError('Build console assets with scripts/install-console.sh')
  identity=None
  from .identity import Identity
  config_path=os.environ.get('TD_ENTRA_CONFIG')
  synthetic=os.environ.get('TD_SYNTHETIC_ENTRA')=='1'
  if config_path and synthetic:raise RuntimeError('Choose real or synthetic Entra, never both.')
  if config_path:identity=Identity(json.loads(Path(config_path).read_text()))
  elif synthetic:identity=Identity({'tenant_id':'11111111-1111-4111-8111-111111111111','client_id':'22222222-2222-4222-8222-222222222222','redirect_uri':'http://127.0.0.1:5176/demo-api/auth/callback'},synthetic=True)
  local_login=os.environ.get('TD_CONSOLE_LOCAL_LOGIN','0' if config_path else '1')=='1'
  if not identity and not local_login:raise RuntimeError('No console authentication method enabled.')
  app=create_app(directory,seed=False,lifespan=lifecycle,identity=identity,local_login=local_login)
  app.mount('/',StaticFiles(directory=assets,html=True),name='console')
  return app


def main():
  import argparse
  import uvicorn
  parser=argparse.ArgumentParser(description='Run the local TrapDefense proxy console (requires Docker)')
  parser.add_argument('--state-dir',help='Persistent local console state directory')
  parser.add_argument('--assets',help='Built console/dist directory')
  args=parser.parse_args()
  if args.state_dir:os.environ['TD_CONSOLE_STATE']=args.state_dir
  if args.assets:os.environ['TD_CONSOLE_ASSETS']=args.assets
  uvicorn.run('asr_proxy.console.app:from_env',factory=True,host='127.0.0.1',port=5176,access_log=False,ws='none')
