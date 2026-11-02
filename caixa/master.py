"""`Master`: Caixa's master database (`<box>/.caixa/caixa.sqlite`).

People and the names they are known by, the imports that fed the box, and the append-only change
log. The collectors' adapters (see `caixa.collectors`) write items and their links through this
connection; the people page and `aliases.json` read it.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Optional, Union

from caixa.schema import apply_migrations, current_version

PathLike = Union[str, Path]
ALIAS_KINDS = ("phone", "email", "username", "name")
OPERATIONS = ("insert", "update", "link")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_alias(value: str, kind: str) -> str:
    """The comparable form of an alias: digits for a phone, lower case for the rest."""
    text = value.strip()
    if kind == "phone":
        digits = re.sub(r"\D", "", text)
        return ("+" if text.startswith("+") else "") + digits
    if kind == "email":
        return text.lower()
    return re.sub(r"\s+", " ", text).casefold()


@dataclass(frozen=True)
class Person:
    id: int
    name: str
    is_owner: bool


@dataclass(frozen=True)
class Alias:
    id: int
    person_id: int
    kind: str
    value: str
    normalized: str
    service: Optional[str]
    source: str


@dataclass(frozen=True)
class ImportRecord:
    id: int
    collector: str
    source: Optional[str]
    started_at: str
    finished_at: Optional[str]
    inserted: int
    updated: int
    unchanged: int
    linked: int
    status: str


@dataclass(frozen=True)
class Change:
    change: int
    item_id: str
    operation: str
    version: int
    import_id: Optional[int]
    at: str


class Master:
    """The master database; use as a context manager."""

    def __init__(self, path: PathLike) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, uri=True)  # uri: lets ATTACH open "file:" paths
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA journal_mode = WAL")
        apply_migrations(self._db)

    def __enter__(self) -> "Master":
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        if exc_type is None:
            self._db.commit()
        else:
            self._db.rollback()
        self._db.close()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._db

    @property
    def version(self) -> int:
        return current_version(self._db)

    def commit(self) -> None:
        self._db.commit()

    # --- People -----------------------------------------------------------------------------

    def add_person(self, name: str, is_owner: bool = False) -> int:
        """The id of the person with this name (case-insensitive), creating them if new."""
        clean = re.sub(r"\s+", " ", name).strip()
        if not clean:
            raise ValueError("A person needs a name; the name was empty.")
        existing = self.person_id(clean)
        if existing is not None:
            return existing
        if is_owner and self.owner_id() is not None:
            raise ValueError("The box already has an owner.")
        cur = self._db.execute(
            "INSERT INTO people (name, is_owner, created_at) VALUES (?, ?, ?)",
            (clean, int(is_owner), _now()),
        )
        return int(cur.lastrowid or 0)

    def person_id(self, name: str) -> Optional[int]:
        row = self._db.execute(
            "SELECT id FROM people WHERE name = ?", (re.sub(r"\s+", " ", name).strip(),)
        ).fetchone()
        return int(row[0]) if row else None

    def owner_id(self) -> Optional[int]:
        row = self._db.execute("SELECT id FROM people WHERE is_owner = 1").fetchone()
        return int(row[0]) if row else None

    def people(self) -> list[Person]:
        return [
            Person(r["id"], r["name"], bool(r["is_owner"]))
            for r in self._db.execute("SELECT * FROM people ORDER BY name COLLATE NOCASE")
        ]

    # --- Aliases ----------------------------------------------------------------------------

    def add_alias(
        self,
        person_id: int,
        value: str,
        kind: str,
        service: Optional[str] = None,
        source: str = "human",
        move: bool = False,
    ) -> int:
        """Record a name, number, address or username for a person.

        The same alias can't name two people: `move=True` hands it over to this person.
        """
        if kind not in ALIAS_KINDS:
            raise ValueError(f"Unknown alias kind '{kind}'; use one of {', '.join(ALIAS_KINDS)}.")
        if not value.strip():
            raise ValueError("An alias can't be empty.")
        normalized = normalize_alias(value, kind)
        row = self._db.execute(
            "SELECT id, person_id FROM aliases WHERE kind = ? AND normalized = ? "
            "AND COALESCE(service, '') = ?",
            (kind, normalized, service or ""),
        ).fetchone()
        if row:
            if row["person_id"] == person_id:
                return int(row["id"])
            if not move:
                other = self._db.execute(
                    "SELECT name FROM people WHERE id = ?", (row["person_id"],)
                ).fetchone()[0]
                raise ValueError(f"'{value}' already names {other}.")
            self._db.execute(
                "UPDATE aliases SET person_id = ? WHERE id = ?", (person_id, row["id"])
            )
            return int(row["id"])
        cur = self._db.execute(
            "INSERT INTO aliases (person_id, kind, value, normalized, service, source) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (person_id, kind, value.strip(), normalized, service, source),
        )
        return int(cur.lastrowid or 0)

    def aliases(self, person_id: Optional[int] = None) -> list[Alias]:
        rows = self._db.execute(
            "SELECT * FROM aliases"
            + (" WHERE person_id = ?" if person_id else "")
            + " ORDER BY id",
            (person_id,) if person_id else (),
        )
        return [
            Alias(
                r["id"],
                r["person_id"],
                r["kind"],
                r["value"],
                r["normalized"],
                r["service"],
                r["source"],
            )
            for r in rows
        ]

    def find_person(self, value: str, service: Optional[str] = None) -> Optional[int]:
        """The person an identifier belongs to (any kind of alias), if one is known."""
        candidates = {normalize_alias(value, kind) for kind in ALIAS_KINDS} - {""}
        marks = ",".join("?" for _ in candidates)
        row = self._db.execute(
            f"SELECT person_id FROM aliases WHERE normalized IN ({marks}) "
            "AND (service IS NULL OR service = ?) ORDER BY service IS NULL LIMIT 1",
            (*sorted(candidates), service),
        ).fetchone()
        return int(row[0]) if row else None

    def export_aliases(self, path: PathLike) -> int:
        """Write `aliases.json` (`{identifier or name: person}`, as Chattr reads it)."""
        mapping = {
            r["value"]: r["name"]
            for r in self._db.execute(
                "SELECT a.value, p.name FROM aliases a JOIN people p ON p.id = a.person_id "
                "ORDER BY a.value, a.id"
            )
        }
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return len(mapping)

    # --- Imports and the change log ---------------------------------------------------------

    def start_import(self, collector: str, source: Optional[PathLike] = None) -> int:
        cur = self._db.execute(
            "INSERT INTO imports (collector, source, started_at) VALUES (?, ?, ?)",
            (collector, str(source) if source is not None else None, _now()),
        )
        return int(cur.lastrowid or 0)

    def finish_import(
        self,
        import_id: int,
        inserted: int = 0,
        updated: int = 0,
        unchanged: int = 0,
        linked: int = 0,
        status: str = "done",
        details: Optional[str] = None,
    ) -> None:
        self._db.execute(
            "UPDATE imports SET finished_at = ?, inserted = ?, updated = ?, unchanged = ?, "
            "linked = ?, status = ?, details = ? WHERE id = ?",
            (_now(), inserted, updated, unchanged, linked, status, details, import_id),
        )

    def imports(self) -> list[ImportRecord]:
        return [
            ImportRecord(
                r["id"], r["collector"], r["source"], r["started_at"], r["finished_at"],
                r["inserted"], r["updated"], r["unchanged"], r["linked"], r["status"],
            )  # fmt: skip
            for r in self._db.execute("SELECT * FROM imports ORDER BY id")
        ]

    def log_change(
        self, item_id: str, operation: str, version: int, import_id: Optional[int]
    ) -> int:
        """Append to the change log; returns the new change number."""
        if operation not in OPERATIONS:
            raise ValueError(
                f"Unknown operation '{operation}'; use one of {', '.join(OPERATIONS)}."
            )
        cur = self._db.execute(
            "INSERT INTO change_log (item_id, operation, version, import_id, at) "
            "VALUES (?, ?, ?, ?, ?)",
            (item_id, operation, version, import_id, _now()),
        )
        return int(cur.lastrowid or 0)

    def changes(self, since: int = 0) -> list[Change]:
        """The change log after change number `since`, oldest first."""
        return [
            Change(r["change"], r["item_id"], r["operation"], r["version"], r["import_id"], r["at"])
            for r in self._db.execute(
                "SELECT * FROM change_log WHERE change > ? ORDER BY change", (since,)
            )
        ]
