"""The master's record of documents: the one place that writes the document tables (migration 6).

A document is an `items` row (type `document`, collector its format, id `<format>:<source sha256>`)
and a `documents` row with its facts. Around it:

- `document_sources`: every place the same file was found (importing it again from elsewhere adds
  a row and nothing else);
- `document_pages`: each page's text, from the PDF or from OCR, indexed in `documents_fts`;
- `document_fields`: every candidate value of a fact, with its source (the filename, the PDF's
  properties, its text, OCR, a model, the owner), its evidence and page, and whether it was applied;
- `document_runs`: what was done to it (import, OCR, validation, enrichment…), with which tool;
- `document_tags`: its tags, each with who gave it (a model or the owner);
- `authors` and `author_aliases`: who issued it, found again by any way their name is written
  (accents and case aside).

The `items` row's time is the document's naming date at its precision (midnight UTC); an undated
document has an empty time and the precision `unknown`. Its `text` is the summary (page text lives
in `document_pages`), `file_path` the archived file's path relative to the box, `content_hash` the
archived file's SHA-256.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any, Iterable, Optional, Sequence

from caixa.master import Master

#: The columns of `documents` a `DocumentRecord` sets, in order.
COLUMNS = (
    "format",
    "original_filename",
    "source_sha256",
    "archived_sha256",
    "size",
    "pages",
    "title",
    "author_id",
    "category",
    "type",
    "date",
    "date_precision",
    "date_kind",
    "summary",
    "summary_model",
    "processing_status",
    "ocr_status",
    "validation_status",
    "ai_status",
    "review",
    "text_hash",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DocumentRecord:
    """What is known about one document, as `save_document` stores it."""

    format: str
    original_filename: str
    source_sha256: str
    size: int
    file_path: str  # the archived file, relative to the box
    archived_sha256: Optional[str] = None
    pages: Optional[int] = None
    title: Optional[str] = None
    author: Optional[str] = None
    author_kind: str = "organization"
    type: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = None  # the naming date: YYYY, YYYY-MM or YYYY-MM-DD
    date_precision: Optional[str] = None  # day | month | year
    date_kind: Optional[str] = None
    summary: Optional[str] = None
    summary_model: Optional[str] = None
    processing_status: str = "archived"
    ocr_status: str = "not_needed"
    validation_status: str = "passed"
    ai_status: str = "pending"
    review: list[str] = field(default_factory=list)
    text_hash: Optional[str] = None


@dataclass(frozen=True)
class PageText:
    page: int  # from 1
    text: str
    source: str = "pdf"  # pdf | ocr
    page_class: Optional[str] = None  # text | needs_ocr | ocr_layer | broken_text | blank
    quality: Optional[dict[str, Any]] = None


def item_id_for(format: str, source_sha256: str) -> str:
    return f"{format}:{source_sha256}"


def normalize_author(name: str) -> str:
    """How an author's name is compared: no accents, no case, single spaces."""
    decomposed = unicodedata.normalize("NFKD", name)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", plain).strip().casefold()


# --- Authors -------------------------------------------------------------------------------------


def find_author(master: Master, name: str) -> Optional[int]:
    row = master.connection.execute(
        "SELECT author_id FROM author_aliases WHERE normalized = ?", (normalize_author(name),)
    ).fetchone()
    return int(row[0]) if row else None


def author_names(master: Master) -> list[str]:
    """Every author's name and every other way it is written (for finding them in filenames)."""
    rows = master.connection.execute(
        "SELECT name FROM authors UNION SELECT alias FROM author_aliases"
    ).fetchall()
    return [str(r[0]) for r in rows]


def add_author_alias(master: Master, author_id: int, alias: str) -> None:
    master.connection.execute(
        "INSERT OR IGNORE INTO author_aliases (author_id, alias, normalized) VALUES (?, ?, ?)",
        (author_id, alias, normalize_author(alias)),
    )


