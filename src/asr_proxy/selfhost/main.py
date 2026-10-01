"""Initialize once, then serve the self-hosted Docker package."""
import argparse
import asyncio
import getpass
import os
from pathlib import Path
import secrets
from contextlib import asynccontextmanager, nullcontext
import grpc
import uvicorn
from fastapi.staticfiles import StaticFiles
from envoy.service.ext_proc.v3 import external_processor_pb2_grpc as rpc
from asr_proxy.console.app import create_app
from asr_proxy.console.dataplane import ConsoleProcessor
from asr_proxy.console.store import Store
from asr_proxy.inspection.pool import atomic_write
from .config import load, envoy_config
from .gateway import create_gateway
from types import SimpleNamespace
from .runtime import SelfhostRuntime, seed_policy
from .snapshot import SnapshotPublisher, ensure_signing_key
from .inspector_pool import SelfhostInspectorPool


def plane_paths(state, control_keys=None, policy_trust=None):
  """Default to state-relative paths; Compose mounts the key and trust directories separately."""
  state=Path(state)
  control_keys=control_keys or os.environ.get('TD_CONTROL_KEYS') or state/'control-keys'
  policy_trust=policy_trust or os.environ.get('TD_POLICY_TRUST') or state/'policy-trust'
  return SimpleNamespace(policy=state/'policy',signing_key=Path(control_keys)/'policy-signing.key',
    trust=Path(policy_trust)/'policy.pub')


def publisher(paths):
  return SnapshotPublisher(paths.policy,ensure_signing_key(paths.signing_key,paths.trust))


def initialize(state, generated, config, password, paths=None):
  state.mkdir(parents=True,exist_ok=True,mode=0o700)
  if (state/'console.sqlite').exists():raise ValueError('Already initialized; existing credentials were preserved')
  if not 12<=len(password)<=128:raise ValueError('Use an administrator password of 12–128 characters')
  for name, data in [('attestation.key',secrets.token_bytes(48)),('client.key',secrets.token_urlsafe(36).encode())]:
    atomic_write(state/name,data)
  generated.mkdir(parents=True,exist_ok=True)
  atomic_write(generated/'envoy.yaml',envoy_config(config),mode=0o644)
  store=Store(state,bootstrap_password=password)
  revision=publisher(paths or plane_paths(state)).publish(config,seed_policy(store,config))
  store.audit('installation.initialized',f'Self-hosted AI Firewall · policy snapshot r{revision}')


def secret(path):
  path=Path(path)
  if path.stat().st_mode & 0o077:raise ValueError('Secret files must be owner-readable only (0600)')
  value=path.read_text().strip()
  if not value or any(c.isspace() for c in value):raise ValueError('Invalid secret file format')
  return value


def lock(state, name):
  """Hold an exclusive per-plane lock for the process lifetime; Compose volumes share one kernel."""
  import fcntl
  handle=open(Path(state)/name,'a')
  try:fcntl.flock(handle,fcntl.LOCK_EX | fcntl.LOCK_NB)
  except BlockingIOError:raise ValueError('Stop the app before activating settings') from None
  return handle


def uvicorn_server(app, port):
  server=uvicorn.Server(uvicorn.Config(app,host='0.0.0.0',port=port,access_log=False,
    ws='none',timeout_graceful_shutdown=3,limit_concurrency=64))
  server.capture_signals=lambda: nullcontext()
  return server


async def run_servers(servers, extra=()):
  """Serve until a signal or until any listener or watched task ends."""
  loop=asyncio.get_running_loop()
  import signal
  def stop():
    for server in servers:server.should_exit=True
  for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,stop)
  tasks=[asyncio.create_task(server.serve()) for server in servers]
  try:
    await asyncio.wait(tasks+list(extra),return_when=asyncio.FIRST_COMPLETED)
  finally:
    stop()
    await asyncio.gather(*tasks,return_exceptions=True)


async def control_loop(runtime, interval=0.5):
  """Drain data-plane evidence and audit snapshot rejections; failures never touch the data plane."""
  from .dataplane import log
  seen=None
  tick=0
  while True:
    try:
      await asyncio.to_thread(runtime.ingest_events)
      if tick % 2 == 0:
        status=await asyncio.to_thread(runtime.dataplane_status)
        rejection=status.get('last_rejection')
        if rejection and rejection!=seen:
          seen=rejection
          await asyncio.to_thread(runtime.store.audit,'dataplane.snapshot_rejected',
            f"{rejection['reason']} · kept r{rejection.get('kept_revision')}")
    except Exception as error:
      log('control.maintenance_failed',error=type(error).__name__)
    tick+=1
    await asyncio.sleep(interval)


