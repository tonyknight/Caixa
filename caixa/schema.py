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
- `accounts`, `mail`, `mail_accounts`, `mail_threads`: the mail imported through Caixa's mail
  workflow (Phase 1.5), each mail with its facts and account, each conversation with its summary.
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

# Version 2: the category a person is sorted into on the box's index page (NULL: not yet).
MIGRATION_2 = """
ALTER TABLE people ADD COLUMN category TEXT;
"""

# Version 3: items can be deleted (their owner took someone out of the box), and the change log
# says so. The log's CHECK names the operations, so the table is made again with the old rows.
MIGRATION_3 = """
CREATE TABLE change_log_3 (
    change INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('insert', 'update', 'link', 'delete')),
    version INTEGER NOT NULL,
    import_id INTEGER REFERENCES imports (id),
    at TEXT NOT NULL
);
INSERT INTO change_log_3 SELECT change, item_id, operation, version, import_id, at FROM change_log;
DROP TABLE change_log;
ALTER TABLE change_log_3 RENAME TO change_log;
CREATE TRIGGER change_log_no_update BEFORE UPDATE ON change_log
BEGIN SELECT RAISE(ABORT, 'change_log is append-only'); END;
CREATE TRIGGER change_log_no_delete BEFORE DELETE ON change_log
BEGIN SELECT RAISE(ABORT, 'change_log is append-only'); END;
"""

# Version 4: mail (Phase 1.5): the accounts mail comes from, the facts of every imported mail (its
# plain text is its item's `text`), the accounts a mail was seen in, and each conversation with what
# later steps add to it (the page that shows it, the person it is filed with, its summary).
MIGRATION_4 = """
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE mail (
    item_id TEXT PRIMARY KEY REFERENCES items (id),
    account_id INTEGER NOT NULL REFERENCES accounts (id),
    message_id TEXT,
    thread_key TEXT NOT NULL,
    date_utc TEXT NOT NULL,
    tz_offset_minutes INTEGER,
    sender_address TEXT,
    sender_name TEXT,
    recipients TEXT NOT NULL DEFAULT '[]',
    subject TEXT NOT NULL DEFAULT ''
);
CREATE INDEX mail_by_thread ON mail (thread_key);
CREATE INDEX mail_by_sender ON mail (sender_address);
CREATE TABLE mail_accounts (
    item_id TEXT NOT NULL REFERENCES items (id),
    account_id INTEGER NOT NULL REFERENCES accounts (id),
    PRIMARY KEY (item_id, account_id)
);
CREATE TABLE mail_threads (
    thread_key TEXT PRIMARY KEY,
    account_id INTEGER REFERENCES accounts (id),
    subject TEXT NOT NULL DEFAULT '',
    first_utc TEXT,
    last_utc TEXT,
    mails INTEGER NOT NULL DEFAULT 0,
    files INTEGER NOT NULL DEFAULT 0,
    home_person_id INTEGER REFERENCES people (id),
    page TEXT,
    summary TEXT,
    summary_model TEXT,
    summary_at TEXT,
    summary_hash TEXT
);
"""

MIGRATIONS: list[tuple[int, str]] = [
    (1, MIGRATION_1),
    (2, MIGRATION_2),
    (3, MIGRATION_3),
    (4, MIGRATION_4),
]
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
