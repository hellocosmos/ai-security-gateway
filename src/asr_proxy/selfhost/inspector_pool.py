"""Supervise optional self-hosted inspection processes on one Docker host."""
import argparse
import asyncio
import os
from pathlib import Path
import subprocess
import sys

import grpc
import httpx
import uvicorn
from fastapi import FastAPI
from envoy.service.ext_proc.v3 import external_processor_pb2_grpc as rpc

from asr_proxy.console.dataplane import ConsoleProcessor
from asr_proxy.console.store import Store
from asr_proxy.inspection.server import watch_parent
from .config import load
from .operations import active_config
from .runtime import SelfhostRuntime


GRPC_BASE = 18120
HEALTH_BASE = 18130


async def inspector_worker(args):
  if os.getppid() != args.parent_pid:
    raise RuntimeError('inspector_parent_unavailable')
  state = Path(args.state)
  deployment = active_config(Store(state, require_existing=True), load(args.config))
  runtime = SelfhostRuntime(state, deployment)
  server = grpc.aio.server(maximum_concurrent_rpcs=32)
  rpc.add_ExternalProcessorServicer_to_server(ConsoleProcessor(runtime), server)
  if not server.add_insecure_port(f'0.0.0.0:{GRPC_BASE + args.index}'):
    raise RuntimeError('inspector_grpc_bind_failed')
  await server.start()
  app = FastAPI()

  @app.get('/_trapdefense/health')
  def health():
    return {'status': 'ready'}

  web = uvicorn.Server(uvicorn.Config(app, host='0.0.0.0', port=HEALTH_BASE + args.index,
    access_log=False, timeout_graceful_shutdown=3, ws='none'))
  watcher = asyncio.create_task(watch_parent(web, args.parent_pid))
  try:
    await web.serve()
  finally:
    watcher.cancel()
    await asyncio.gather(watcher, return_exceptions=True)
    await server.stop(2)


class SelfhostInspectorPool:
  def __init__(self, replicas, state, config, on_health=None):
    self.replicas = replicas
    self.state = str(state)
    self.config = str(config)
    self.members = [None] * replicas
    self.restarts = [0] * replicas
    self.failed = asyncio.Event()
    self.monitor_task = None
    self.stopping = False
    self.on_health = on_health

  def spawn(self, index):
    process = subprocess.Popen([sys.executable, '-m', 'asr_proxy.selfhost.inspector_pool',
      '--state', self.state, '--config', self.config, '--index', str(index),
      '--parent-pid', str(os.getpid())])
    self.members[index] = process

  async def healthy(self, index):
    process = self.members[index]
    if process is None or process.poll() is not None:
      return False
    try:
      async with httpx.AsyncClient(timeout=.5, trust_env=False) as client:
        response = await client.get(f'http://127.0.0.1:{HEALTH_BASE + index}/_trapdefense/health')
      reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', GRPC_BASE + index), .5)
      writer.close()
      await writer.wait_closed()
      return response.status_code == 200
    except (httpx.HTTPError, OSError, TimeoutError):
      return False

  async def ready(self, index, seconds=30):
    deadline = asyncio.get_running_loop().time() + seconds
    while asyncio.get_running_loop().time() < deadline:
      if await self.healthy(index):
        return True
      if self.members[index].poll() is not None:
        return False
      await asyncio.sleep(.2)
    return False

  async def start(self):
    try:
      for index in range(self.replicas):
        self.spawn(index)
        if not await self.ready(index):
          raise RuntimeError('inspector_startup_failed')
      if self.on_health is not None:
        self.on_health(True)
      self.monitor_task = asyncio.create_task(self.monitor())
    except BaseException:
      await self.stop()
      raise

  async def monitor(self):
    misses = [0] * self.replicas
    while not self.stopping:
      await asyncio.sleep(1)
      for index in range(self.replicas):
        if await self.healthy(index):
          misses[index] = 0
          continue
        misses[index] += 1
        if self.on_health is not None:
          self.on_health(False)
        if misses[index] < 3:
          continue
        await self.terminate(index)
        if self.restarts[index] >= 3:
          self.failed.set()
          return
        self.restarts[index] += 1
        self.spawn(index)
        if not await self.ready(index):
          await self.terminate(index)
          self.failed.set()
          return
        misses[index] = 0
      if self.on_health is not None and not any(misses):
        self.on_health(True)

  async def terminate(self, index):
    process = self.members[index]
    if process is None:
      return
    if process.poll() is None:
      process.terminate()
      try:
        await asyncio.to_thread(process.wait, 5)
      except subprocess.TimeoutExpired:
        process.kill()
        await asyncio.to_thread(process.wait, 2)
    self.members[index] = None

  async def stop(self):
    self.stopping = True
    if self.on_health is not None:
      self.on_health(False)
    if self.monitor_task is not None:
      self.monitor_task.cancel()
      await asyncio.gather(self.monitor_task, return_exceptions=True)
    await asyncio.gather(*(self.terminate(index) for index in range(self.replicas)))


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--state', required=True)
  parser.add_argument('--config', required=True)
  parser.add_argument('--index', required=True, type=int, choices=range(4))
  parser.add_argument('--parent-pid', required=True, type=int)
  args = parser.parse_args()
  asyncio.run(inspector_worker(args))


if __name__ == '__main__':
  main()
