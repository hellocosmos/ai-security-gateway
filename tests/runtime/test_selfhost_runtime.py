"""Opt-in actual Docker package verification with an isolated synthetic destination."""
import os
from pathlib import Path
import socket
import subprocess
import time
from uuid import uuid4
import httpx
import pytest
import yaml

pytestmark=pytest.mark.skipif(os.environ.get('TD_SELFHOST_E2E')!='1',reason='Set TD_SELFHOST_E2E=1 to build and test Docker self-hosting')
ROOT=Path(__file__).parents[2]


def free_port():
  with socket.socket() as sock:
    sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


@pytest.mark.parametrize('mode',['passthrough_bearer','static_bearer','static_api_key','https_static_bearer'])
def test_package_lifecycle(tmp_path,mode):
  port,gateway_port=free_port(),free_port()
  origin=f'http://localhost:{port}'
  config=yaml.safe_load((ROOT/'deploy/selfhost/deployment.yaml').read_text())
  config['console_origin']=origin
  static=mode!='passthrough_bearer'
  secret_value=('sk-proj-'+'A1b2C3d4E5f6G7h8I9j0K1l2'
    if mode=='static_api_key' else 'synthetic-target-token')
  if mode in ('static_bearer','https_static_bearer'):
    config['target_auth']={'mode':'static_bearer','secret_file':'/state/destination.token'}
  elif mode=='static_api_key':
    config['target_auth']={'mode':'static_api_key','secret_file':'/state/destination.token','header':'x-api-key'}
  if mode.startswith('https'):
    config.update(upstream='https://fixture:8080',allow_plaintext_upstream=False)
  path=tmp_path/'deployment.yaml';path.write_text(yaml.safe_dump(config))
  env={**os.environ,'TD_CONSOLE_PORT':str(port),'TD_GATEWAY_PORT':str(gateway_port),'TD_CONFIG_FILE':str(path)}
  project='td-selfhost-test-'+uuid4().hex[:8]
  base=['docker','compose','-p',project,'-f',str(ROOT/'deploy/selfhost/compose.yaml'),'--profile','smoke']
  if mode.startswith('https'):
    for name in ('fixture','untrusted'):
      result=subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1',
        '-subj','/CN='+name,'-addext','subjectAltName=DNS:'+name,'-keyout',str(tmp_path/(name+'.key')),
        '-out',str(tmp_path/(name+'.crt'))],capture_output=True)
      assert result.returncode==0,'Synthetic certificate generation failed'
    ca=tmp_path/'ca.crt';ca.write_bytes((tmp_path/'fixture.crt').read_bytes())
    override=tmp_path/'tls.yaml'
    override.write_text(yaml.safe_dump({'services':{
      'envoy':{'volumes':[str(ca)+':/etc/ssl/certs/ca-certificates.crt:ro']},
      # The pytest directory and private key belong to the runner. With cap_drop=ALL,
      # container root cannot bypass its 0700/0600 permissions on Linux.
      'fixture':{'user':f'{os.getuid()}:{os.getgid()}', 'environment':{'TD_FIXTURE_CERT':'/cert/fixture.crt','TD_FIXTURE_KEY':'/cert/fixture.key'},
        'volumes':[str(tmp_path)+':/cert:ro']}}}))
    base.extend(['-f',str(override)])
  def compose(*args):
    result=subprocess.run([*base,*args],env=env,cwd=ROOT,text=True,capture_output=True,timeout=600)
    assert result.returncode==0, result.stderr[-3000:]
    return result.stdout.strip()
  def wait():
    until=time.monotonic()+60
    while time.monotonic()<until:
      try:
        if httpx.get(origin+'/demo-api/health',timeout=1).status_code==200:return
      except httpx.HTTPError:pass
      time.sleep(.5)
    pytest.fail('Console did not become healthy')
  password='synthetic-install-password-037'
  try:
    compose('build','app')
    compose('run','--rm','--no-deps','--entrypoint','python','app','-c',
      'from pathlib import Path; from asr_proxy.selfhost.main import initialize; from asr_proxy.selfhost.config import load; '
      f'initialize(Path("/state"),Path("/generated"),load("/config/deployment.yaml"),"{password}"); '
      f'from asr_proxy.inspection.pool import atomic_write; atomic_write(Path("/state/destination.token"),"{secret_value}")')
    compose('up','-d');wait()
    key=compose('exec','-T','app','cat','/state/client.key')
    if os.environ.get('GITHUB_ACTIONS')=='true':print('::add-mask::'+key,flush=True)
    headers={'x-td-client-key':key}
    if not static:headers['authorization']='Bearer synthetic-target-token'
    gateway=f'http://127.0.0.1:{gateway_port}'
    with httpx.Client(base_url=gateway,timeout=15) as c, httpx.Client(base_url=origin,timeout=5,
        headers={'origin':origin,'x-td-demo':'1'}) as admin:
      # Compose starts Envoy after app health, but its listener/DNS may not yet be ready.
      # Only this side-effect-free synthetic read is a readiness probe; the product never retries calls.
      deadline=time.monotonic()+30
      last_status=None
      while time.monotonic()<deadline:
        try:
          probe=c.post('/api/notes',headers=headers,json={'message':'readiness probe'})
          last_status=probe.status_code
          if last_status==200:break
          if last_status!=503:pytest.fail(f'Unexpected readiness status: {last_status}')
        except httpx.ConnectError:pass
        time.sleep(.5)
      else:pytest.fail(f'Inspection path did not become ready; last status: {last_status}')
      assert c.post('/api/notes',json={'message':'safe'}).status_code==401
      assert c.post('/api/notes',headers=headers,json={'message':'safe'}).status_code==200
      redact=c.post('/api/notes',headers=headers,json={'message':'Contact alex@example.com'})
      assert redact.status_code==200 and '[REDACTED]' in redact.text and 'alex@example.com' not in redact.text
      denied=c.post('/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'tools/call',
        'params':{'name':'notes.delete','arguments':{}}})
      assert denied.status_code==403
      assert c.post('/api/notes',headers={**headers,'authorization':'Bearer wrong'},json={}).status_code==(400 if static else 401)
      assert admin.post('/demo-api/login',json={'username':'admin','password':'1234'}).status_code==401
      assert admin.post('/demo-api/login',json={'username':'admin','password':password}).status_code==200
      timeline=admin.get('/demo-api/operations').json()['latency']
      assert timeline['requests']
      assert any(row['http_status']==200 and row['complete'] and row['response_body_wait_ms'] is not None
                 for row in timeline['requests'])
      assert all('run_id' not in row and 'message' not in row for row in timeline['requests'])
      assert key not in str(timeline) and 'alex@example.com' not in str(timeline)
      data=admin.get('/demo-api/overview').json()
      assert data['synthetic'] is False and data['scenarios']==[]
      expected='static_api_key' if mode=='static_api_key' else 'static_bearer' if static else 'passthrough_bearer'
      assert data['deployment']['target_auth']['mode']==expected
      assert 'secret_file' not in data['deployment']['target_auth']
      assert len(data['events'])>=(3 if static else 4)
      text=str(data['events'])
      assert key not in text and secret_value not in text and 'alex@example.com' not in text
      assert admin.post('/demo-api/scenarios/read',json={}).status_code==404
      assert admin.post('/demo-api/network',json={}).status_code in (404,405)
      assert admin.post('/demo-api/policy',headers={'origin':'https://untrusted.example'},json=data['policy']).status_code==403
      policy=data['policy'];policy['rules']['0:notes.read']='block'
      applied=admin.post('/demo-api/policy',json=policy)
      assert applied.status_code==200
      assert c.post('/api/notes',headers=headers,json={'message':'safe'}).status_code==403
      changed=admin.post('/demo-api/password',json={'current_password':password,'new_password':password+'-changed'})
      assert changed.status_code==200
      assert admin.get('/demo-api/session').status_code==401
      compose('restart','app','envoy');wait()
      assert compose('exec','-T','app','cat','/state/client.key')==key
      assert admin.post('/demo-api/login',json={'username':'admin','password':password+'-changed'}).status_code==200
      current=admin.get('/demo-api/policy').json()
      assert current['rules']['0:notes.read']=='block' and current['version']==applied.json()['version']
      # Restore allow then prove there is no direct-upstream fallback when Envoy is absent.
      current['rules']['0:notes.read']='allow'
      assert admin.post('/demo-api/policy',json=current).status_code==200
      compose('stop','envoy')
      assert c.post('/api/notes',headers=headers,json={'message':'safe'}).status_code==503
      compose('start','envoy')
      until=time.monotonic()+15
      while time.monotonic()<until:
        if c.post('/api/notes',headers=headers,json={'message':'safe'}).status_code==200:break
        time.sleep(.5)
      else:pytest.fail('Inspection path did not recover')
      if mode=='passthrough_bearer':
        workspace=admin.get('/demo-api/operations').json()
        candidate=workspace['active'];candidate['max_body_bytes']=32768
        stage=admin.post('/demo-api/operations/stage',json={'version':workspace['version'],'config':candidate})
        assert stage.status_code==200 and stage.json()['restart_required']
        preview=admin.post('/demo-api/operations/preview',json={
          'route':0,'body':{'message':'Contact alex@example.com'},'policy':admin.get('/demo-api/policy').json()})
        assert preview.status_code==200 and preview.json()['decision']=='redact'
        diagnostic=admin.post('/demo-api/operations/diagnose',json={}).json()
        assert diagnostic['status']=='listeners_ready' and diagnostic['authentication']=='not_tested'
        # A second process cannot activate a new generation while the gateway serves.
        rejected=subprocess.run([*base,'run','--rm','app','activate-config'],env=env,
          cwd=ROOT,text=True,capture_output=True,timeout=60)
        assert rejected.returncode!=0
        assert admin.get('/demo-api/operations').json()['active']['max_body_bytes']==1048576
        compose('stop','app')
        envoy_rejected=subprocess.run([*base,'run','--rm','app','activate-config'],env=env,
          cwd=ROOT,text=True,capture_output=True,timeout=60)
        assert envoy_rejected.returncode!=0
        compose('stop','envoy')
        compose('run','--rm','app','activate-config')
        compose('up','-d','app','envoy');wait()
        assert admin.post('/demo-api/login',json={'username':'admin','password':password+'-changed'}).status_code==200
        activated=admin.get('/demo-api/operations').json()
        assert activated['active']['max_body_bytes']==32768 and not activated['restart_required']
        # Persist across a further restart, then recover the prior configuration.
        compose('restart','app','envoy');wait()
        assert admin.get('/demo-api/operations').json()['active']['max_body_bytes']==32768
        restored=admin.post('/demo-api/operations/restore',json={
          'version':activated['version'],'revision':activated['history'][0]['revision']})
        assert restored.status_code==200
        compose('stop','app','envoy');compose('run','--rm','app','activate-config')
        compose('up','-d','app','envoy');wait()
        assert admin.get('/demo-api/operations').json()['active']['max_body_bytes']==1048576
      if mode.startswith('https'):
        ca.write_bytes((tmp_path/'untrusted.crt').read_bytes())
        compose('restart','envoy')
        assert c.post('/api/notes',headers=headers,json={'message':'safe'}).status_code==503
  except BaseException:
    # Access logging is disabled; retain bounded component errors for CI diagnosis.
    print(compose('logs','--no-color','--tail','30','app','envoy','fixture'),flush=True)
    raise
  finally:
    # The random project and all its volumes were created exclusively by this test.
    compose('down','-v','--remove-orphans')


