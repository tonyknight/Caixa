"""Migration 6: documents in the master database (ticket 20261124-03)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from caixa.master import Master
from caixa.schema import CURRENT_VERSION, MIGRATIONS, apply_migrations

DOCUMENT_TABLES = {
    "authors",
    "author_aliases",
    "documents",
    "document_sources",
    "document_pages",
    "documents_fts",
    "document_runs",
    "document_fields",
    "tags",
    "document_tags",
    "chunks",
}
NOW = datetime(2024, 12, 1, tzinfo=timezone.utc).isoformat()


def _tables(db: sqlite3.Connection) -> set[str]:
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _document(db: sqlite3.Connection, item_id: str = "pdf:abc") -> None:
    db.execute(
        "INSERT INTO items (id, type, collector, timestamp_utc, time_precision, content_hash) "
        "VALUES (?, 'document', 'pdf', '2024-11-30T00:00:00+00:00', 'day', 'h')",
        (item_id,),
    )
    db.execute(
        "INSERT INTO documents (item_id, format, original_filename, source_sha256, size, "
        "created_at, updated_at) VALUES (?, 'pdf', 'a.pdf', ?, 10, ?, ?)",
        (item_id, item_id.split(":")[1], NOW, NOW),
    )


def test_the_current_version_is_6() -> None:
    assert CURRENT_VERSION == 6 and MIGRATIONS[-1][0] == 6


def test_a_new_master_has_the_document_tables(tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        assert DOCUMENT_TABLES <= _tables(master.connection)


def test_a_version_5_master_is_migrated(tmp_path: Path) -> None:
    path = tmp_path / "caixa.sqlite"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        for version, sql in MIGRATIONS[:5]:
            db.executescript(sql)
            db.execute("INSERT INTO schema_version VALUES (?, ?)", (version, NOW))
    with sqlite3.connect(path) as db:
        assert "documents" not in _tables(db)
        assert apply_migrations(db) == 6
        assert DOCUMENT_TABLES <= _tables(db)


def _search(db: sqlite3.Connection, words: str) -> list[int]:
    return [
        r[0]
        for r in db.execute(
            "SELECT p.page FROM documents_fts f JOIN document_pages p ON p.id = f.rowid "
            "WHERE documents_fts MATCH ? ORDER BY p.page",
            (words,),
        )
    ]


def test_page_text_is_searchable_and_follows_its_page(tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        db = master.connection
        _document(db)
        db.execute(
            "INSERT INTO document_pages (item_id, page, text, source) VALUES "
            "('pdf:abc', 1, 'Banco Atlântico — conta 4821', 'pdf'), "
            "('pdf:abc', 2, 'Contador 77812', 'ocr')"
        )
        assert _search(db, "atlantico") == [1]  # accents are ignored
        assert _search(db, "4821") == [1] and _search(db, "77812") == [2]
        db.execute("UPDATE document_pages SET text = 'Saldo final' WHERE page = 1")
        assert _search(db, "4821") == [] and _search(db, "saldo") == [1]
        db.execute("DELETE FROM document_pages WHERE page = 2")
        assert _search(db, "77812") == []


def test_the_starter_tags_are_there(tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        starters = {
            r[0] for r in master.connection.execute("SELECT name FROM tags WHERE starter = 1")
        }
    assert {"statement", "bill", "receipt", "tax", "insurance", "medical"} <= starters


def test_deleting_a_document_item_takes_its_rows(tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        db = master.connection
        _document(db)
        db.execute("INSERT INTO document_pages (item_id, page, text) VALUES ('pdf:abc', 1, 'x y')")
        db.execute(
            "INSERT INTO document_sources (item_id, path, filename, first_seen) "
            "VALUES ('pdf:abc', '/in/a.pdf', 'a.pdf', ?)",
            (NOW,),
        )
        run = db.execute(
            "INSERT INTO document_runs (item_id, stage, result, at) "
            "VALUES ('pdf:abc', 'import', 'ok', ?)",
            (NOW,),
        ).lastrowid
        db.execute(
            "INSERT INTO document_fields (item_id, field, value, source, run_id) "
            "VALUES ('pdf:abc', 'title', 'A', 'ai_inference', ?)",
            (run,),
        )
        db.execute("INSERT INTO document_tags (item_id, tag) VALUES ('pdf:abc', 'statement')")
        db.execute("INSERT INTO chunks (item_id, page, text) VALUES ('pdf:abc', 1, 'x y')")
        assert master.delete_items(["pdf:abc"]) == 1
        for table in (
            "documents", "document_pages", "document_sources", "document_runs",
            "document_fields", "document_tags", "chunks",
        ):  # fmt: skip
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table
        assert _search(db, "x") == []
