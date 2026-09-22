"""Initialize once, then serve the self-hosted Docker package."""
import argparse
import asyncio
import getpass
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
from .runtime import SelfhostRuntime


def initialize(state, generated, config, password):
  state.mkdir(parents=True,exist_ok=True,mode=0o700)
  if (state/'console.sqlite').exists():raise ValueError('Already initialized; existing credentials were preserved')
  if not 12<=len(password)<=128:raise ValueError('Use an administrator password of 12–128 characters')
  for name, data in [('attestation.key',secrets.token_bytes(48)),('client.key',secrets.token_urlsafe(36).encode())]:
    atomic_write(state/name,data)
  generated.mkdir(parents=True,exist_ok=True)
  atomic_write(generated/'envoy.yaml',envoy_config(config),mode=0o644)
  Store(state,bootstrap_password=password).audit('installation.initialized','Self-hosted AI Firewall')


def secret(path):
  path=Path(path)
  if path.stat().st_mode & 0o077:raise ValueError('Secret files must be owner-readable only (0600)')
  value=path.read_text().strip()
  if not value or any(c.isspace() for c in value):raise ValueError('Invalid secret file format')
  return value


async def serve(args, config):
  state=Path(args.state)
  runtime=SelfhostRuntime(state,config)
  client_key=secret(state/'client.key')
  if len(client_key)<32:raise ValueError('Invalid client key')
  target_secret=secret(config.target_auth.secret_file) if config.target_auth.secret_file else None
  atomic_write(Path(args.generated)/'envoy.yaml',envoy_config(config),mode=0o644)
  grpc_server=grpc.aio.server(maximum_concurrent_rpcs=32)
  rpc.add_ExternalProcessorServicer_to_server(ConsoleProcessor(runtime),grpc_server)
  if not grpc_server.add_insecure_port('0.0.0.0:18081'):raise RuntimeError('Inspector port unavailable')
  @asynccontextmanager
  async def lifecycle(app):
    await grpc_server.start()
    runtime.inspector_ready=True
    runtime.store.audit('installation.started','Self-hosted adapter, inspector and console')
    try:yield
    finally:
      runtime.inspector_ready=False
      await grpc_server.stop(2)
  console=create_app(state,seed=False,runtime_factory=lambda *a,**k:runtime,
    lifespan=lifecycle,console_origin=config.console_origin)
  console.mount('/',StaticFiles(directory=args.assets,html=True),name='console')
  from .auth import GatewayAuthenticator
  from .agent_credentials import AgentCredentials
  local_keys=AgentCredentials(state/'agent-credentials.sqlite',runtime.broker,runtime.broker_tenant) if config.gateway_auth.mode=='agent_key' else None
  gateway=create_gateway(config,client_key,runtime.key,target_secret=target_secret,
    authenticator=GatewayAuthenticator(config.gateway_auth,client_key=client_key,agent_credentials=local_keys),
    observe=runtime.observe_gateway,measure=runtime.latency.record,timeline=runtime.latency)
  servers=[uvicorn.Server(uvicorn.Config(app,host='0.0.0.0',port=port,access_log=False,
    ws='none',timeout_graceful_shutdown=3,limit_concurrency=64)) for app,port in [(console,18080),(gateway,18084)]]
  # One signal handler coordinates both listeners and the gRPC service.
  for server in servers:server.capture_signals=lambda: nullcontext()
  loop=asyncio.get_running_loop()
  import signal
  def stop():
    for server in servers:server.should_exit=True
  for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,stop)
  tasks=[asyncio.create_task(server.serve()) for server in servers]
  try:
    await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
  finally:
    stop()
    await asyncio.gather(*tasks)


def main():
  parser=argparse.ArgumentParser(description='TrapDefense self-hosted AI Firewall')
  parser.add_argument('command',choices=['init','serve','client-key','render','policy-reset','activate-config'])
  parser.add_argument('--config',default='/config/deployment.yaml')
  parser.add_argument('--state',default='/state')
  parser.add_argument('--generated',default='/generated')
  parser.add_argument('--assets',default='/app/console/dist')
  args=parser.parse_args()
  try:
    if args.command=='client-key':
      print(secret(Path(args.state)/'client.key'));return
    config=load(args.config)
    if args.command in ('serve','activate-config'):
      import fcntl
      runtime_lock=open(Path(args.state)/'runtime.lock','a')
      try:fcntl.flock(runtime_lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
      except BlockingIOError:raise ValueError('Stop the app before activating settings') from None
    if args.command not in ('init',):
      from .operations import active_config, activate
      store=Store(Path(args.state),require_existing=True)
      config=active_config(store,config)
    if args.command=='init':
      password=getpass.getpass('New administrator password (12+ characters): ')
      if password!=getpass.getpass('Confirm password: '):raise ValueError('Passwords did not match')
      initialize(Path(args.state),Path(args.generated),config,password)
      print('Initialized. Store your client key securely: docker compose run --rm app client-key')
    elif args.command=='activate-config':
      import socket
      try:
        connection=socket.create_connection(('envoy',18082),timeout=2)
      except OSError:pass
      else:
        connection.close()
        raise ValueError('Stop Envoy before activating settings')
      config=activate(store,config)
      atomic_write(Path(args.generated)/'envoy.yaml',envoy_config(config),mode=0o644)
      print('Connection activated. Start both app and Envoy. Changed route mappings reset local route policies.')
    elif args.command=='policy-reset':
      store=Store(Path(args.state),require_existing=True)
      with store.connect() as db:db.execute("DELETE FROM settings WHERE key='policy'")
      store.audit('policy.reset','Explicit CLI reset; new mappings will seed policy on startup')
      print('Saved policy reset. Accounts, keys and events were preserved.')
    elif args.command=='render':
      atomic_write(Path(args.generated)/'envoy.yaml',envoy_config(config),mode=0o644)
    else:asyncio.run(serve(args,config))
  except (ValueError,OSError):
    # Configuration validation can include submitted secret values; keep stdout sanitized.
    raise SystemExit('Setup failed. Check configuration, file permissions and initialization state.') from None


if __name__=='__main__':main()
