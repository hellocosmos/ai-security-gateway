"""Bounded process-local timings; no request content or identity is retained."""
from collections import deque
import math
from threading import Lock

SERIES = ('gateway_total', 'envoy_exchange', 'request_inspection',
          'response_metadata_inspection', 'response_inspection')


class LatencyMetrics:
  def __init__(self):
    self.lock = Lock()
    self.samples = {name: deque(maxlen=256) for name in SERIES}

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
      return {'scope': 'current_process_last_256_per_phase', 'series': result}
