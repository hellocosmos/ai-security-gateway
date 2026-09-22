"""Compare bounded gateway admission values against one synthetic SSE workload."""
import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import platform
import re
import ssl
import subprocess
import tempfile
import threading
import time
import httpx
import yaml
from examples.agent_workflow.stack import Stack, free_port
from .benchmark import sample, summary

CANDIDATES=(8,16,32,48)


def memory_mib(value):
  match=re.fullmatch(r'([0-9.]+)\s*([KMG]iB|B)',value.split('/')[0].strip())
  if match is None:return None
  return round(float(match[1])*{'B':1/(1024*1024),'KiB':1/1024,'MiB':1,'GiB':1024}[match[2]],2)


async def batch(url,key,concurrency,n,context):
  async with httpx.AsyncClient(verify=context,timeout=20,trust_env=False,
                               limits=httpx.Limits(max_connections=100)) as client:
    semaphore=asyncio.Semaphore(concurrency)
    async def one():
      async with semaphore:return await sample(client,url,key,'long')
    started=time.perf_counter()
    results=await asyncio.gather(*(one() for _ in range(n)))
    return results,(time.perf_counter()-started)*1000


def summarize(results,duration):
  ok=[r for r in results if r['status']==200 and r['complete']]
  return {'requests':len(results),'statuses':dict(Counter(str(r['status']) for r in results)),
          'complete_200':len(ok),'incomplete_200':sum(r['status']==200 and not r['complete'] for r in results),
          'batch_ms':round(duration,2),'completed_per_second':round(len(ok)*1000/duration,2),
          'first_content_ms':summary([r['first_content_ms'] for r in ok]),
          'completion_ms':summary([r['completion_ms'] for r in ok])}


def main():
  parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
  rows=[]
  with tempfile.TemporaryDirectory(prefix='td-latency045-') as base:
    for limit in CANDIDATES:
      candidate_base=Path(base)/str(limit);candidate_base.mkdir()
      stack=Stack(candidate_base,'model','synthetic-model',False)
      config_path=stack.directory/'deployment.yaml';config=yaml.safe_load(config_path.read_text())
      config['llm']['timeout_seconds']=10;config['max_body_bytes']=32768
      config['gateway_max_inflight']=limit
      config_path.write_text(yaml.safe_dump(config))
      override_path=stack.directory/'compose.yaml';override=yaml.safe_load(override_path.read_text())
      fixture=override['services']['workflow-fixture']
      fixture['volumes'][0]=str(Path(__file__).with_name('fixture.py').resolve())+':/fixture/server.py:ro'
      port=free_port();fixture['ports']=[f'127.0.0.1:{port}:443']
      override_path.write_text(yaml.safe_dump(override))
      context=ssl.create_default_context(cafile=str(stack.directory/'cert.pem'))
      context.check_hostname=False # Loopback port for generated local, pinned certificate.
      resources=[];sample_errors=[];stop=threading.Event()
      def sample_resources():
        while not stop.is_set():
          try:
            result=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}'],
              capture_output=True,text=True,timeout=15)
            if result.returncode:raise RuntimeError('Docker resource sample failed')
            for line in result.stdout.splitlines():
              value=json.loads(line)
              if value.get('Name','').startswith(stack.project):
                role = ('workflow-fixture' if '-workflow-fixture-' in value['Name']
                        else value['Name'].split('-')[-2])
                resources.append({'role':role,
                  'cpu_percent':float(value['CPUPerc'].rstrip('%')),
                  'memory_mib':memory_mib(value['MemUsage'])})
          except (ValueError,KeyError,RuntimeError,subprocess.TimeoutExpired):
            sample_errors.append('Resource sampling unavailable')
            return
          stop.wait(.5)
      worker=None
      try:
        stack.compose('build','app');stack.initialize('synthetic-target-only');stack.ready()
        worker=threading.Thread(target=sample_resources,daemon=True);worker.start()
        asyncio.run(batch(stack.url,stack.key('agent-a'),1,4,context)) # Warm-up excluded.
        runs=[]
        for concurrency,n in ((32,64),(64,128)):
          for repeat in range(2):
            result,duration=asyncio.run(batch(stack.url,stack.key('agent-a'),concurrency,n,context))
            runs.append({'concurrency':concurrency,'repeat':repeat+1,**summarize(result,duration)})
            print(limit,concurrency,repeat+1,runs[-1]['statuses'],flush=True)
        recovery,duration=asyncio.run(batch(stack.url,stack.key('agent-a'),1,4,context))
        token=stack.compose('exec','-T','app','python','-c',
          "from asr_proxy.console.store import Store; print(Store('/state',require_existing=True).create_session())").strip()
        snapshot=httpx.get(stack.origin+'/demo-api/operations',cookies={'td_demo_session':token},timeout=5).json()['latency']
        traces=snapshot['requests']
        if sample_errors or not resources:raise RuntimeError('Resource sampling unavailable')
        assert traces and all('run_id' not in trace for trace in traces)
        assert any(item['complete'] and item['response_body_wait_ms'] is not None for item in traces),traces
        assert all(row['incomplete_200']==0 for row in runs)
        assert all(row['complete_200']==4 for row in [summarize(recovery,duration)])
        rows.append({'gateway_max_inflight':limit,'runs':runs,'recovery':summarize(recovery,duration),
                     'sampled_peak_cpu_percent':{role:max(x['cpu_percent'] for x in resources if x['role']==role)
                       for role in ('app','envoy','workflow-fixture') if any(x['role']==role for x in resources)},
                     'sampled_peak_memory_mib':{role:max((x['memory_mib'] for x in resources
                       if x['role']==role and x['memory_mib'] is not None),default=None)
                       for role in ('app','envoy','workflow-fixture')},
                     'trace_count':len(traces),'sample_trace':next(x for x in traces if x['complete'])})
      finally:
        stop.set()
        if worker:worker.join(timeout=20)
        stack.cleanup()
    report={'kind':'synthetic_docker_admission_sweep','version':'0.45','host':platform.platform(),
      'cpu_count':os.cpu_count(),'fixture':'32 content chunks, 20ms between chunks',
      'body_limit_bytes':32768,'inspector_streams':16,'inspection_workers':4,
      'rows':rows,'scope':'one local run, no production capacity inference'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
