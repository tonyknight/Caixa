"""The authors documents are filed under: listed, renamed and merged, their folders following.

An author's name is its folder in each year (`Documents/PDF/<YYYY>/<Author>/`) and the end of its
documents' archival names. Renaming an author moves and renames every file of theirs, and keeps
the old name as an alias, so the filenames, properties and text that say it still find them.
Merging two authors (one organization written two ways) gives the documents, and the aliases, to
the one kept. Each move is returned, so undo can put the files back.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from caixa.documents import records
from caixa.documents.archive import Facts, place
from caixa.documents.reconcile import _move


def list_authors(master: Any) -> list[dict[str, Any]]:
    """Every author with its aliases and how many documents it has, by name."""
    db = master.connection
    found = []
    for row in db.execute("SELECT * FROM authors ORDER BY name COLLATE NOCASE"):
        aliases = [
            str(r[0])
            for r in db.execute(
                "SELECT alias FROM author_aliases WHERE author_id = ? AND alias != ? ORDER BY alias",
                (row["id"], row["name"]),
            )
        ]
        (count,) = db.execute(
            "SELECT COUNT(*) FROM documents WHERE author_id = ?", (row["id"],)
        ).fetchone()
        found.append(
            {
                "id": row["id"],
                "name": row["name"],
                "kind": row["kind"],
                "person_id": row["person_id"],
                "aliases": aliases,
                "documents": int(count),
            }
        )
    return found


def _refile(box: Any, master: Any, author_id: int) -> list[tuple[str, str]]:
    """File every document of an author again under the author's name as it is now."""
    db = master.connection
    (name,) = db.execute("SELECT name FROM authors WHERE id = ?", (author_id,)).fetchone()
    moves: list[tuple[str, str]] = []
    items = [
        r[0] for r in db.execute("SELECT item_id FROM documents WHERE author_id = ?", (author_id,))
    ]
    for item_id in items:
        record = replace(records.load_record(master, item_id), author=str(name))
        relative = place(
            box, record.original_filename, record.source_sha256,
            Facts(date=record.date, title=record.title, author=record.author),
            record.format, current=record.file_path,
        )  # fmt: skip
        if relative != record.file_path:
            _move(box, record.file_path, relative)
            moves.append((record.file_path, relative))
        records.save_document(master, replace(record, file_path=relative), None)
    return moves


def rename(box: Any, master: Any, author_id: int, name: str) -> list[tuple[str, str]]:
    """Rename an author (the old name stays an alias); returns the files moved. A name another
    author has is refused (merge them instead)."""
    name = " ".join(name.split())
    if not name:
        raise ValueError("An author needs a name.")
    taken = records.find_author(master, name)
    if taken is not None and taken != author_id:
        raise ValueError(f"'{name}' is another author already; merge the two instead.")
    db = master.connection
    row = db.execute("SELECT name FROM authors WHERE id = ?", (author_id,)).fetchone()
    if row is None:
        raise KeyError(author_id)
    records.add_author_alias(master, author_id, str(row[0]))
    db.execute("UPDATE authors SET name = ? WHERE id = ?", (name, author_id))
    records.add_author_alias(master, author_id, name)
    return _refile(box, master, author_id)


def merge(box: Any, master: Any, source_id: int, target_id: int) -> list[tuple[str, str]]:
    """Give every document and alias of `source_id` to `target_id`, which keeps its name;
    returns the files moved."""
    if source_id == target_id:
        raise ValueError("An author cannot be merged with itself.")
    db = master.connection
    for author in (source_id, target_id):
        if db.execute("SELECT 1 FROM authors WHERE id = ?", (author,)).fetchone() is None:
            raise KeyError(author)
    db.execute(
        "UPDATE author_aliases SET author_id = ? WHERE author_id = ?", (target_id, source_id)
    )
    db.execute("UPDATE documents SET author_id = ? WHERE author_id = ?", (target_id, source_id))
    db.execute("DELETE FROM authors WHERE id = ?", (source_id,))
    return _refile(box, master, target_id)


__all__ = ["list_authors", "merge", "rename"]
