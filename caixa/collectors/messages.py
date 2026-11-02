"""The messages adapter: Chattr's `chattr.sqlite` into the master database.

The handoff is an `ATTACH`: the master opens `chattr.sqlite` read-only and upserts items in SQL
terms, by the stable id Chattr gave each message. Nothing here imports Chattr, and nothing writes
to Chattr's database.

For each message:

- new id → insert an item and append an `insert` change-log row;
- same id with a different content hash or version → update the item (what a person decided, such
  as its privacy, is kept) and append an `update` row;
- unchanged → nothing is written, so syncing unchanged data adds no change-log rows.

People are linked by role: the *sender* (the handle's person; the owner for the owner's own
messages), *recipients* (the other side of a one-to-one chat, or a mail's To and Cc), and the
*participants* of a group. The aliases Chattr resolved become aliases in the master. When a link
set changes for an unchanged item (a handle was linked to a person later) a `link` row is appended
for exactly that item. Handles with no person yet are reported for a human to link.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Union

from caixa.master import Master

COLLECTOR = "chattr"
PathLike = Union[str, Path]
_PHONE_LIKE = re.compile(r"^\+?[\d\s().\-]{6,}$")


@dataclass
class UnresolvedHandle:
    service: str
    identifier: str
    display_name: Optional[str]
    messages: int


@dataclass
class SyncResult:
    import_id: int
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    linked: int = 0  # unchanged items whose people links changed
    people: int = 0  # people newly created
    aliases: int = 0  # aliases newly learned
    conflicts: list[str] = field(default_factory=list)  # aliases that already name someone else
    unresolved: list[UnresolvedHandle] = field(default_factory=list)


def _alias_kind(service: str, identifier: str) -> tuple[str, Optional[str]]:
    """(kind, service) for an identifier: phones and emails belong to everyone; names and usernames
    only to the service that uses them."""
    if "@" in identifier:
        return "email", None
    if _PHONE_LIKE.match(identifier) and len(re.sub(r"\D", "", identifier)) >= 7:
        return "phone", None
    return ("name" if " " in identifier.strip() else "username"), service


def sync_chattr(
    master: Master, chattr_db: PathLike, pages: Optional[Mapping[str, str]] = None
) -> SyncResult:
    """Bring the master up to date with `chattr_db`; `pages` maps an item id to the page showing it."""
    source = Path(chattr_db).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    db = master.connection
    import_id = master.start_import(COLLECTOR, source)
    master.commit()
    result = SyncResult(import_id)
    db.execute("ATTACH DATABASE ? AS chattr", (f"{source.as_uri()}?mode=ro",))
    try:
        db.execute("SAVEPOINT sync")
        try:
            _sync(master, db, result, pages or {})
            db.execute("RELEASE sync")
        except Exception as error:
            db.execute("ROLLBACK TO sync")
            db.execute("RELEASE sync")
            master.finish_import(import_id, status="failed", details=str(error))
            master.commit()
            raise
        master.finish_import(
            import_id,
            inserted=result.inserted,
            updated=result.updated,
            unchanged=result.unchanged,
            linked=result.linked,
        )
        master.commit()
    finally:
        db.execute("DETACH DATABASE chattr")
    return result


def _sync(
    master: Master, db: sqlite3.Connection, result: SyncResult, pages: Mapping[str, str]
) -> None:
    owner_pid = _learn_people(master, db, result)

    handle_person: dict[int, int] = {}
    handle_key: dict[tuple[str, str], int] = {}
    for row in db.execute("SELECT id, service, normalized, person FROM chattr.handles"):
        if row["person"]:
            pid = master.person_id(row["person"])
            if pid is not None:
                handle_person[row["id"]] = pid
                handle_key[(row["service"], row["normalized"])] = pid

    owner_handles = {
        r[0] for r in db.execute("SELECT handle_id FROM chattr.participants WHERE role = 'owner'")
    } | {
        r[0]
        for r in db.execute(
            "SELECT DISTINCT sender_handle_id FROM chattr.messages "
            "WHERE is_from_owner = 1 AND sender_handle_id IS NOT NULL"
        )
    }
    members: dict[str, set[int]] = defaultdict(set)  # conversation → people other than the owner
    for row in db.execute(
        "SELECT conversation_id, handle_id FROM chattr.participants UNION "
        "SELECT conversation_id, sender_handle_id FROM chattr.messages "
        "WHERE sender_handle_id IS NOT NULL"
    ):
        handle = row[1]
        if handle not in owner_handles and handle in handle_person:
            members[row[0]].add(handle_person[handle])
    groups = {r[0] for r in db.execute("SELECT id FROM chattr.conversations WHERE type = 'group'")}

    existing = {
        r["id"]: (r["content_hash"], r["version"], r["file_path"])
        for r in db.execute("SELECT id, content_hash, version, file_path FROM main.items")
    }
    current: dict[str, set[tuple[int, str]]] = defaultdict(set)
    for r in db.execute("SELECT item_id, person_id, role FROM main.item_people"):
        current[r["item_id"]].add((r["person_id"], r["role"]))

    def person_for_address(address: str) -> Optional[int]:
        return handle_key.get(("Mail", address.strip().lower())) or master.find_person(
            address, "Mail"
        )

    for row in db.execute(
        "SELECT m.*, c.service AS service FROM chattr.messages m "
        "JOIN chattr.conversations c ON c.id = m.conversation_id ORDER BY m.timestamp_utc, m.id"
    ):
        item_id = row["id"]
        sender: Optional[int] = None
        if row["sender_handle_id"]:
            sender = handle_person.get(row["sender_handle_id"])
        elif row["is_from_owner"]:
            sender = owner_pid
        links: set[tuple[int, str]] = set()
        if sender is not None:
            links.add((sender, "sender"))
        conversation_people = members.get(row["conversation_id"], set())
        if row["service"] == "Mail":
            headers = json.loads(row["mail_headers"]) if row["mail_headers"] else {}
            for field_name in ("to", "cc"):
                for person in headers.get(field_name, []):
                    pid = person_for_address(person.get("address", ""))
                    if pid is not None and pid != sender:
                        links.add((pid, "recipient"))
        elif row["conversation_id"] in groups:
            for pid in conversation_people | ({owner_pid} if owner_pid else set()):
                if pid != sender:
                    links.add((pid, "participant"))
        elif row["is_from_owner"]:
            links |= {(pid, "recipient") for pid in conversation_people}
        elif owner_pid is not None and sender != owner_pid:
            links.add((owner_pid, "recipient"))

        text = row["body"] if row["body"] is not None else row["transcript"]
        page = pages.get(item_id) or (existing[item_id][2] if item_id in existing else None)
        values = (
            row["content_type"], row["service"], row["conversation_id"], row["timestamp_utc"],
            row["tz_offset_minutes"], row["time_precision"], text, page, f"#m-{item_id}",
            row["content_hash"], row["version"], result.import_id,
        )  # fmt: skip
        known = existing.get(item_id)
        if known is None:
            db.execute(
                "INSERT INTO items (id, type, collector, service, conversation, timestamp_utc, "
                "tz_offset_minutes, time_precision, text, file_path, anchor, content_hash, version, "
                "first_import_id, last_import_id) VALUES (?, ?, 'chattr', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, *values[:-1], result.import_id, result.import_id),
            )
            master.log_change(item_id, "insert", row["version"], result.import_id)
            result.inserted += 1
            _set_links(db, item_id, links, set())
            continue
        if known[0] != row["content_hash"] or known[1] != row["version"]:
            db.execute(
                "UPDATE items SET type = ?, service = ?, conversation = ?, timestamp_utc = ?, "
                "tz_offset_minutes = ?, time_precision = ?, text = ?, file_path = ?, anchor = ?, "
                "content_hash = ?, version = ?, last_import_id = ? WHERE id = ?",
                (*values, item_id),
            )
            master.log_change(item_id, "update", row["version"], result.import_id)
            result.updated += 1
            _set_links(db, item_id, links, current[item_id])
            continue
        result.unchanged += 1
        if page != known[2]:
            db.execute(
                "UPDATE items SET file_path = ?, anchor = ? WHERE id = ?",
                (page, f"#m-{item_id}", item_id),
            )
        if links != current[item_id]:
            _set_links(db, item_id, links, current[item_id])
            master.log_change(item_id, "link", row["version"], result.import_id)
            result.linked += 1

    result.unresolved = [
        UnresolvedHandle(r["service"], r["identifier"], r["display_name"], r["messages"])
        for r in db.execute(
            "SELECT h.service, h.identifier, h.display_name, COUNT(m.id) AS messages "
            "FROM chattr.handles h LEFT JOIN chattr.messages m ON m.sender_handle_id = h.id "
            "WHERE h.person IS NULL GROUP BY h.id ORDER BY messages DESC, h.service, h.identifier"
        )
    ]


def _set_links(
    db: sqlite3.Connection, item_id: str, wanted: set[tuple[int, str]], have: set[tuple[int, str]]
) -> None:
    for person_id, role in have - wanted:
        db.execute(
            "DELETE FROM item_people WHERE item_id = ? AND person_id = ? AND role = ?",
            (item_id, person_id, role),
        )
    for person_id, role in wanted - have:
        db.execute(
            "INSERT INTO item_people (item_id, person_id, role) VALUES (?, ?, ?)",
            (item_id, person_id, role),
        )


def _learn_people(master: Master, db: sqlite3.Connection, result: SyncResult) -> Optional[int]:
    """Create the people Chattr resolved, learn their aliases, and find the owner."""
    before_people = len(master.people())
    owner_names = {
        r["person"]
        for r in db.execute(
            "SELECT DISTINCT h.person FROM chattr.handles h WHERE h.person IS NOT NULL AND h.id IN "
            "(SELECT handle_id FROM chattr.participants WHERE role = 'owner' UNION "
            "SELECT sender_handle_id FROM chattr.messages WHERE is_from_owner = 1)"
        )
    }
    if master.owner_id() is None and len(owner_names) == 1:
        master.add_person(next(iter(owner_names)), is_owner=True)
    before_aliases = len(master.aliases())
    for row in db.execute(
        "SELECT service, identifier, person FROM chattr.handles WHERE person IS NOT NULL ORDER BY id"
    ):
        pid = master.add_person(row["person"])
        kind, service = _alias_kind(row["service"], row["identifier"])
        try:
            master.add_alias(pid, row["identifier"], kind, service=service, source="chattr")
        except ValueError as error:
            result.conflicts.append(str(error))
    result.people = len(master.people()) - before_people
    result.aliases = len(master.aliases()) - before_aliases
    return master.owner_id()
