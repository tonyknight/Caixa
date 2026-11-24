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
- `documents` and around it (Phase 1.5 - PDF): every document filed in the box (one `items` row
  each, type `document`), where it was found (`document_sources`), the text of each page and its
  full-text index (`document_pages`, `documents_fts`), every fact with where it came from
  (`document_fields`), what was done to it (`document_runs`), its tags, its author (`authors`,
  `author_aliases`), and the passages semantic search reads (`chunks`).
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

# Version 5: subcategories of the four categories people are sorted into (two levels at most), and
# the subcategory a person is in (NULL: the category itself).
MIGRATION_5 = """
CREATE TABLE subcategories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    parent_id INTEGER REFERENCES subcategories (id),
    name TEXT NOT NULL COLLATE NOCASE
);
CREATE UNIQUE INDEX subcategories_unique ON subcategories (category, COALESCE(parent_id, 0), name);
ALTER TABLE people ADD COLUMN subcategory_id INTEGER REFERENCES subcategories (id);
"""

# Version 6: documents (Phase 1.5 - PDF). A document is an `items` row (type `document`, id
# `<format>:<source sha256>`); its facts are in `documents`, each fact's sources and evidence in
# `document_fields`. Page text is indexed by `documents_fts` (external content, kept in step by
# triggers), accents ignored. `chunks` is keyed by item so other domains can add theirs later.
MIGRATION_6 = """
CREATE TABLE authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    kind TEXT NOT NULL DEFAULT 'organization' CHECK (kind IN ('organization', 'person')),
    person_id INTEGER REFERENCES people (id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE author_aliases (
    author_id INTEGER NOT NULL REFERENCES authors (id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized TEXT NOT NULL UNIQUE
);
CREATE INDEX author_aliases_by_author ON author_aliases (author_id);

CREATE TABLE documents (
    item_id TEXT PRIMARY KEY REFERENCES items (id),
    format TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL UNIQUE,
    archived_sha256 TEXT,
    size INTEGER NOT NULL,
    pages INTEGER,
    title TEXT,
    author_id INTEGER REFERENCES authors (id),
    category TEXT,
    type TEXT,
    date TEXT,
    date_precision TEXT CHECK (date_precision IN ('day', 'month', 'year')),
    date_kind TEXT,
    summary TEXT,
    summary_model TEXT,
    processing_status TEXT NOT NULL DEFAULT 'archived'
        CHECK (processing_status IN ('archived', 'needs_review', 'failed')),
    ocr_status TEXT NOT NULL DEFAULT 'not_needed'
        CHECK (ocr_status IN ('not_needed', 'done', 'partial', 'needs_ocr', 'failed')),
    validation_status TEXT NOT NULL DEFAULT 'passed'
        CHECK (validation_status IN ('passed', 'unchanged_copy', 'failed')),
    ai_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (ai_status IN ('pending', 'processing', 'completed', 'needs_review', 'failed')),
    review TEXT NOT NULL DEFAULT '[]',
    text_hash TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX documents_by_author ON documents (author_id);
CREATE INDEX documents_by_date ON documents (date);
CREATE INDEX documents_by_text ON documents (text_hash);

CREATE TABLE document_sources (
    item_id TEXT NOT NULL REFERENCES items (id),
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    size INTEGER,
    modified TEXT,
    first_seen TEXT NOT NULL,
    import_id INTEGER REFERENCES imports (id),
    PRIMARY KEY (item_id, path)
);

CREATE TABLE document_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items (id),
    page INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'pdf' CHECK (source IN ('pdf', 'ocr')),
    class TEXT,
    quality TEXT,
    UNIQUE (item_id, page)
);
CREATE VIRTUAL TABLE documents_fts USING fts5(
    text, content = 'document_pages', content_rowid = 'id',
    tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TRIGGER document_pages_indexed AFTER INSERT ON document_pages BEGIN
    INSERT INTO documents_fts (rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER document_pages_unindexed AFTER DELETE ON document_pages BEGIN
    INSERT INTO documents_fts (documents_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER document_pages_reindexed AFTER UPDATE OF text ON document_pages BEGIN
    INSERT INTO documents_fts (documents_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO documents_fts (rowid, text) VALUES (new.id, new.text);
END;

CREATE TABLE document_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items (id),
    stage TEXT NOT NULL
        CHECK (stage IN ('import', 'inspect', 'ocr', 'validate', 'enrich', 'reprocess', 'correct')),
    tool TEXT,
    version TEXT,
    settings TEXT,
    model TEXT,
    provider TEXT,
    prompt_version TEXT,
    schema_version TEXT,
    result TEXT NOT NULL,
    report TEXT,
    at TEXT NOT NULL
);
CREATE INDEX document_runs_by_item ON document_runs (item_id);

CREATE TABLE document_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items (id),
    field TEXT NOT NULL,
    value TEXT,
    number REAL,
    source TEXT NOT NULL CHECK (source IN (
        'original_filename', 'pdf_metadata', 'pdf_content', 'ocr', 'ai_inference', 'user_verified'
    )),
    evidence TEXT,
    page INTEGER,
    state TEXT NOT NULL DEFAULT 'proposed'
        CHECK (state IN ('proposed', 'applied', 'conflict', 'rejected')),
    run_id INTEGER REFERENCES document_runs (id) ON DELETE SET NULL
);
CREATE INDEX document_fields_by_item ON document_fields (item_id, field);

CREATE TABLE tags (
    name TEXT PRIMARY KEY COLLATE NOCASE,
    starter INTEGER NOT NULL DEFAULT 0 CHECK (starter IN (0, 1))
);
INSERT INTO tags (name, starter) VALUES
    ('banking', 1), ('statement', 1), ('bill', 1), ('utilities', 1), ('receipt', 1),
    ('invoice', 1), ('cheque', 1), ('tax', 1), ('insurance', 1), ('medical', 1), ('legal', 1),
    ('property', 1), ('correspondence', 1), ('pension', 1), ('car', 1), ('home', 1);
CREATE TABLE document_tags (
    item_id TEXT NOT NULL REFERENCES items (id),
    tag TEXT NOT NULL COLLATE NOCASE,
    source TEXT NOT NULL DEFAULT 'ai_inference' CHECK (source IN ('ai_inference', 'user_verified')),
    PRIMARY KEY (item_id, tag)
);

CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL REFERENCES items (id),
    page INTEGER,
    start INTEGER,
    end INTEGER,
    text TEXT NOT NULL,
    embedding BLOB,
    embedding_model TEXT
);
CREATE INDEX chunks_by_item ON chunks (item_id);
"""

# Version 7: whether a fact's evidence was found where it was said to be (NULL: nothing to check).
MIGRATION_7 = """
ALTER TABLE document_fields ADD COLUMN verified INTEGER CHECK (verified IN (0, 1));
"""

MIGRATIONS: list[tuple[int, str]] = [
    (1, MIGRATION_1),
    (2, MIGRATION_2),
    (3, MIGRATION_3),
    (4, MIGRATION_4),
    (5, MIGRATION_5),
    (6, MIGRATION_6),
    (7, MIGRATION_7),
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
