"""The jobs table: every import (and other long task) a box has been asked to do.

A SQLite file in the box's `.caixa/` folder, so a long import's progress and outcome survive a
restart. Each call opens its own short connection, so the runner thread and request threads never
share one. A job is `queued` → `running` → `done`, `failed` or `cancelled`; a job that was queued or
running when Caixa stopped is `interrupted` on the next start (running it again is safe: imports
change nothing that is already there).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Union

PathLike = Union[str, Path]
STATUSES = ("queued", "running", "done", "failed", "cancelled", "interrupted")
FINISHED = ("done", "failed", "cancelled", "interrupted")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    collector TEXT,
    source TEXT,
    options TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'done', 'failed', 'cancelled', 'interrupted')),
    stage TEXT,
    current INTEGER NOT NULL DEFAULT 0,
    total INTEGER,
    message TEXT,
    result TEXT,
    error TEXT,
    log TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
"""
_FIELDS = ("status", "stage", "current", "total", "message", "result", "error", "log")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    def __init__(self, path: PathLike, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        if not read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as db:
                db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        if self.read_only:
            db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        else:
            db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    # --- Writing ----------------------------------------------------------------------------

    def create(
        self,
        kind: str,
        collector: Optional[str],
        source: Optional[str],
        options: Mapping[str, Any],
    ) -> int:
        with closing(self._connect()) as db, db:
            cur = db.execute(
                "INSERT INTO jobs (kind, collector, source, options, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (kind, collector, source, json.dumps(options, ensure_ascii=False), now()),
            )
            return int(cur.lastrowid or 0)

    def update(self, job: int, **fields: Any) -> None:
        """Change a job's status, progress, result, error or log; times follow the status."""
        unknown = set(fields) - set(_FIELDS)
        if unknown:
            raise ValueError(f"Unknown job fields: {', '.join(sorted(unknown))}")
        if "result" in fields and not isinstance(fields["result"], (str, type(None))):
            fields["result"] = json.dumps(fields["result"], ensure_ascii=False)
        status = fields.get("status")
        extra: dict[str, Any] = {}
        if status == "running":
            extra["started_at"] = now()
        elif status in FINISHED:
            extra["finished_at"] = now()
        columns = {**fields, **extra}
        assignments = ", ".join(f"{name} = ?" for name in columns)
        with closing(self._connect()) as db, db:
            db.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", (*columns.values(), job))

    def mark_interrupted(self) -> int:
        """After a restart: whatever was queued or running did not finish."""
        with closing(self._connect()) as db, db:
            cur = db.execute(
                "UPDATE jobs SET status = 'interrupted', finished_at = ?, "
                "error = 'Caixa stopped before this finished; run it again to continue.' "
                "WHERE status IN ('queued', 'running')",
                (now(),),
            )
            return cur.rowcount

    # --- Reading ----------------------------------------------------------------------------

    def get(self, job: int) -> dict[str, Any]:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM jobs WHERE id = ?", (job,)).fetchone()
        if row is None:
            raise KeyError(job)
        return self._plain(row)

    def list(self, limit: int = 50, status: Optional[str] = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM jobs" + (" WHERE status = ?" if status else "")
        with closing(self._connect()) as db:
            rows = db.execute(
                query + " ORDER BY id DESC LIMIT ?", (*((status,) if status else ()), limit)
            ).fetchall()
        return [self._plain(r) for r in rows]

    @staticmethod
    def _plain(row: sqlite3.Row) -> dict[str, Any]:
        job = dict(row)
        job["options"] = json.loads(job["options"] or "{}")
        job["result"] = json.loads(job["result"]) if job["result"] else None
        return job
