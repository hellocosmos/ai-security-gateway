"""Bounded process-local timings; no request content or identity is retained."""
from collections import OrderedDict, deque
import math
import re
import time
from threading import Lock

SERIES = ('gateway_total', 'envoy_exchange', 'request_inspection',
          'response_metadata_inspection', 'response_inspection')
STAGES = frozenset(('envoy_sent', 'request_checked', 'response_headers_received',
                    'response_headers_checked', 'response_body_received', 'response_checked'))


class LatencyMetrics:
  def __init__(self, inspector_processes=1):
    self.inspector_processes = inspector_processes
    self.lock = Lock()
    self.samples = {name: deque(maxlen=256) for name in SERIES}
    self.pending = OrderedDict()
    self.requests = deque(maxlen=64)

  def begin(self, run_id, *, at=None):
    if not isinstance(run_id, str) or re.fullmatch(r'[0-9a-f]{32}', run_id) is None:
      return
    with self.lock:
      self.pending[run_id] = {'started': time.perf_counter() if at is None else at,
                              'stages': {}, 'checks': {}}
      self.pending.move_to_end(run_id)
      while len(self.pending) > 256:
        self.pending.popitem(last=False)

  def mark(self, run_id, stage, *, at=None):
    if stage not in STAGES:
      return
    with self.lock:
      if run_id in self.pending:
        self.pending[run_id]['stages'][stage] = time.perf_counter() if at is None else at

  def inspection(self, run_id, phase, *, queue_ms, work_ms):
    if phase not in SERIES[2:] or any(not isinstance(value, (int, float)) or
        not math.isfinite(value) or value < 0 for value in (queue_ms, work_ms)):
      return
    with self.lock:
      if run_id in self.pending:
        checks = self.pending[run_id]['checks'].setdefault(phase, [])
        checks.append((float(queue_ms), float(work_ms)))
        if len(checks) > 8: del checks[:-8]

  def stream_wait(self, run_id, milliseconds):
    if not isinstance(milliseconds, (int, float)) or not math.isfinite(milliseconds) or milliseconds < 0:
      return
    with self.lock:
      if run_id in self.pending:
        self.pending[run_id]['stream_wait_ms'] = float(milliseconds)

  def finish(self, run_id, status, *, at=None):
    with self.lock:
      item = self.pending.pop(run_id, None)
      if item is None:
        return
      end = time.perf_counter() if at is None else at
      stages = item['stages']
      def elapsed(start, stop):
        left = item['started'] if start == 'started' else stages.get(start)
        right = end if stop == 'ready' else stages.get(stop)
        return round((right-left)*1000, 2) if left is not None and right is not None and right >= left else None
      checks = [pair for entries in item['checks'].values() for pair in entries]
      self.requests.appendleft({
        'http_status': status if isinstance(status, int) and 100 <= status <= 599 else None,
        'gateway_total_ms': elapsed('started', 'ready'),
        'before_envoy_ms': elapsed('started', 'envoy_sent'),
        'upstream_headers_wait_ms': elapsed('request_checked', 'response_headers_received'),
        'response_body_wait_ms': elapsed('response_headers_checked', 'response_body_received'),
        'after_response_check_ms': elapsed('response_checked', 'ready'),
        'inspection_queue_ms': round(sum(pair[0] for pair in checks), 2) if checks else None,
        'inspection_work_ms': round(sum(pair[1] for pair in checks), 2) if checks else None,
        'inspector_stream_wait_ms': round(item['stream_wait_ms'], 2) if 'stream_wait_ms' in item else None,
        'inspection_calls': len(checks),
        'complete': all(name in stages for name in ('request_checked', 'response_headers_checked',
                                                    'response_checked')),
      })

  def record(self, name, milliseconds):
    if name not in self.samples or not isinstance(milliseconds, (int, float)):
      return
    if not math.isfinite(milliseconds) or milliseconds < 0:
      return
    with self.lock:
      self.samples[name].append(float(milliseconds))

  def snapshot(self):
    with self.lock:
      result = []
      for name, samples in self.samples.items():
        ordered = sorted(samples)
        def percentile(p):
          return round(ordered[max(0, math.ceil(len(ordered)*p)-1)], 2) if ordered else None
        result.append({'phase': name, 'samples': len(ordered), 'p50_ms': percentile(.5),
                       'p95_ms': percentile(.95), 'max_ms': percentile(1)})
      scope = 'current_process_last_256_per_phase' if self.inspector_processes == 1 else 'gateway_process_only_last_256_per_phase'
      request_scope = 'current_process_last_64_completed' if self.inspector_processes == 1 else 'gateway_process_only_last_64_completed'
      return {'scope': scope, 'series': result, 'request_scope': request_scope,
              'inspector_timing_available': self.inspector_processes == 1,
              'requests': list(self.requests)}
