"""The owner's preference file: `.caixa/owner.json`.

What the owner of a box decided about the people in it, kept apart from the imported data so that
it outlives a reset and applies again at the next import:

- `names`: who a number, an address or a name really is (what was linked, renamed or merged by
  hand). At import these come first, before Contacts and before the names a source gives;
- `categories`: the category each person was sorted into;
- `removed`: the people (`person`, by name) and identifiers (`identifier`, with the `service`
  it is on) taken out of the box. Their one-to-one conversations are not imported again.

Caixa writes the file whenever one of these changes. It is plain JSON and can be edited by hand
while Caixa is not running: names and categories added there are taken up at the next import, and
an entry deleted from `removed` lets that person be imported again. (A name or category that Caixa
already knows is dropped through Caixa, not by deleting it here.)

The file holds names, numbers and addresses of real people. It stays in the box's `.caixa` folder,
readable only by its owner. The box's settings are a different file, `box.yaml`, beside it.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from chattr.people import normalize_identifier

from caixa.box import Box
from caixa.master import ALIAS_KINDS, CATEGORIES, Master

NAME = "owner.json"
SCHEMA = 1


def path(box: Box) -> Path:
    return box.caixa_dir / NAME


def load(box: Box) -> dict[str, Any]:
    """The file's contents, with every section present; a missing or damaged file reads as empty
    (a damaged one is kept beside it as `owner.json.damaged`, never overwritten unread)."""
    empty: dict[str, Any] = {"schema": SCHEMA, "names": [], "categories": {}, "removed": []}
    file = path(box)
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return empty
    except (OSError, ValueError):
        try:
            os.replace(file, file.with_name(NAME + ".damaged"))
        except OSError:
            pass
        return empty
    if not isinstance(data, dict):
        return empty
    names = [
        n for n in data.get("names", [])
        if isinstance(n, dict) and n.get("identifier") and n.get("person")
    ]  # fmt: skip
    categories = {str(k): v for k, v in (data.get("categories") or {}).items() if v in CATEGORIES}
    removed = [
        r for r in data.get("removed", [])
        if isinstance(r, dict) and (r.get("identifier") or r.get("person"))
    ]  # fmt: skip
    return {"schema": SCHEMA, "names": names, "categories": categories, "removed": removed}


def _write(box: Box, data: dict[str, Any]) -> None:
    file = path(box)
    part = file.with_name(NAME + ".part")
    handle = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        json.dump(data, out, ensure_ascii=False, indent=2, sort_keys=True)
        out.write("\n")
    os.replace(part, file)


def apply(box: Box, master: Master) -> int:
    """Teach the master what the file says: its names (as names given by hand) and categories.
    Returns how many names were new to it. What the master already has is left as it is."""
    data = load(box)
    learned = 0
    known = {(a.kind, a.normalized, a.service or "") for a in master.aliases()}
    for entry in data["names"]:
        kind = entry.get("kind") if entry.get("kind") in ALIAS_KINDS else "name"
        person = master.person_id(str(entry["person"])) or master.add_person(str(entry["person"]))
        try:
            alias = master.add_alias(
                person, str(entry["identifier"]), kind, service=entry.get("service") or None
            )
        except ValueError:
            continue  # it already names someone else in this box: the box's word stands
        row = master.connection.execute(
            "SELECT kind, normalized, COALESCE(service, '') FROM aliases WHERE id = ?", (alias,)
        ).fetchone()
        master.connection.execute("UPDATE aliases SET source = 'human' WHERE id = ?", (alias,))
        if tuple(row) not in known:
            learned += 1
    for name, category in data["categories"].items():
        person = master.add_person(name)  # (the person, new or already there)
        if master.category(person) is None:
            master.set_category([person], category)
    master.commit()
    return learned


def save(box: Box, master: Master) -> None:
    """Write the file from what the master now holds: every name given by hand and every
    category. The removed list is kept as it is. (`apply` comes first, when the box is opened and
    at each import, so what was typed into the file is in the master by now.)"""
    data = load(box)
    people = {p.id: p for p in master.people()}
    data["names"] = sorted(
        (
            {"identifier": a.value, "kind": a.kind, "service": a.service,
             "person": people[a.person_id].name}
            for a in master.aliases()
            if a.source == "human" and a.person_id in people
        ),
        key=lambda n: (str(n["person"]).casefold(), str(n["identifier"])),
    )  # fmt: skip
    data["categories"] = dict(sorted(master.categories().items(), key=lambda i: i[0].casefold()))
    _write(box, data)


def forget_names(box: Box) -> None:
    """Drop the names and categories (the removed list stays)."""
    data = load(box)
    data["names"], data["categories"] = [], {}
    _write(box, data)


def add_removed(box: Box, entries: Iterable[dict[str, Any]]) -> int:
    """Record people (`person`) and identifiers (`identifier`, `service`) taken out of the box;
    returns how many were new."""
    data = load(box)

    def key_of(entry: dict[str, Any]) -> tuple[str, str]:
        if entry.get("identifier"):
            return (entry.get("service") or "", _key(str(entry["identifier"])))
        return ("\0person", str(entry["person"]).strip().casefold())

    have = {key_of(r) for r in data["removed"]}
    added = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for entry in entries:
        key = key_of(entry)
        if key in have or not key[1]:
            continue
        have.add(key)
        if entry.get("identifier"):
            kept = {"identifier": str(entry["identifier"]), "service": entry.get("service") or None}
        else:
            kept = {"person": str(entry["person"]).strip()}
        data["removed"].append({**kept, "removed_at": now})
        added += 1
    _write(box, data)
    return added


def _key(identifier: str, region: str = "US") -> str:
    return str(normalize_identifier(identifier, region))


def removed_matcher(
    removed: Iterable[dict[str, Any]], region: str = "US"
) -> Optional[Callable[[str, str, Optional[str]], bool]]:
    """`match(service, identifier, person)` for Chattr's `remove_people`: true for a handle on
    the removed list (an entry with no service, a number or an address, counts on every service)
    and for a handle of a person on it. None when the list is empty."""
    everywhere: set[str] = set()
    on_service: set[tuple[str, str]] = set()
    people: set[str] = set()
    for entry in removed:
        if not entry.get("identifier"):
            people.add(str(entry.get("person") or "").strip().casefold())
            continue
        key = _key(str(entry["identifier"]), region)
        if not key:
            continue
        if entry.get("service"):
            on_service.add((str(entry["service"]), key))
        else:
            everywhere.add(key)
    people.discard("")
    if not everywhere and not on_service and not people:
        return None

    def match(service: str, identifier: str, person: Optional[str]) -> bool:
        if person and person.strip().casefold() in people:
            return True
        key = _key(identifier, region)
        return key in everywhere or (service, key) in on_service

    return match
