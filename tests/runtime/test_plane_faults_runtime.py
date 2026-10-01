"""Opt-in fault injection on the real split Compose stack.

Invariant for every scenario: an allowed call is served only through inspection,
a blocked call never reaches the destination, and an unavailable data plane never
falls back to an uninspected 200.
"""
import json
import os
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import yaml

pytestmark=pytest.mark.skipif(os.environ.get('TD_FAULT_E2E')!='1',reason='Set TD_FAULT_E2E=1 to inject faults into Docker self-hosting')
ROOT=Path(__file__).parents[2]
PASSWORD='synthetic-fault-password-047'
STATUS="import json,urllib.request\ntry:print(urllib.request.urlopen('http://127.0.0.1:18085/_trapdefense/status',timeout=2).read().decode())\nexcept Exception as e:print(json.dumps({'error':type(e).__name__}))"


def free_port():
  with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


@pytest.fixture(scope='module')
def stack(tmp_path_factory):
  tmp=tmp_path_factory.mktemp('faults')
  port,gateway_port=free_port(),free_port()
  origin=f'http://localhost:{port}'
  config=yaml.safe_load((ROOT/'deploy/selfhost/deployment.yaml').read_text())
  config['console_origin']=origin
  path=tmp/'deployment.yaml';path.write_text(yaml.safe_dump(config))
  env={**os.environ,'TD_CONSOLE_PORT':str(port),'TD_GATEWAY_PORT':str(gateway_port),'TD_CONFIG_FILE':str(path)}
  base=['docker','compose','-p','td-fault-test-'+uuid4().hex[:8],'-f',str(ROOT/'deploy/selfhost/compose.yaml'),'--profile','smoke']
  def compose(*args,check=True,timeout=600):
    result=subprocess.run([*base,*args],env=env,cwd=ROOT,text=True,capture_output=True,timeout=timeout)
    if check:assert result.returncode==0,result.stderr[-3000:]
    return result.stdout.strip()
  try:
    compose('build','app')
    compose('run','--rm','--no-deps','--entrypoint','python','app','-c',
      'from pathlib import Path; from asr_proxy.selfhost.main import initialize; '
      'from asr_proxy.selfhost.config import load; '
      f'initialize(Path("/state"),Path("/generated"),load("/config/deployment.yaml"),"{PASSWORD}")')
    compose('up','-d')
    key=compose('exec','-T','app','cat','/state/client.key')
    value={'compose':compose,'origin':origin,'gateway':f'http://127.0.0.1:{gateway_port}',
      'headers':{'x-td-client-key':key,'authorization':'Bearer synthetic-target-token'}}
    wait_console(value);wait_served(value)
    yield value
  except BaseException:
    print(compose('logs','--no-color','--tail','60','app','dataplane','envoy',check=False),flush=True)
    raise
  finally:
    compose('down','-v','--remove-orphans',check=False)


def wait_console(stack,seconds=60):
  until=time.monotonic()+seconds
  while time.monotonic()<until:
    try:
      if httpx.get(stack['origin']+'/demo-api/health',timeout=1).status_code==200:return
    except httpx.HTTPError:pass
    time.sleep(.5)
  pytest.fail('Console did not become healthy')


def call(stack,tool='read',message='safe'):
  """Return the HTTP status, or None when the gateway refused the connection."""
  with httpx.Client(base_url=stack['gateway'],timeout=15) as client:
    try:
      if tool=='read':
        return client.post('/api/notes',headers=stack['headers'],json={'message':message}).status_code
      return client.post('/mcp',headers=stack['headers'],json={'jsonrpc':'2.0','id':1,'method':'tools/call',
        'params':{'name':'notes.delete','arguments':{}}}).status_code
    except httpx.TransportError:
      return None


def wait_served(stack,seconds=60):
  # Side-effect-free synthetic read used only as a readiness probe.
  until=time.monotonic()+seconds
  while time.monotonic()<until:
    status=call(stack)
    if status==200:return
    assert status in (None,503),status
    time.sleep(.5)
  pytest.fail('Inspection path did not become ready')


def assert_enforcing(stack,rounds=5):
  for _ in range(rounds):
    assert call(stack)==200
    assert call(stack,'delete')==403