def author_id(master: Master, name: str, kind: str = "organization") -> int:
    """The author known by `name` (any alias, accents and case aside), made when new."""
    found = find_author(master, name)
    if found is not None:
        return found
    db = master.connection
    row = db.execute("SELECT id FROM authors WHERE name = ?", (name,)).fetchone()
    if row is None:
        cur = db.execute(
            "INSERT INTO authors (name, kind, created_at) VALUES (?, ?, ?)", (name, kind, _now())
        )
        row = (cur.lastrowid,)
    add_author_alias(master, int(row[0]), name)
    return int(row[0])


# --- Documents -----------------------------------------------------------------------------------


def _timestamp(date: Optional[str], precision: Optional[str]) -> tuple[str, str]:
    if not date:
        return "", "unknown"
    parts = date.split("-") + ["01", "01"]
    year, month, day = parts[0], parts[1], parts[2]
    return f"{year}-{month}-{day}T00:00:00+00:00", precision or "day"


def find_by_source(master: Master, source_sha256: str) -> Optional[str]:
    row = master.connection.execute(
        "SELECT item_id FROM documents WHERE source_sha256 = ?", (source_sha256,)
    ).fetchone()
    return str(row[0]) if row else None


def find_by_text(master: Master, text_hash: str) -> Optional[str]:
    """A document whose text has this fingerprint (`caixa.documents.pdf.inspect.text_hash`)."""
    row = master.connection.execute(
        "SELECT item_id FROM documents WHERE text_hash = ? ORDER BY created_at LIMIT 1",
        (text_hash,),
    ).fetchone()
    return str(row[0]) if row else None


def save_document(
    master: Master, record: DocumentRecord, import_id: Optional[int]
) -> tuple[str, str]:
    """Insert or update a document and its item; returns `(item_id, outcome)`, the outcome being
    `inserted`, `updated` or `unchanged`. A change raises the item's version in the change log."""
    db = master.connection
    item_id = item_id_for(record.format, record.source_sha256)
    who = author_id(master, record.author, record.author_kind) if record.author else None
    values = {
        **{name: getattr(record, name, None) for name in COLUMNS if name != "author_id"},
        "author_id": who,
        "review": json.dumps(sorted(set(record.review))),
    }
    stamp, precision = _timestamp(record.date, record.date_precision)
    item = (stamp, precision, record.summary, record.file_path, record.archived_sha256 or "")
    known = db.execute(
        f"SELECT {', '.join(COLUMNS)} FROM documents WHERE item_id = ?", (item_id,)
    ).fetchone()
    now = _now()
    if known is None:
        db.execute(
            "INSERT INTO items (id, type, collector, timestamp_utc, time_precision, text, "
            "file_path, content_hash, first_import_id, last_import_id) "
            "VALUES (?, 'document', ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, record.format, *item, import_id, import_id),
        )
        db.execute(
            f"INSERT INTO documents (item_id, {', '.join(COLUMNS)}, created_at, updated_at) "
            f"VALUES (?, {', '.join('?' for _ in COLUMNS)}, ?, ?)",
            (item_id, *(values[name] for name in COLUMNS), now, now),
        )
        master.log_change(item_id, "insert", 1, import_id)
        return item_id, "inserted"
    current = db.execute(
        "SELECT timestamp_utc, time_precision, text, file_path, content_hash, version "
        "FROM items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if tuple(known) == tuple(values[name] for name in COLUMNS) and tuple(current)[:5] == item:
        return item_id, "unchanged"
    version = int(current["version"]) + 1
    db.execute(
        "UPDATE items SET timestamp_utc = ?, time_precision = ?, text = ?, file_path = ?, "
        "content_hash = ?, version = ?, last_import_id = COALESCE(?, last_import_id) WHERE id = ?",
        (*item, version, import_id, item_id),
    )
    db.execute(
        f"UPDATE documents SET {', '.join(f'{name} = ?' for name in COLUMNS)}, updated_at = ? "
        "WHERE item_id = ?",
        (*(values[name] for name in COLUMNS), now, item_id),
    )
    master.log_change(item_id, "update", version, import_id)
    return item_id, "updated"


def load_record(master: Master, item_id: str) -> DocumentRecord:
    """The record `save_document` would write for a document as it is now (`KeyError` without
    one): change what is new, then save it."""
    row = master.connection.execute(
        "SELECT d.*, a.name AS author_name, a.kind AS author_kind, i.file_path "
        "FROM documents d JOIN items i ON i.id = d.item_id "
        "LEFT JOIN authors a ON a.id = d.author_id WHERE d.item_id = ?",
        (item_id,),
    ).fetchone()
    if row is None:
        raise KeyError(item_id)
    names = {name for name in COLUMNS if name not in ("author_id", "review")}
    return DocumentRecord(
        **{name: row[name] for name in names},
        file_path=row["file_path"],
        author=row["author_name"],
        author_kind=row["author_kind"] or "organization",
        review=json.loads(row["review"] or "[]"),
    )


def add_source(
    master: Master,
    item_id: str,
    path: str,
    size: Optional[int],
    modified: Optional[str],
    import_id: Optional[int],
) -> bool:
    """Record a place the document's file was found; False when that place was known."""
    cur = master.connection.execute(
        "INSERT OR IGNORE INTO document_sources (item_id, path, filename, size, modified, "
        "first_seen, import_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (item_id, path, PurePath(path).name, size, modified, _now(), import_id),
    )
    return cur.rowcount > 0


def set_pages(master: Master, item_id: str, pages: Sequence[PageText]) -> None:
    """Replace the document's page text (the full-text index follows by its triggers)."""
    db = master.connection
    db.execute("DELETE FROM document_pages WHERE item_id = ?", (item_id,))
    db.executemany(
        "INSERT INTO document_pages (item_id, page, text, source, class, quality) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                item_id, p.page, p.text, p.source, p.page_class,
                json.dumps(p.quality) if p.quality is not None else None,
            )  # fmt: skip
            for p in pages
        ],
    )


