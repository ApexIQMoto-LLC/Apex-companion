"""Durable local operations queue for finite, allowlisted APEX jobs.

This database is only a *task journal*. It cannot execute shell commands or
arbitrary model output. The dispatcher implements a fixed handler per kind.
Never put passwords, tokens, source code or raw email bodies in task arguments.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ALLOWED_KINDS = frozenset({"unity_diagnostics", "git_health", "unity_editmode_tests", "desktop_inspect"})
SAFE_PHONE_KINDS = frozenset({"unity_diagnostics", "git_health"})
TERMINAL = frozenset({"completed", "blocked", "failed", "cancelled"})


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def _datetime(s):
    return datetime.fromisoformat(s)


class OperationsQueue:
    def __init__(self, dbpath):
        self.path = str(dbpath)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS ops_tasks (
                task_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                status TEXT NOT NULL, origin TEXT NOT NULL,
                project_hash TEXT NOT NULL, payload TEXT NOT NULL,
                created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                result TEXT NOT NULL DEFAULT '{}',
                dedupe_key TEXT UNIQUE, error_code TEXT,
                note TEXT NOT NULL DEFAULT ''
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_ops_queue ON ops_tasks(status,created_utc)")
            db.execute("""CREATE TABLE IF NOT EXISTS ops_control (
                name TEXT PRIMARY KEY, value TEXT NOT NULL
            )""")

    @contextmanager
    def _db(self):
        connection=sqlite3.connect(self.path,timeout=10)
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _row(row):
        if not row:
            return None
        d = dict(zip(("task_id", "kind", "status", "origin", "project_hash", "payload", "created_utc", "updated_utc", "attempts", "result", "dedupe_key", "error_code", "note"), row))
        d["payload"] = json.loads(d["payload"])
        d["result"] = json.loads(d["result"])
        return d

    def enqueue(self, kind, *, origin="desktop", project_hash="", note="", dedupe_key=None, payload=None):
        if kind not in ALLOWED_KINDS:
            raise ValueError("Task is not in the APEX operations allowlist")
        if origin not in {"desktop", "away", "phone"}:
            raise ValueError("Unrecognized task origin")
        if origin == "phone" and kind not in SAFE_PHONE_KINDS:
            raise PermissionError("Phone cannot enqueue Unity test runs or desktop inspection")
        if payload not in (None, {}):
            raise ValueError("Task arguments are fixed by the dispatcher, not supplied from messages")
        if len(project_hash)>72 or len(str(note))>300:
            raise ValueError("Task metadata is too long")
        if dedupe_key is not None and len(str(dedupe_key))>128:
            raise ValueError("Invalid deduplication key")
        tid=uuid.uuid4().hex[:20]
        now=utcnow()
        with self._db() as db:
            # Do not let a compromised phone or a repeated away event create
            # an unbounded backlog of local work.
            queued=db.execute("SELECT count(*) FROM ops_tasks WHERE status IN ('queued','running')").fetchone()[0]
            if queued>=25:
                raise RuntimeError("Operation queue is full; review tasks before adding more")
            try:
                db.execute("""INSERT INTO ops_tasks
                    (task_id,kind,status,origin,project_hash,payload,created_utc,updated_utc,dedupe_key,note)
                    VALUES(?,?, 'queued',?,?,'{}',?,?,?,?)""",
                    (tid,kind,origin,project_hash,now,now,dedupe_key,str(note)[:300]))
            except sqlite3.IntegrityError:
                if not dedupe_key:raise
                record=db.execute("SELECT task_id FROM ops_tasks WHERE dedupe_key=?",(dedupe_key,)).fetchone()
                return record[0]
        return tid

    def set_paused(self, paused):
        with self._db() as db:
            db.execute("INSERT INTO ops_control(name,value) VALUES('paused',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",("1" if paused else "0",))

    def paused(self):
        with self._db() as db:
            row=db.execute("SELECT value FROM ops_control WHERE name='paused'").fetchone()
        return bool(row and row[0]=="1")

    def claim(self):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            if self.paused():
                return None
            row=db.execute("SELECT * FROM ops_tasks WHERE status='queued' ORDER BY created_utc ASC LIMIT 1").fetchone()
            if not row:
                return None
            task=self._row(row)
            changed=db.execute("UPDATE ops_tasks SET status='running',attempts=attempts+1,updated_utc=? WHERE task_id=? AND status='queued'",(utcnow(),task['task_id'])).rowcount
            if changed!=1:return None
            task["status"]="running";task["attempts"]+=1
            return task

    def finish(self, task_id, status, result=None, error_code=""):
        if status not in TERMINAL:
            raise ValueError("Not a terminal task status")
        safe_result=result if isinstance(result,dict) else {}
        text=json.dumps(safe_result,ensure_ascii=True)[:4500]
        with self._db() as db:
            changed=db.execute("UPDATE ops_tasks SET status=?,result=?,error_code=?,updated_utc=? WHERE task_id=? AND status='running'",
                               (status,text,str(error_code)[:60],utcnow(),task_id)).rowcount
        return bool(changed)

    def cancel(self, task_id):
        with self._db() as db:
            return bool(db.execute("UPDATE ops_tasks SET status='cancelled',updated_utc=? WHERE task_id=? AND status='queued'",(utcnow(),task_id)).rowcount)

    def recover_interrupted(self):
        # Never automatically rerun an operation interrupted by process crash:
        # even allowlisted work can have changed the project outside the DB.
        with self._db() as db:
            return db.execute("UPDATE ops_tasks SET status='blocked',error_code='interrupted_restart',updated_utc=? WHERE status='running'",(utcnow(),)).rowcount

    def recent(self, limit=25):
        with self._db() as db:
            rows=db.execute("SELECT * FROM ops_tasks ORDER BY created_utc DESC LIMIT ?",(max(1,min(int(limit),100)),)).fetchall()
        return [self._row(x) for x in rows]

    def get(self, task_id):
        with self._db() as db:
            return self._row(db.execute("SELECT * FROM ops_tasks WHERE task_id=?",(task_id,)).fetchone())

    def counts(self):
        with self._db() as db:
            return dict(db.execute("SELECT status,count(*) FROM ops_tasks GROUP BY status").fetchall())
