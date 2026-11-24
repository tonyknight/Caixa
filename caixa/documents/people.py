"""Documents and the box's people: who wrote a document, and who it names.

A name matches a person of the box by their name or one of their `name` aliases, compared with
case, spacing and accents aside (`match`); a name that would match two people matches neither.

`link_documents` records, in `item_people`, every document's author that is a person of the box
as `sender`, and every person the model found named in it (its `person` fields) as `mentioned`.
The owner is never linked: every document in the box is theirs. Only those two roles of a
document are kept up to date here; any other is left as it is. It runs before the document pages
are drawn, so an import, a reading, a correction or a renamed author keeps the links current; when
they change and the box has person pages, a change waits for **Update the pages**.

`person_links` is what Chattr's person pages show of documents (its generic `page_links` slot):
each linked person's documents, newest first, each with **Open**.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from typing import Any, Optional

from caixa.box import Box
from caixa.master import Master

#: The roles a document's people are linked by (see the module text).
ROLES = ("sender", "mentioned")


def _fold(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name or "")
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(bare.casefold().split())


def _names(master: Master) -> dict[str, Optional[int]]:
    """Every name a person of the box is known by, folded, to their id (None when two share it)."""
    found: dict[str, Optional[int]] = {}

    def add(name: str, person: int) -> None:
        key = _fold(name)
        if not key:
            return
        found[key] = person if found.get(key, person) == person else None

    db = master.connection
    for person, name in db.execute("SELECT id, name FROM people"):
        add(str(name), int(person))
    for person, value in db.execute("SELECT person_id, value FROM aliases WHERE kind = 'name'"):
        add(str(value), int(person))
    return found


def match(master: Master, name: str) -> Optional[int]:
    """The person of the box this name is, or None (see the module text)."""
    return _names(master).get(_fold(name))


def _wanted(master: Master) -> dict[str, set[tuple[int, str]]]:
    names = _names(master)
    owner = master.owner_id()
    db = master.connection
    wanted: dict[str, set[tuple[int, str]]] = {
        str(item): set() for (item,) in db.execute("SELECT item_id FROM documents")
    }
    for item, author in db.execute(
        "SELECT d.item_id, a.name FROM documents d JOIN authors a ON a.id = d.author_id"
    ):
        person = names.get(_fold(str(author)))
        if person is not None and person != owner:
            wanted[str(item)].add((person, "sender"))
    for item, value in db.execute(
        "SELECT DISTINCT item_id, value FROM document_fields "
        "WHERE field = 'person' AND state != 'rejected' AND value IS NOT NULL"
    ):
        person = names.get(_fold(str(value)))
        if person is None or person == owner or str(item) not in wanted:
            continue
        if (person, "sender") not in wanted[str(item)]:
            wanted[str(item)].add((person, "mentioned"))
    return wanted


def _has_person_pages(box: Box) -> bool:
    return (box.work_dir("chattr") / "Database" / "chattr.sqlite").is_file()


def link_documents(box: Box) -> set[int]:
    """Bring every document's `sender` and `mentioned` links up to date (see the module text);
    returns the people whose links changed."""
    changed: set[int] = set()
    with box.master() as master:
        db = master.connection
        have: dict[str, set[tuple[int, str]]] = defaultdict(set)
        for item, person, role in db.execute(
            "SELECT ip.item_id, ip.person_id, ip.role FROM item_people ip "
            "JOIN documents d ON d.item_id = ip.item_id WHERE ip.role IN (?, ?)",
            ROLES,
        ):
            have[str(item)].add((int(person), str(role)))
        for item, links in _wanted(master).items():
            for person, role in have.get(item, set()) - links:
                db.execute(
                    "DELETE FROM item_people WHERE item_id = ? AND person_id = ? AND role = ?",
                    (item, person, role),
                )
                changed.add(person)
            for person, role in links - have.get(item, set()):
                db.execute(
                    "INSERT OR IGNORE INTO item_people (item_id, person_id, role) VALUES (?, ?, ?)",
                    (item, person, role),
                )
                changed.add(person)
    if changed and _has_person_pages(box):
        box.add_pending("pages")
    return changed


def person_links(box: Box) -> dict[str, list[dict[str, Any]]]:
    """For Chattr's person pages: `{person's name: [{group: "Documents", links: [{label, href,
    note}]}]}`, hrefs relative to the box, newest first."""
    if not box.master_path.exists():
        return {}
    with box.master(read_only=True) as master:
        try:
            rows = master.connection.execute(
                "SELECT p.name, ip.role, d.title, d.date, d.original_filename, i.file_path "
                "FROM item_people ip JOIN people p ON p.id = ip.person_id "
                "JOIN documents d ON d.item_id = ip.item_id JOIN items i ON i.id = d.item_id "
                "WHERE ip.role IN (?, ?) AND p.is_owner = 0 "
                "ORDER BY p.name, d.date IS NULL, d.date DESC, d.title",
                ROLES,
            ).fetchall()
        except Exception:  # an older database, before documents
            return {}
    found: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for name, role, title, date, original, path in rows:
        label = " ".join(filter(None, [f"({date})" if date else "", title or original]))
        note = "by them" if role == "sender" else "names them"
        found[str(name)].append({"label": label, "href": str(path), "note": note})
    return {name: [{"group": "Documents", "links": links}] for name, links in found.items()}


__all__ = ["ROLES", "link_documents", "match", "person_links"]