def add_run(
    master: Master,
    item_id: str,
    stage: str,
    result: str,
    *,
    tool: Optional[str] = None,
    version: Optional[str] = None,
    settings: Optional[dict[str, Any]] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    prompt_version: Optional[str] = None,
    schema_version: Optional[str] = None,
    report: Optional[dict[str, Any]] = None,
) -> int:
    """Record what was done to a document; returns the run's id."""
    cur = master.connection.execute(
        "INSERT INTO document_runs (item_id, stage, tool, version, settings, model, provider, "
        "prompt_version, schema_version, result, report, at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            item_id, stage, tool, version, json.dumps(settings) if settings else None, model,
            provider, prompt_version, schema_version, result,
            json.dumps(report) if report else None, _now(),
        ),
    )  # fmt: skip
    return int(cur.lastrowid or 0)


def add_field(
    master: Master,
    item_id: str,
    name: str,
    value: Optional[str],
    source: str,
    *,
    evidence: Optional[str] = None,
    page: Optional[int] = None,
    number: Optional[float] = None,
    state: str = "proposed",
    run_id: Optional[int] = None,
    verified: Optional[bool] = None,
) -> int:
    """Record one candidate value of a fact, with where it came from; `verified` says whether its
    evidence was found where it was said to be (None: nothing to check)."""
    cur = master.connection.execute(
        "INSERT INTO document_fields (item_id, field, value, number, source, evidence, page, "
        "state, run_id, verified) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            item_id, name, value, number, source, evidence, page, state, run_id,
            None if verified is None else int(bool(verified)),
        ),
    )  # fmt: skip
    return int(cur.lastrowid or 0)


def clear_fields(master: Master, item_id: str, source: str) -> int:
    """Forget a document's facts from one source (a model's earlier reading); returns how many."""
    cur = master.connection.execute(
        "DELETE FROM document_fields WHERE item_id = ? AND source = ?", (item_id, source)
    )
    return cur.rowcount


def set_tags(master: Master, item_id: str, tags: Iterable[str], source: str) -> None:
    """The document's tags from `source` (a model, or the owner) become `tags`; tags from the other
    source stay, and a tag the owner gave is never taken over by a model's."""
    db = master.connection
    wanted = {re.sub(r"\s+", " ", t).strip().casefold() for t in tags if t and t.strip()}
    if source == "ai_inference":  # what the owner took off stays off
        from caixa.documents.tags import rejected_tags

        wanted -= rejected_tags(master, item_id)
    db.execute("DELETE FROM document_tags WHERE item_id = ? AND source = ?", (item_id, source))
    for tag in sorted(wanted):
        db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        db.execute(
            "INSERT OR IGNORE INTO document_tags (item_id, tag, source) VALUES (?, ?, ?)",
            (item_id, tag, source),
        )