def test_optional_inspector_process_pool(tmp_path):
  port,gateway_port=free_port(),free_port()
  origin=f'http://localhost:{port}'
  config=yaml.safe_load((ROOT/'deploy/selfhost/deployment.yaml').read_text())
  config.update(console_origin=origin,inspector_replicas=2,gateway_admission_wait_ms=100)
  path=tmp_path/'deployment.yaml'
  path.write_text(yaml.safe_dump(config))
  env={**os.environ,'TD_CONSOLE_PORT':str(port),'TD_GATEWAY_PORT':str(gateway_port),
    'TD_CONFIG_FILE':str(path)}
  project='td-pool-test-'+uuid4().hex[:8]
  base=['docker','compose','-p',project,'-f',str(ROOT/'deploy/selfhost/compose.yaml'),'--profile','smoke']
  def compose(*args):
    result=subprocess.run([*base,*args],env=env,cwd=ROOT,text=True,capture_output=True,timeout=600)
    assert result.returncode==0,result.stderr[-3000:]
    return result.stdout.strip()
  try:
    compose('build','app')
    compose('run','--rm','--no-deps','--entrypoint','python','app','-c',
      'from pathlib import Path; from asr_proxy.selfhost.main import initialize; '
      'from asr_proxy.selfhost.config import load; '
      'initialize(Path("/state"),Path("/generated"),load("/config/deployment.yaml"),"synthetic-pool-password")')
    compose('up','-d')
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
      try:
        if httpx.get(origin+'/demo-api/health',timeout=1).status_code==200:break
      except httpx.HTTPError:pass
      time.sleep(.5)
    else:pytest.fail('Pooled console did not become ready')
    key=compose('exec','-T','app','cat','/state/client.key')
    headers={'x-td-client-key':key,'authorization':'Bearer synthetic-target-token'}
    with httpx.Client(base_url=f'http://127.0.0.1:{gateway_port}',timeout=15) as gateway, \
        httpx.Client(base_url=origin,timeout=5,headers={'origin':origin,'x-td-demo':'1'}) as admin:
      deadline=time.monotonic()+30
      while time.monotonic()<deadline:
        result=gateway.post('/api/notes',headers=headers,json={'message':'safe'})
        if result.status_code==200:break
        assert result.status_code==503
        time.sleep(.5)
      else:pytest.fail('Pooled inspection path did not become ready')
      assert admin.post('/demo-api/login',json={'username':'admin','password':'synthetic-pool-password'}).status_code==200
      assert admin.get('/demo-api/overview').json()['deployment']['inspector_replicas']==2
      assert admin.get('/demo-api/operations').json()['latency']['inspector_timing_available'] is False
      redact=gateway.post('/api/notes',headers=headers,json={'message':'Contact alex@example.com'})
      assert redact.status_code==200 and '[REDACTED]' in redact.text and 'alex@example.com' not in redact.text
      policy=admin.get('/demo-api/policy').json()
      policy['rules']['0:notes.read']='block'
      assert admin.post('/demo-api/policy',json=policy).status_code==200
      # Multiple workers must refresh the same versioned policy before another call.
      assert all(gateway.post('/api/notes',headers=headers,json={'message':'safe'}).status_code==403
        for _ in range(4))
      def children():
        script='''import json
from pathlib import Path
items=[]
for path in Path('/proc').iterdir():
  if not path.name.isdigit():continue
  try:args=path.joinpath('cmdline').read_bytes().decode(errors='ignore').split('\\0')
  except OSError:continue
  if 'asr_proxy.selfhost.inspector_pool' in args and '--index' in args:
    items.append((int(path.name),args[args.index('--index')+1]))
print(json.dumps(items))'''
        import json
        return {index:pid for pid,index in json.loads(compose('exec','-T','app','python','-c',script))}
      before=children()
      assert set(before)=={'0','1'}
      compose('exec','-T','app','python','-c',f'import os,signal;os.kill({before["0"]},signal.SIGKILL)')
      deadline=time.monotonic()+15
      while time.monotonic()<deadline:
        after=children()
        if set(after)=={'0','1'} and after['0']!=before['0']:break
        time.sleep(.5)
      else:pytest.fail('Supervisor did not replace failed inspector')
      deadline=time.monotonic()+10
      while time.monotonic()<deadline:
        statuses=[gateway.post('/api/notes',headers=headers,json={'message':'safe'}).status_code
          for _ in range(4)]
        assert all(status in (403,500,503,504) for status in statuses),statuses
        if statuses==[403]*4:break
        time.sleep(.5)
      else:pytest.fail('Pooled policy enforcement did not recover')
      overview=admin.get('/demo-api/overview').json()
      assert len(overview['events'])>=6
      assert key not in str(overview['events']) and 'alex@example.com' not in str(overview['events'])
  except BaseException:
    print(compose('logs','--no-color','--tail','30','app','envoy','fixture'),flush=True)
    raise
  finally:
    compose('down','-v','--remove-orphans')
