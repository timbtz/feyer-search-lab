"""Durable local queue; all evaluator inputs are immutable Git commit IDs."""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

TERMINAL_STATUSES = frozenset({"completed", "failed", "timed_out", "interrupted", "rejected"})
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REQUEST_FIELDS = ('sha', 'branch', 'agent', 'direction', 'hypothesis', 'profile')


def normalize_request_id(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) not in (32, 36):
        raise ValueError('request_id must be a UUID')
    try:
        return uuid.UUID(value).hex
    except (ValueError, AttributeError) as exc:
        raise ValueError('request_id must be a UUID') from exc


class Queue:
    def __init__(self, state_dir, repo_path):
        self.state_dir = Path(state_dir).resolve()
        self.repo_path = Path(repo_path).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.state_dir / "queue.sqlite3"
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, sha TEXT NOT NULL, branch TEXT NOT NULL,
                    agent TEXT NOT NULL, direction TEXT NOT NULL, hypothesis TEXT NOT NULL,
                    profile TEXT NOT NULL, status TEXT NOT NULL,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    started_at REAL, finished_at REAL, worker_id TEXT,
                    result_json TEXT, error TEXT
                );
                CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs(status, created_at);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL, at REAL NOT NULL,
                    event TEXT NOT NULL, detail_json TEXT NOT NULL
                );
            """)
            # Serialize migration with other constructors. NULL keeps legacy jobs
            # and intentionally independent submissions fully backward compatible.
            db.execute('BEGIN IMMEDIATE')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(jobs)')}
            if 'request_id' not in columns:
                db.execute('ALTER TABLE jobs ADD COLUMN request_id TEXT')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS jobs_request_id ON jobs(request_id) WHERE request_id IS NOT NULL')

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def _git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.repo_path), *args], text=True,
            stderr=subprocess.PIPE,
        ).strip()

    @staticmethod
    def _record(row):
        if row is None:
            return None
        record = dict(row)
        record["result"] = json.loads(record.pop("result_json")) if record["result_json"] else None
        record.pop("result_json", None)
        return record

    @staticmethod
    def _event(db, job_id, event, detail=None):
        db.execute("INSERT INTO events(job_id,at,event,detail_json) VALUES(?,?,?,?)",
                   (job_id, time.time(), event, json.dumps(detail or {}, allow_nan=False)))

    def enqueue(self, sha, branch, agent, direction, hypothesis="", profile="screen", request_id=None):
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise ValueError("sha must be a full 40-character hexadecimal commit ID")
        sha = sha.lower()
        request_id = normalize_request_id(request_id)
        if profile not in {"screen", "full", "diagnostic"}:
            raise ValueError("profile must be screen, full or diagnostic")
        for name, value in (("branch", branch), ("agent", agent), ("direction", direction)):
            if not isinstance(value, str) or not value.strip() or len(value) > 300 or "\0" in value:
                raise ValueError(f"Invalid {name}")
        if branch.startswith("-") or branch.startswith("@"):
            raise ValueError("Invalid branch")
        self._git("check-ref-format", "--branch", branch)
        if not isinstance(hypothesis, str) or len(hypothesis) > 20000 or "\0" in hypothesis:
            raise ValueError("Invalid hypothesis")
        if self._git("cat-file", "-t", sha) != "commit":
            raise ValueError("sha must identify a commit already fetched into the mirror")
        payload = dict(sha=sha, branch=branch, agent=agent, direction=direction, hypothesis=hypothesis, profile=profile)
        ref = None
        try:
            with self._connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if request_id is not None:
                    existing = db.execute('SELECT * FROM jobs WHERE request_id=?', (request_id,)).fetchone()
                    if existing is not None:
                        if any(existing[key] != payload[key] for key in REQUEST_FIELDS):
                            raise ValueError('request_id already identifies a different submission payload')
                        return self._record(existing)
                job_id = uuid.uuid4().hex
                ref = f"refs/candidates/{job_id}"
                self._git("update-ref", ref, sha)
                now = time.time()
                db.execute("""INSERT INTO jobs
                    (id,sha,branch,agent,direction,hypothesis,profile,status,created_at,updated_at,request_id)
                    VALUES(?,?,?,?,?,?,?,'queued',?,?,?)""",
                    (job_id, sha, branch, agent, direction, hypothesis, profile, now, now, request_id))
                self._event(db, job_id, "queued", {"ref": ref})
        except BaseException:
            if ref is not None:
                self._git("update-ref", "-d", ref, sha)
            raise
        return self.get(job_id)

    def get_by_request_id(self, request_id):
        request_id = normalize_request_id(request_id)
        if request_id is None:
            raise ValueError('request_id is required for lookup')
        with self._connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE request_id=?', (request_id,)).fetchone()
        return self._record(row)

    def get(self, job_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._record(row)

    def list_jobs(self, limit=50, status=None):
        if not isinstance(limit, int) or not 1 <= limit <= 10000:
            raise ValueError("limit must be between 1 and 10000")
        with self._connect() as db:
            if status is None:
                rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM jobs WHERE status=? ORDER BY created_at DESC, id DESC LIMIT ?",
                                  (status, limit)).fetchall()
        return [self._record(row) for row in rows]

    def events(self, job_id):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM events WHERE job_id=? ORDER BY seq", (job_id,)).fetchall()
        return [dict(row) | {"detail": json.loads(row["detail_json"])} for row in rows]

    def claim(self, worker_id):
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker_id is required")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if row is None:
                return None
            now = time.time()
            db.execute("UPDATE jobs SET status='running',worker_id=?,started_at=?,updated_at=? WHERE id=?",
                       (worker_id, now, now, row["id"]))
            self._event(db, row["id"], "running", {"worker_id": worker_id})
            result = db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
        return self._record(result)

    def heartbeat(self, job_id, worker_id):
        with self._connect() as db:
            changed = db.execute("UPDATE jobs SET updated_at=? WHERE id=? AND worker_id=? AND status='running'",
                                 (time.time(), job_id, worker_id)).rowcount
        if changed != 1:
            raise RuntimeError("Worker no longer owns this running job")

    def finish(self, job_id, worker_id, status, result=None, error=None):
        if status not in TERMINAL_STATUSES:
            raise ValueError("Invalid terminal status")
        encoded = json.dumps(result, allow_nan=False) if result is not None else None
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            changed = db.execute("""UPDATE jobs SET status=?,updated_at=?,finished_at=?,result_json=?,error=?
                WHERE id=? AND worker_id=? AND status='running'""",
                (status, now, now, encoded, error, job_id, worker_id)).rowcount
            if changed != 1:
                raise RuntimeError("Worker no longer owns this running job")
            self._event(db, job_id, status, {"error": error})
        return self.get(job_id)

    def recover_stale(self, max_age=120):
        """Mark abandoned runs interrupted. Call only while owning the worker lock."""
        if max_age < 0:
            raise ValueError("max_age must be nonnegative")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            rows = db.execute("SELECT id FROM jobs WHERE status='running' AND updated_at<?",
                              (now - max_age,)).fetchall()
            for row in rows:
                db.execute("UPDATE jobs SET status='interrupted',updated_at=?,finished_at=?,error=? WHERE id=?",
                           (now, now, "Worker heartbeat expired; submit a new job to retry", row["id"]))
                self._event(db, row["id"], "interrupted", {"reason": "heartbeat expired"})
        return [row["id"] for row in rows]
