import json
import os
import shutil
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .models import Job


def write_json(path: Path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


class Store:
    def __init__(self, root):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs = root / "jobs"
        self.jobs.mkdir(exist_ok=True)
        self.staging = root / "staging"
        self.staging.mkdir(exist_ok=True)
        with self.db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, expires REAL NOT NULL, body TEXT NOT NULL)"
            )

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.root / "jobs.sqlite3", timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def recover(self):
        # Exactly one process owns this store. Persisted processing jobs are replayed.
        with self.db() as db:
            for (body,) in db.execute("SELECT body FROM jobs WHERE status='processing'").fetchall():
                job = Job.model_validate_json(body)
                job.status, job.stage = "queued", "queued"
                db.execute(
                    "UPDATE jobs SET status=?,body=? WHERE id=?",
                    (job.status, job.model_dump_json(), job.job_id),
                )
        for directory in self.staging.iterdir():
            shutil.rmtree(directory, ignore_errors=True)
        self.cleanup()

    def create(self, job):
        with self.db() as db:
            db.execute(
                "INSERT INTO jobs VALUES (?,?,?,?)",
                (job.job_id, job.status, job.expires_at, job.model_dump_json()),
            )

    def count_pending(self):
        with self.db() as db:
            return db.execute(
                "SELECT count(*) FROM jobs WHERE status IN ('queued','processing') AND expires>?",
                (time.time(),),
            ).fetchone()[0]

    def get(self, job_id):
        with self.db() as db:
            row = db.execute(
                "SELECT body FROM jobs WHERE id=? AND expires>?", (job_id, time.time())
            ).fetchone()
        return Job.model_validate_json(row[0]) if row else None

    def save(self, job):
        with self.db() as db:
            db.execute(
                "UPDATE jobs SET status=?,body=? WHERE id=? AND expires>?",
                (job.status, job.model_dump_json(), job.job_id, time.time()),
            )

    def claim(self):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT body FROM jobs WHERE status='queued' AND expires>? ORDER BY rowid LIMIT 1",
                (time.time(),),
            ).fetchone()
            if not row:
                return None
            job = Job.model_validate_json(row[0])
            job.status, job.stage = "processing", "ocr"
            db.execute(
                "UPDATE jobs SET status=?,body=? WHERE id=?",
                (job.status, job.model_dump_json(), job.job_id),
            )
            return job

    def delete(self, job_id):
        with self.db() as db:
            db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        shutil.rmtree(self.jobs / job_id, ignore_errors=True)

    def cleanup(self):
        with self.db() as db:
            expired = db.execute("SELECT id FROM jobs WHERE expires<=?", (time.time(),)).fetchall()
        for (job_id,) in expired:
            self.delete(job_id)
        # Also recover directory/DB crash gaps, without racing recent uploads.
        for directory in self.jobs.iterdir():
            try:
                if directory.is_dir() and time.time() - directory.stat().st_mtime > 86400:
                    if self.get(directory.name) is None:
                        shutil.rmtree(directory, ignore_errors=True)
            except FileNotFoundError:
                pass