def dataplane_status(stack):
  return json.loads(stack['compose']('exec','-T','dataplane','python','-c',STATUS))


@contextmanager
def admin(stack):
  with httpx.Client(base_url=stack['origin'],timeout=5,headers={'origin':stack['origin'],'x-td-demo':'1'}) as client:
    assert client.post('/demo-api/login',json={'username':'admin','password':PASSWORD}).status_code==200
    yield client


def spool_lines(stack):
  return int(stack['compose']('exec','-T','dataplane','sh','-c',
    'cat /state/dataplane/events/*/*.jsonl 2>/dev/null | wc -l'))


def test_f1_control_crash_does_not_stop_enforcement(stack):
  with admin(stack) as client:before=len(client.get('/demo-api/events').json())
  stack['compose']('kill','-s','SIGKILL','app')
  assert_enforcing(stack)
  status=dataplane_status(stack)
  assert status['ready'] and status['snapshot']['revision']>=1
  stack['compose']('start','app');wait_console(stack)
  # Evidence produced while the console was down is ingested after it returns.
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
    with admin(stack) as client:events=client.get('/demo-api/events').json()
    if len(events)>=before+10:break
    time.sleep(.5)
  else:pytest.fail('Evidence from the control-plane outage was not ingested')


def test_f2_console_database_lock_does_not_delay_inspection(stack):
  stack['compose']('exec','-d','app','python','-c',
    "import sqlite3,time;d=sqlite3.connect('/state/console.sqlite');d.execute('BEGIN EXCLUSIVE');time.sleep(12)")
  time.sleep(1)
  for _ in range(5):
    started=time.monotonic()
    assert call(stack)==200 and call(stack,'delete')==403
    assert time.monotonic()-started<2
  time.sleep(12)


def test_f4_tampered_snapshot_keeps_last_known_good(stack):
  kept=dataplane_status(stack)['snapshot']['revision']
  stack['compose']('exec','-T','app','sh','-c',
    "python -c \"import json;p='/state/policy/current.json';e=json.load(open(p));"
    "e['payload']['policy']['rules']['0:notes.read']='block';open(p,'w').write(json.dumps(e))\"")
  deadline=time.monotonic()+10
  while time.monotonic()<deadline and not dataplane_status(stack).get('last_rejection'):time.sleep(.5)
  status=dataplane_status(stack)
  assert status['last_rejection']['reason']=='policy_snapshot_signature_invalid'
  assert status['snapshot']['revision']==kept
  assert_enforcing(stack)
  # A legitimate change republishes a verified snapshot and is enforced within the poll interval.
  with admin(stack) as client:
    policy=client.get('/demo-api/policy').json();policy['rules']['0:notes.read']='block'
    assert client.post('/demo-api/policy',json=policy).status_code==200
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and call(stack)!=403:time.sleep(.5)
    assert call(stack)==403
    policy=client.get('/demo-api/policy').json();policy['rules']['0:notes.read']='allow'
    assert client.post('/demo-api/policy',json=policy).status_code==200
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and call(stack)!=200:time.sleep(.5)
    assert call(stack)==200
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
      if any(row['event']=='dataplane.snapshot_rejected' for row in client.get('/demo-api/audit').json()):break
      time.sleep(.5)
    else:pytest.fail('Snapshot rejection was not audited by the control plane')


def test_f5_missing_snapshot_at_boot_never_serves(stack):
  compose=stack['compose']
  compose('stop','dataplane')
  compose('exec','-T','app','mv','/state/policy/current.json','/state/policy/held.json')
  compose('start','dataplane')
  try:
    for _ in range(6):
      assert call(stack) in (None,503)
      assert call(stack,'delete') in (None,503)
      time.sleep(.5)
  finally:
    compose('exec','-T','app','mv','/state/policy/held.json','/state/policy/current.json')
  wait_served(stack)
  assert_enforcing(stack,2)


def test_f10_envoy_down_has_no_direct_fallback(stack):
  compose=stack['compose']
  lines=spool_lines(stack)
  compose('stop','envoy')
  try:
    for _ in range(3):
      assert call(stack)==503 and call(stack,'delete')==503
  finally:
    compose('start','envoy')
  wait_served(stack)
  assert_enforcing(stack,2)
  assert spool_lines(stack)>lines
