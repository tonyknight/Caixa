"""Tags: written by the model with each summary, made tidy by Caixa, and the owner's to change.

The model is shown the starter set (common tags such as `statement`, `bill`, `tax`) and asked to
use one when it fits. `normalize_tags` makes what it answers tidy: lower case, single spaces, a
starter tag recognised under capitals, accents or a plural, no duplicates, at most four. The owner
adds and removes tags (`change_tags`); a tag the owner removed is remembered, so reading the
document again does not bring it back. The starter set itself can grow and shrink
(`change_starter`).
"""

from __future__ import annotations

import unicodedata
from typing import Any, Iterable, Optional, Sequence

#: The most tags a document is given by the model.
MOST = 4


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def normalize_tags(
    given: Iterable[str], starters: Sequence[str] = (), most: int = MOST
) -> list[str]:
    """Tags made tidy (see the module text), in the order given."""
    plain_starters = {_plain(s): s for s in starters}
    kept: list[str] = []
    for tag in given:
        text = " ".join(str(tag or "").split()).casefold()
        if not text:
            continue
        plain = _plain(text)
        text = plain_starters.get(plain) or plain_starters.get(plain.removesuffix("s")) or text
        if text not in kept:
            kept.append(text)
    return kept[:most]


def starter_tags(master: Any) -> list[str]:
    return [
        str(r[0])
        for r in master.connection.execute("SELECT name FROM tags WHERE starter = 1 ORDER BY name")
    ]


def rejected_tags(master: Any, item_id: str) -> set[str]:
    """The tags the owner took off this document (the model does not put them back)."""
    return {
        str(r[0]).casefold()
        for r in master.connection.execute(
            "SELECT value FROM document_fields WHERE item_id = ? AND field = 'tag' "
            "AND source = 'user_verified' AND state = 'rejected'",
            (item_id,),
        )
    }


def change_tags(
    master: Any,
    item_id: str,
    add: Optional[Iterable[str]] = None,
    remove: Optional[Iterable[str]] = None,
) -> list[dict[str, str]]:
    """The owner adds tags (theirs from now on) and removes any; returns the document's tags."""
    from caixa.documents import records

    db = master.connection
    added = normalize_tags(add or [], starter_tags(master), most=50)
    removed = {" ".join(t.split()).casefold() for t in (remove or []) if t and t.strip()}
    for tag in removed:
        db.execute("DELETE FROM document_tags WHERE item_id = ? AND tag = ?", (item_id, tag))
        if tag not in rejected_tags(master, item_id):
            records.add_field(master, item_id, "tag", tag, "user_verified", state="rejected")
    for tag in added:
        db.execute(
            "DELETE FROM document_fields WHERE item_id = ? AND field = 'tag' AND value = ? "
            "AND source = 'user_verified' AND state = 'rejected'",
            (item_id, tag),
        )
        db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        db.execute(
            "INSERT OR REPLACE INTO document_tags (item_id, tag, source) VALUES (?, ?, 'user_verified')",
            (item_id, tag),
        )
    return [
        dict(r)
        for r in db.execute(
            "SELECT tag, source FROM document_tags WHERE item_id = ? ORDER BY tag", (item_id,)
        )
    ]


def change_starter(
    master: Any, add: Optional[Iterable[str]] = None, remove: Optional[Iterable[str]] = None
) -> list[str]:
    """Grow or shrink the starter set; returns it."""
    db = master.connection
    for tag in normalize_tags(add or [], most=50):
        db.execute(
            "INSERT INTO tags (name, starter) VALUES (?, 1) ON CONFLICT (name) DO UPDATE SET starter = 1",
            (tag,),
        )
    for tag in remove or []:
        db.execute(
            "UPDATE tags SET starter = 0 WHERE name = ?", (" ".join(tag.split()).casefold(),)
        )
    return starter_tags(master)


__all__ = [
    "MOST",
    "change_starter",
    "change_tags",
    "normalize_tags",
    "rejected_tags",
    "starter_tags",
]
