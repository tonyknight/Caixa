"""The schema of `caixa.sqlite`, the master database, as ordered migrations.

The master sees every domain and links items to people. It is separate from each collector's own
database (Chattr's `chattr.sqlite` and so on): the only contract between them is the handoff, in
which a collector's adapter reads the collector's database and upserts here by stable id.

- `people`, `aliases`: who is who, and every name, number, address or username each is known by.
- `items`: one row per message, mail, call or voicemail, with the stable id the collector gave it,
  its time (UTC, the sender's offset, precision), text, the page that shows it, privacy, content
  hash and version.
- `item_people`: every person involved in an item, by role.
- `imports`: provenance of each run.
- `change_log`: append-only (triggers refuse edits and deletes); the change number only grows, so
  anything built on top (an index, a knowledge store) can ask "what changed since N".
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

MIGRATION_1 = """
CREATE TABLE people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    is_owner INTEGER NOT NULL DEFAULT 0 CHECK (is_owner IN (0, 1)),
    notes TEXT,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX people_one_owner ON people (is_owner) WHERE is_owner = 1;

CREATE TABLE aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people (id),
    kind TEXT NOT NULL CHECK (kind IN ('phone', 'email', 'username', 'name')),
    value TEXT NOT NULL,
    normalized TEXT NOT NULL,
    service TEXT,
    source TEXT NOT NULL DEFAULT 'human'
);
CREATE UNIQUE INDEX aliases_unique ON aliases (kind, normalized, COALESCE(service, ''));
CREATE INDEX aliases_by_person ON aliases (person_id);

CREATE TABLE imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collector TEXT NOT NULL,
    source TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    inserted INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    linked INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    details TEXT
);

CREATE TABLE items (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    collector TEXT NOT NULL,
    service TEXT,
    conversation TEXT,
    timestamp_utc TEXT NOT NULL,
    tz_offset_minutes INTEGER,
    time_precision TEXT NOT NULL DEFAULT 'second',
    text TEXT,
    file_path TEXT,
    anchor TEXT,
    privacy TEXT NOT NULL DEFAULT 'private' CHECK (privacy IN ('private', 'family', 'public')),
    content_hash TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    first_import_id INTEGER REFERENCES imports (id),
    last_import_id INTEGER REFERENCES imports (id)
);
CREATE INDEX items_by_time ON items (timestamp_utc);
CREATE INDEX items_by_conversation ON items (collector, conversation);

CREATE TABLE item_people (
    item_id TEXT NOT NULL REFERENCES items (id),
    person_id INTEGER NOT NULL REFERENCES people (id),
    role TEXT NOT NULL CHECK (role IN ('sender', 'recipient', 'participant', 'depicted', 'mentioned')),
    PRIMARY KEY (item_id, person_id, role)
);
CREATE INDEX item_people_by_person ON item_people (person_id, role);

CREATE TABLE change_log (
    change INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('insert', 'update', 'link')),
    version INTEGER NOT NULL,
    import_id INTEGER REFERENCES imports (id),
    at TEXT NOT NULL
);
CREATE TRIGGER change_log_no_update BEFORE UPDATE ON change_log
BEGIN SELECT RAISE(ABORT, 'change_log is append-only'); END;
CREATE TRIGGER change_log_no_delete BEFORE DELETE ON change_log
BEGIN SELECT RAISE(ABORT, 'change_log is append-only'); END;
"""

MIGRATIONS: list[tuple[int, str]] = [(1, MIGRATION_1)]
CURRENT_VERSION = MIGRATIONS[-1][0]


def current_version(conn: sqlite3.Connection) -> int:
    """The highest applied migration, or 0 for a new database."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_version'"
    ).fetchone()
    if not exists:
        return 0
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return int(row[0] or 0)


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply every migration newer than the database; return the resulting version."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = current_version(conn)
    for version, sql in MIGRATIONS:
        if version <= applied:
            continue
        with conn:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat()),
            )
        applied = version
    return applied
