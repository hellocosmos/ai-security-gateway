"""Append-only evidence spool owned by the data plane and drained by the control plane.

Each writing process owns one subdirectory, so rotation never races across
processes. The reader tracks (inode, offset) per writer and commits the cursor
in the same SQLite transaction as the ingested events.
"""
import json
import os
import time
from pathlib import Path
from threading import Lock

ACTIVE = 'events.jsonl'
MAX_ACTIVE_BYTES = 64 * 1024 * 1024
MAX_READ_BYTES = 4 * 1024 * 1024


class EventSpool:
  def __init__(self, directory, writer, *, max_bytes=MAX_ACTIVE_BYTES):
    self.directory = Path(directory) / writer
    self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    self.max_bytes = max_bytes
    self.lock = Lock()
    self.healthy = True
    self.failures = 0

  def append(self, event):
    line = json.dumps(event, separators=(',', ':'), ensure_ascii=False).encode() + b'\n'
    with self.lock:
      try:
        path = self.directory / ACTIVE
        try:
          if path.stat().st_size + len(line) > self.max_bytes:
            os.replace(path, self.directory / f'events-{time.time_ns()}.jsonl')
        except FileNotFoundError:
          pass
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
          written = os.write(descriptor, line)
          if written != len(line): raise OSError('short_spool_write')
          os.fsync(descriptor)
        finally:
          os.close(descriptor)
      except OSError:
        self.healthy = False
        self.failures += 1
        raise
      self.healthy = True

  def probe(self):
    """Re-check writability after a failure without touching evidence files."""
    with self.lock:
      probe = self.directory / '.probe'
      try:
        descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
          os.write(descriptor, b'1')
          os.fsync(descriptor)
        finally:
          os.close(descriptor)
        probe.unlink()
        self.healthy = True
      except OSError:
        self.healthy = False
      return self.healthy


def _files(writer_directory):
  sealed = sorted(writer_directory.glob('events-*.jsonl'),
    key=lambda path: int(path.stem.split('-', 1)[1]) if path.stem.split('-', 1)[1].isdigit() else 0)
  active = writer_directory / ACTIVE
  return sealed + ([active] if active.exists() else [])


def read_pending(directory, cursor, *, limit=MAX_READ_BYTES):
  """Return (events, new_cursor, drained_files). Never returns a partial line."""
  directory = Path(directory)
  cursor = dict(cursor or {})
  events, drained, budget = [], [], limit
  if not directory.is_dir():
    return events, cursor, drained
  for writer_directory in sorted(path for path in directory.iterdir() if path.is_dir()):
    writer = writer_directory.name
    position = cursor.get(writer)
    files = _files(writer_directory)
    inodes = [path.stat().st_ino for path in files]
    if position and position.get('inode') in inodes:
      start = inodes.index(position['inode'])
      offset = position['offset']
      # Files before the cursor were fully committed earlier.
      drained.extend(files[:start])
    else:
      start, offset = 0, 0
    for index in range(start, len(files)):
      path = files[index]
      with open(path, 'rb') as handle:
        handle.seek(offset)
        data = handle.read(max(budget, 0))
      end = data.rfind(b'\n') + 1
      for raw in data[:end].splitlines():
        try:
          value = json.loads(raw)
        except ValueError:
          continue
        if isinstance(value, dict): events.append(value)
      offset += end
      budget -= end
      cursor[writer] = {'inode': inodes[index], 'offset': offset}
      sealed = path.name != ACTIVE
      if sealed and offset >= path.stat().st_size and index + 1 < len(files):
        drained.append(path)
        offset = 0
        continue
      break
    if budget <= 0: break
  return events, cursor, drained
