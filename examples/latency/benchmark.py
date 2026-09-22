"""Run with python -m examples.latency.benchmark --output report.json.

Owns and cleans one isolated Docker stack. No live API key or paid calls.
"""
import argparse
import asyncio
from collections import Counter
import json
import math
import os
from pathlib import Path
import platform
import ssl
import subprocess
import tempfile
import threading
import time
import httpx
import yaml
from examples.agent_workflow.stack import Stack, free_port


def summary(values):
  values=sorted(v for v in values if v is not None)
  return {'n':len(values),**{name:round(values[max(0,math.ceil(len(values)*p)-1)],2) if values else None
    for name,p in [('p50',.5),('p95',.95),('max',1)]}}


async def sample(client,url,key,scenario):
  started=time.perf_counter();first=None;content='';size=0;done=False
  try:
    async with client.stream('POST',url+'/v1/chat/completions',headers={'Authorization':'Bearer '+key},
        json={'model':'synthetic-model','messages':[{'role':'user','content':scenario}],'stream':True}) as response:
      async for line in response.aiter_lines():
        size+=len(line.encode())
        if line=='data: [DONE]':done=True
        if response.status_code!=200 or not line.startswith('data: {'):continue
        value=json.loads(line[6:])
        for choice in value.get('choices',[]):
          text=choice.get('delta',{}).get('content','')
          if text and first is None:first=(time.perf_counter()-started)*1000
          content+=text
      return {'status':response.status_code,'first_content_ms':first,'completion_ms':(time.perf_counter()-started)*1000,
        'bytes':size,'complete':done,'pii_visible':'alex@example.com' in content}
  except (httpx.HTTPError,ValueError):
    return {'status':'client_error','first_content_ms':first,'completion_ms':(time.perf_counter()-started)*1000,
      'bytes':size,'complete':False,'pii_visible':'alex@example.com' in content}


async def matrix(stack,direct,context):
  rows=[]
  async with httpx.AsyncClient(verify=context,timeout=20,trust_env=False,limits=httpx.Limits(max_connections=100)) as client:
    for scenario in ('short','long'):
      for concurrency in (1,8,32):
        for name,url,key in [('direct',direct,'synthetic-target-only'),('gateway',stack.url,stack.key('agent-a'))]:
          await sample(client,url,key,scenario) # Warm-up excluded.
          semaphore=asyncio.Semaphore(concurrency)
          async def one():
            async with semaphore:return await sample(client,url,key,scenario)
          results=await asyncio.gather(*(one() for _ in range(max(12,concurrency*2))))
          ok=[r for r in results if r['status']==200 and r['complete']]
          rows.append({'path':name,'scenario':scenario,'concurrency':concurrency,'requests':len(results),
            'statuses':dict(Counter(str(r['status']) for r in results)),'successful':len(ok),
            'first_content_ms':summary([r['first_content_ms'] for r in ok]),
            'completion_ms':summary([r['completion_ms'] for r in ok]),'response_bytes':summary([r['bytes'] for r in ok])})
          print(name,scenario,concurrency,len(ok),'/',len(results),flush=True)
    pressure=await asyncio.gather(*(sample(client,stack.url,stack.key('agent-a'),'long') for _ in range(64)))
    checks={scenario:await sample(client,stack.url,stack.key('agent-a'),scenario) for scenario in ('pii','limit','timeout')}
    checks['invalid_credential']=await sample(client,stack.url,'invalid-synthetic','short')
    assert checks['pii']['status']==200 and checks['pii']['complete'] and not checks['pii']['pii_visible']
    for name in ('limit','timeout','invalid_credential'):
      assert checks[name]['status']!=200 and checks[name]['first_content_ms'] is None,checks
    return rows,{'statuses':dict(Counter(str(r['status']) for r in pressure)),
      'incomplete_successes':sum(r['status']==200 and not r['complete'] for r in pressure)},checks


def main():
  parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
  with tempfile.TemporaryDirectory(prefix='td-latency044-') as base:
    stack=Stack(Path(base),'model','synthetic-model',False)
    config_path=stack.directory/'deployment.yaml';config=yaml.safe_load(config_path.read_text())
    config['llm']['timeout_seconds']=10;config['max_body_bytes']=32768
    config_path.write_text(yaml.safe_dump(config))
    override_path=stack.directory/'compose.yaml';override=yaml.safe_load(override_path.read_text())
    fixture=override['services']['workflow-fixture']
    fixture['volumes'][0]=str(Path(__file__).with_name('fixture.py').resolve())+':/fixture/server.py:ro'
    port=free_port();fixture['ports']=[f'127.0.0.1:{port}:443']
    override_path.write_text(yaml.safe_dump(override))
    # Trust only the generated local fixture certificate; hostname is checked via its SAN.
    context=ssl.create_default_context(cafile=str(stack.directory/'cert.pem'))
    context.check_hostname=False # loopback tunnel; certificate chain still pinned to the unique fixture CA.
    resources=[];stop=threading.Event()
    def stats():
      while not stop.is_set():
        result=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}'],capture_output=True,text=True,timeout=15)
        for line in result.stdout.splitlines():
          value=json.loads(line)
          if value.get('Name','').startswith(stack.project):
            resources.append({'Name':value['Name'].split('-')[-2],
              **{k:value[k] for k in ('CPUPerc','MemUsage')}})
        stop.wait(1)
    worker=None
    try:
      stack.compose('build','app');stack.initialize('synthetic-target-only');stack.ready()
      worker=threading.Thread(target=stats,daemon=True);worker.start()
      rows,pressure,checks=asyncio.run(matrix(stack,f'https://127.0.0.1:{port}',context))
      token=stack.compose('exec','-T','app','python','-c',
        "from asr_proxy.console.store import Store; print(Store('/state',require_existing=True).create_session())").strip()
      snapshot=httpx.get(stack.origin+'/demo-api/operations',cookies={'td_demo_session':token}).json()['latency']
      assert all(row['samples']>0 for row in snapshot['series']),snapshot
      report={'kind':'synthetic_docker_envoy_sse','version':'0.44','host':platform.platform(),
        'cpu_count':os.cpu_count(),'docker':json.loads(subprocess.check_output(['docker','info','--format','{{json .}}'],text=True)),
        'limits':{'body_bytes':32768,'model_timeout_seconds':10,'gateway_slots':32,'inspector_streams':16,'workers':4},
        'latency_snapshot':snapshot,'matrix':rows,'pressure_64':pressure,'checks':checks,'resources':resources}
      # Keep environment sizing, never daemon registry/account/network details.
      report['docker']={k:report['docker'].get(k) for k in ('NCPU','MemTotal','Architecture','ServerVersion')}
      args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    finally:
      stop.set()
      if worker:worker.join(timeout=20)
      stack.cleanup()


if __name__=='__main__':main()
