"""Local deployment controls and a persistent, privacy-limited audit journal."""
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
from threading import Lock
import time


class AuditJournal:
    def __init__(self, directory):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        keyfile=self.directory/'audit.key'
        if not keyfile.exists():
            try:
                fd=os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'wb') as f:f.write(secrets.token_bytes(32))
            except FileExistsError:pass
        self.key=keyfile.read_bytes()
        if len(self.key)!=32:raise RuntimeError('Invalid audit key')
        self.path=self.directory/'audit.sqlite3'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS events (trace_id TEXT PRIMARY KEY, timestamp_utc TEXT NOT NULL, method TEXT NOT NULL, route TEXT NOT NULL, request_digest TEXT NOT NULL, status INTEGER NOT NULL, duration_ms REAL NOT NULL, decision_status TEXT, model_version TEXT NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS events_timestamp ON events(timestamp_utc)')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()

    def record(self, trace, method, route, body, status, elapsed, decision):
        digest=hmac.new(self.key,body,hashlib.sha256).hexdigest()
        with self.connect() as db:
            db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)',(trace,datetime.now(timezone.utc).isoformat(),method,route,digest,status,round(elapsed,3),decision,'phase4-operational-80-v1'))

    def recent(self,limit=30):
        with self.connect() as db:
            db.row_factory=sqlite3.Row
            return [dict(r) for r in db.execute('SELECT * FROM events ORDER BY timestamp_utc DESC LIMIT ?', (limit,))]

    def summary(self):
        with self.connect() as db:
            total=db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
            errors=db.execute('SELECT COUNT(*) FROM events WHERE status>=500').fetchone()[0]
        return {'recorded_requests':total,'server_errors':errors,'storage':'SQLite WAL; persisted in the configured runtime directory','raw_inputs_stored':False}


class RateLimit:
    """One process-wide ceiling appropriate to the single-operator local demo."""
    def __init__(self, limit=120, window=60):self.limit=limit;self.window=window;self.times=deque();self.lock=Lock()
    def allow(self):
        now=time.monotonic()
        with self.lock:
            while self.times and now-self.times[0]>=self.window:self.times.popleft()
            if len(self.times)>=self.limit:return False
            self.times.append(now);return True


def verify_bundle(root):
    root=Path(root)
    expected=json.loads((root/'bundle_lock.json').read_text())
    for relative,digest in expected.items():
        path=root/relative
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Bundle integrity mismatch: '+relative)
    return len(expected)