async def serve_control(args, config, paths):
  state=Path(args.state)
  runtime=SelfhostRuntime(state,config,publisher=publisher(paths),dataplane_url=args.dataplane_url)
  revision=runtime.publish()
  runtime.store.audit('control.started',f'Console and policy publisher · snapshot r{revision}')
  @asynccontextmanager
  async def lifecycle(app):
    task=asyncio.create_task(control_loop(runtime))
    try:yield
    finally:
      task.cancel()
      await asyncio.gather(task,return_exceptions=True)
  console=create_app(state,seed=False,runtime_factory=lambda *a,**k:runtime,
    lifespan=lifecycle,console_origin=config.console_origin)
  console.mount('/',StaticFiles(directory=args.assets,html=True),name='console')
  await run_servers([uvicorn_server(console,18080)])


async def serve_dataplane(args, paths):
  from .dataplane import DataplaneRuntime, create_status_app, log, maintain
  from .snapshot import SnapshotLoader
  state=Path(args.state)
  runtime=DataplaneRuntime(state,SnapshotLoader(paths.policy,paths.trust),proxy_host=args.proxy_host)
  status=uvicorn_server(create_status_app(runtime),18085)
  status_task=asyncio.create_task(status.serve())
  maintenance=asyncio.create_task(maintain(runtime))
  try:
    # Serve no traffic until a signed snapshot verifies; readiness stays closed meanwhile.
    while runtime.snapshot is None:
      if status_task.done():raise RuntimeError('dataplane_status_unavailable')
      await asyncio.sleep(.5)
    config=runtime.deployment
    client_key=secret(state/'client.key')
    if len(client_key)<32:raise ValueError('Invalid client key')
    target_secret=secret(config.target_auth.secret_file) if config.target_auth.secret_file else None
    atomic_write(Path(args.generated)/'envoy.yaml',envoy_config(config,args.inspector_host),mode=0o644)
    pool=None
    grpc_server=None
    if config.inspector_replicas==1:
      grpc_server=grpc.aio.server(maximum_concurrent_rpcs=32)
      rpc.add_ExternalProcessorServicer_to_server(ConsoleProcessor(runtime),grpc_server)
      if not grpc_server.add_insecure_port('0.0.0.0:18081'):raise RuntimeError('Inspector port unavailable')
      await grpc_server.start()
      runtime.inspector_ready=True
    else:
      pool=SelfhostInspectorPool(config.inspector_replicas,state,paths.trust,runtime.snapshot.connection_digest,
        on_health=lambda healthy:setattr(runtime,'inspector_ready',healthy))
      await pool.start()
      runtime.worker_revisions=pool.revisions
    log('dataplane.started',revision=runtime.snapshot.revision,inspectors=config.inspector_replicas)
    from .auth import GatewayAuthenticator
    from .agent_credentials import AgentCredentials
    engine,_=runtime.stream_snapshot()
    local_keys=(AgentCredentials(state/'agent-credentials.sqlite',engine.broker,config.access_broker.tenant_id or '')
      if config.gateway_auth.mode=='agent_key' else None)
    gateway=create_gateway(config,client_key,runtime.key,target_secret=target_secret,
      authenticator=GatewayAuthenticator(config.gateway_auth,client_key=client_key,agent_credentials=local_keys),
      observe=runtime.observe_gateway,measure=runtime.latency.record,timeline=runtime.latency,
      admission_check=runtime.admission)
    failure=asyncio.create_task(pool.failed.wait()) if pool is not None else None
    try:
      await run_servers([uvicorn_server(gateway,18084)],[status_task]+([failure] if failure else []))
    finally:
      runtime.inspector_ready=False
      if pool is None:await grpc_server.stop(2)
      else:
        await pool.stop()
        exhausted=pool.failed.is_set()
        failure.cancel()
        await asyncio.gather(failure,return_exceptions=True)
        if exhausted:raise RuntimeError('inspector_recovery_exhausted')
  finally:
    status.should_exit=True
    maintenance.cancel()
    await asyncio.gather(status_task,maintenance,return_exceptions=True)


