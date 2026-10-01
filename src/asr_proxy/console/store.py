"""Persistent demo state. Raw passwords and session tokens are never stored."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
  return datetime.now(timezone.utc).isoformat()


def password_hash(password, salt):
  return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()


class Store:
  def __init__(self, directory, *, bootstrap_password="1234", require_existing=False):
    self.directory=Path(directory)
    self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    self.path=self.directory/'console.sqlite'
    if require_existing and not self.path.is_file():raise ValueError('Run selfhost init before starting the service')
    with self.connect() as db:
      db.executescript('''
        CREATE TABLE IF NOT EXISTS account(username TEXT PRIMARY KEY,salt TEXT,password_hash TEXT,changed INTEGER);
        CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY,expires REAL);
        CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,failures INTEGER,until REAL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,payload TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,actor TEXT,event TEXT,detail TEXT);
      ''')
      columns={row[1] for row in db.execute('PRAGMA table_info(sessions)')}
      if 'principal' not in columns:db.execute("ALTER TABLE sessions ADD COLUMN principal TEXT")
      if not db.execute('SELECT 1 FROM account').fetchone():
        if require_existing:raise ValueError('Administrator has not been initialized')
        salt=secrets.token_hex(16)
        db.execute('INSERT INTO account VALUES(?,?,?,?)',('admin',salt,password_hash(bootstrap_password,salt),int(bootstrap_password!='1234')))
    os.chmod(self.path,0o600)

  @contextmanager
  def connect(self):
    db=sqlite3.connect(self.path,timeout=10)
    db.row_factory=sqlite3.Row
    try:
      with db:yield db
    finally:
      db.close()

  def check_password(self,password):
    with self.connect() as db:
      row=db.execute('SELECT * FROM account WHERE username=?',('admin',)).fetchone()
    return hmac.compare_digest(password_hash(password,row['salt']),row['password_hash'])

  def changed(self):
    with self.connect() as db:return bool(db.execute('SELECT changed FROM account').fetchone()[0])

  def create_session(self,principal=None,ttl=8*3600):
    token=secrets.token_urlsafe(32)
    with self.connect() as db:
      db.execute('DELETE FROM sessions WHERE expires < ?',(time.time(),))
      db.execute('INSERT INTO sessions(digest,expires,principal) VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),time.time()+min(ttl,8*3600),json.dumps(principal or {'username':'admin','role':'admin','authentication':'local'})))
    return token

  def principal(self,token):
    if not token:return None
    with self.connect() as db:
      row=db.execute('SELECT principal FROM sessions WHERE digest=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
    return json.loads(row[0]) if row and row[0] else None

  def authenticated(self,token):return self.principal(token) is not None

  def logout(self,token):
    with self.connect() as db:db.execute('DELETE FROM sessions WHERE digest=?',(hashlib.sha256((token or '').encode()).hexdigest(),))

  def change_password(self,current,new):
    # A single SQLite transaction binds password verification and session revocation.
    with self.connect() as db:
      db.execute('BEGIN IMMEDIATE')
      row=db.execute('SELECT * FROM account').fetchone()
      if not hmac.compare_digest(password_hash(current,row['salt']),row['password_hash']):return False
      salt=secrets.token_hex(16)
      db.execute('UPDATE account SET salt=?,password_hash=?,changed=1',(salt,password_hash(new,salt)))
      db.execute('DELETE FROM sessions')
    self.audit('account.password_changed','All sessions revoked')
    return True

  def login_attempt(self,identity,success=None):
    with self.connect() as db:
      db.execute('BEGIN IMMEDIATE')
      row=db.execute('SELECT * FROM attempts WHERE id=?',(identity,)).fetchone()
      if success is None:return bool(row and row['failures']>=5 and row['until']>time.time())
      if success:db.execute('DELETE FROM attempts WHERE id=?',(identity,))
      else:
        failures=row['failures']+1 if row and row['until']>time.time() else 1
        db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?)',(identity,failures,time.time()+60))
    return False

  def get(self,key,default=None):
    with self.connect() as db:row=db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else default

  def set(self,key,value):
    with self.connect() as db:db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))

  def audit(self,event,detail,actor='system'):
    with self.connect() as db:db.execute('INSERT INTO audit(ts,actor,event,detail) VALUES(?,?,?,?)',(now(),actor,event,detail))

  def audits(self):
    with self.connect() as db:return [dict(r) for r in db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 1000')]

  def add_event(self,event):
    with self.connect() as db:
      cursor=db.execute('INSERT INTO events(payload) VALUES(?)',(json.dumps(event),))
      event={**event,'id':cursor.lastrowid}
    return event

  def ingest_events(self,events,cursor):
    # Events and the spool cursor commit together, so a restart never duplicates or skips.
    with self.connect() as db:
      for event in events:db.execute('INSERT INTO events(payload) VALUES(?)',(json.dumps(event),))
      db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('event_spool_cursor',json.dumps(cursor)))

  def update_event(self,event):
    with self.connect() as db:db.execute('UPDATE events SET payload=? WHERE id=?',(json.dumps({k:v for k,v in event.items() if k!='id'}),event['id']))

  def events(self):
    with self.connect() as db:return [{**json.loads(r['payload']),'id':r['id']} for r in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 2000')]

  def save_policy(self,policy):
    with self.connect() as db:
      db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('policy',json.dumps(policy)))
      db.execute('INSERT INTO audit(ts,actor,event,detail) VALUES(?,?,?,?)',
        (now(),'system','policy.applied',
         f"v{policy['version']} · {policy['mode']} · PII {policy['pii_action']} · tool overrides {sum(value!='inherit' for value in policy['pii_rules'].values())}"))