# --- Reading ---------------------------------------------------------------------------------------

_LISTED = (
    "d.item_id, d.format, d.original_filename, d.title, a.name AS author, d.type, d.category, "
    "d.date, d.date_precision, d.date_kind, d.summary, d.summary_model, d.pages, "
    "d.processing_status, d.ocr_status, d.validation_status, d.ai_status, d.review, "
    "i.file_path"
)


def _plain(row: Any) -> dict[str, Any]:
    data = dict(row)
    if "review" in data:
        data["review"] = json.loads(data["review"] or "[]")
    return data


def list_documents(
    master: Master,
    *,
    type: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[int] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Documents by date (undated last), optionally only those of a type, an author, a year, a
    processing status or a tag."""
    where, args = [], []  # type: tuple[list[str], list[Any]]
    if type:
        where.append("d.type = ?")
        args.append(type)
    if author:
        found = find_author(master, author)
        where.append("d.author_id = ?")
        args.append(found if found is not None else -1)
    if year:
        where.append("substr(d.date, 1, 4) = ?")
        args.append(f"{int(year):04d}")
    if status:
        where.append("d.processing_status = ?")
        args.append(status)
    if tag:
        where.append("d.item_id IN (SELECT item_id FROM document_tags WHERE tag = ?)")
        args.append(tag.casefold())
    sql = (
        f"SELECT {_LISTED} FROM documents d JOIN items i ON i.id = d.item_id "
        "LEFT JOIN authors a ON a.id = d.author_id"
        + (f" WHERE {' AND '.join(where)}" if where else "")
        + " ORDER BY d.date IS NULL, d.date, d.title, d.item_id"
    )
    return [_plain(row) for row in master.connection.execute(sql, args)]


def get_document(master: Master, item_id: str) -> dict[str, Any]:
    """Everything known about one document; `KeyError` when there is none."""
    db = master.connection
    row = db.execute(
        f"SELECT {_LISTED}, d.source_sha256, d.archived_sha256, d.size, d.text_hash, "
        "d.created_at, d.updated_at FROM documents d JOIN items i ON i.id = d.item_id "
        "LEFT JOIN authors a ON a.id = d.author_id WHERE d.item_id = ?",
        (item_id,),
    ).fetchone()
    if row is None:
        raise KeyError(item_id)
    found = _plain(row)
    found["sources"] = [
        dict(r)
        for r in db.execute(
            "SELECT path, filename, size, modified, first_seen, import_id FROM document_sources "
            "WHERE item_id = ? ORDER BY first_seen, path",
            (item_id,),
        )
    ]
    found["tags"] = [
        dict(r)
        for r in db.execute(
            "SELECT tag, source FROM document_tags WHERE item_id = ? ORDER BY tag", (item_id,)
        )
    ]
    found["fields"] = [
        dict(r)
        for r in db.execute(
            "SELECT id, field, value, number, source, evidence, page, state, run_id, verified "
            "FROM document_fields WHERE item_id = ? ORDER BY field, id",
            (item_id,),
        )
    ]
    found["runs"] = [
        {
            **dict(r),
            "settings": json.loads(r["settings"]) if r["settings"] else None,
            "report": json.loads(r["report"]) if r["report"] else None,
        }
        for r in db.execute("SELECT * FROM document_runs WHERE item_id = ? ORDER BY id", (item_id,))
    ]
    return found


__all__ = [
    "DocumentRecord",
    "PageText",
    "add_author_alias",
    "add_field",
    "add_run",
    "add_source",
    "clear_fields",
    "author_id",
    "author_names",
    "find_author",
    "find_by_source",
    "find_by_text",
    "get_document",
    "item_id_for",
    "list_documents",
    "load_record",
    "normalize_author",
    "save_document",
    "set_pages",
    "set_tags",
]
