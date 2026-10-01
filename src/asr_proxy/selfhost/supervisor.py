"""Single-container compatibility: run the control and data plane as separate processes.

A control-plane exit restarts only the control plane. A data-plane exit stops
the container so the orchestrator restarts the enforcement path. Isolation
guarantees are documented for the split Compose deployment; this wrapper keeps
the local and 0.46-style single service usable.
"""
import json
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone


def log(event, **fields):
  print(json.dumps({'ts': datetime.now(timezone.utc).isoformat(), 'event': event, **fields},
    separators=(',', ':')), file=sys.stderr, flush=True)


class Supervisor:
  def __init__(self, control, dataplane, *, max_backoff=30.0, stable_after=60.0, poll=0.5):
    self.commands = {'control': control, 'dataplane': dataplane}
    self.processes = {}
    self.max_backoff, self.stable_after, self.poll = max_backoff, stable_after, poll
    self.stopping = False
    self.control_restarts = 0

  def start(self, name):
    self.processes[name] = subprocess.Popen(self.commands[name])
    self.started = getattr(self, 'started', {})
    self.started[name] = time.monotonic()
    log('plane.started', plane=name, pid=self.processes[name].pid)

  def stop(self, *_):
    self.stopping = True

  def terminate(self, timeout=5):
    for process in self.processes.values():
      if process.poll() is None: process.terminate()
    deadline = time.monotonic() + timeout
    for process in self.processes.values():
      try:
        process.wait(max(deadline - time.monotonic(), 0))
      except subprocess.TimeoutExpired:
        process.kill()
        process.wait()

  def run(self, *, install_signals=True):
    if install_signals:
      for sig in (signal.SIGINT, signal.SIGTERM): signal.signal(sig, self.stop)
    # Data plane first: it waits for a signed snapshot and never needs the console.
    self.start('dataplane')
    self.start('control')
    restart_at = None
    try:
      while not self.stopping:
        time.sleep(self.poll)
        code = self.processes['dataplane'].poll()
        if code is not None:
          log('plane.exited', plane='dataplane', code=code)
          return code or 1
        control = self.processes['control']
        if restart_at is None and control.poll() is not None:
          uptime = time.monotonic() - self.started['control']
          if uptime >= self.stable_after: self.control_restarts = 0
          delay = min(self.max_backoff, 2 ** self.control_restarts)
          self.control_restarts += 1
          log('plane.exited', plane='control', code=control.returncode, restart_in_seconds=delay)
          restart_at = time.monotonic() + delay
        if restart_at is not None and time.monotonic() >= restart_at:
          restart_at = None
          self.start('control')
      return 0
    finally:
      self.terminate()