def supervise(args):
  import sys
  from .supervisor import Supervisor
  base=[sys.executable,'-m','asr_proxy.selfhost.main','--config',args.config,'--state',args.state,
    '--generated',args.generated,'--assets',args.assets,'--dataplane-url',args.dataplane_url,
    '--inspector-host',args.inspector_host,'--proxy-host',args.proxy_host]
  for option in ('control_keys','policy_trust'):
    if getattr(args,option):base+=['--'+option.replace('_','-'),getattr(args,option)]
  return Supervisor(base+['serve-control'],base+['serve-dataplane']).run()


def main():
  parser=argparse.ArgumentParser(description='TrapDefense self-hosted AI Firewall')
  parser.add_argument('command',choices=['init','serve','serve-control','serve-dataplane',
    'client-key','render','policy-reset','activate-config'])
  parser.add_argument('--config',default='/config/deployment.yaml')
  parser.add_argument('--state',default='/state')
  parser.add_argument('--generated',default='/generated')
  parser.add_argument('--assets',default='/app/console/dist')
  parser.add_argument('--control-keys',default=os.environ.get('TD_CONTROL_KEYS'),help='Control-plane-only directory for the policy signing key')
  parser.add_argument('--policy-trust',default=os.environ.get('TD_POLICY_TRUST'),help='Directory holding the policy verification key')
  parser.add_argument('--dataplane-url',default=os.environ.get('TD_DATAPLANE_URL','http://127.0.0.1:18085'))
  parser.add_argument('--inspector-host',default=os.environ.get('TD_INSPECTOR_HOST','app'),help='Inspector host name Envoy dials')
  parser.add_argument('--proxy-host',default='envoy',help='Envoy host name the gateway probes')
  args=parser.parse_args()
  paths=plane_paths(args.state,args.control_keys,args.policy_trust)
  try:
    if args.command=='client-key':
      print(secret(Path(args.state)/'client.key'));return
    if args.command=='serve':
      raise SystemExit(supervise(args))
    if args.command=='serve-dataplane':
      # The data plane never reads deployment.yaml or console.sqlite: only the signed snapshot.
      holder=lock(args.state,'dataplane.lock')
      asyncio.run(serve_dataplane(args,paths));return
    config=load(args.config)
    holders=[]
    if args.command=='serve-control':holders=[lock(args.state,'control.lock')]
    elif args.command=='activate-config':
      holders=[lock(args.state,name) for name in ('control.lock','dataplane.lock','runtime.lock')]
    if args.command not in ('init',):
      from .operations import active_config, activate
      store=Store(Path(args.state),require_existing=True)
      config=active_config(store,config)
    if args.command=='init':
      password=getpass.getpass('New administrator password (12+ characters): ')
      if password!=getpass.getpass('Confirm password: '):raise ValueError('Passwords did not match')
      initialize(Path(args.state),Path(args.generated),config,password,paths)
      print('Initialized. Store your client key securely: docker compose run --rm control client-key')
    elif args.command=='activate-config':
      import socket
      try:
        connection=socket.create_connection(('envoy',18082),timeout=2)
      except OSError:pass
      else:
        connection.close()
        raise ValueError('Stop Envoy before activating settings')
      config=activate(store,config)
      atomic_write(Path(args.generated)/'envoy.yaml',envoy_config(config,args.inspector_host),mode=0o644)
      revision=publisher(paths).publish(config,seed_policy(store,config))
      store.audit('policy.snapshot_published',f'r{revision} after connection activation')
      print('Connection activated. Start the control plane, data plane and Envoy. Changed route mappings reset local route policies.')
    elif args.command=='policy-reset':
      with store.connect() as db:db.execute("DELETE FROM settings WHERE key='policy'")
      store.audit('policy.reset','Explicit CLI reset; new mappings will seed policy on startup')
      print('Saved policy reset. Accounts, keys and events were preserved.')
    elif args.command=='render':
      atomic_write(Path(args.generated)/'envoy.yaml',envoy_config(config,args.inspector_host),mode=0o644)
    else:asyncio.run(serve_control(args,config,paths))
  except (ValueError,OSError):
    # Configuration validation can include submitted secret values; keep stdout sanitized.
    raise SystemExit('Setup failed. Check configuration, file permissions and initialization state.') from None


if __name__=='__main__':main()
