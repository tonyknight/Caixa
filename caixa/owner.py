"""The owner's preference file: `.caixa/owner.json`.

What the owner of a box decided about the people in it, kept apart from the imported data so that
it outlives a reset and applies again at the next import:

- `names`: who a number, an address or a name really is (what was linked, renamed or merged by
  hand). At import these come first, before Contacts and before the names a source gives;
- `categories`: the category each person was sorted into;
- `subcategories`: the subcategories made under the categories (each with its `category` and its
  `path` of names from the top, two at most), and `placed`: the path of the subcategory each person
  is in, within their category;
- `removed`: the people (`person`, by name) and identifiers (`identifier`, with the `service`
  it is on) taken out of the box. Their one-to-one conversations are not imported again;
- `mail`: what the owner decided about mail: the senders `kept` when cleaning (their mail is never
  left out of a Cleaned mbox), the senders `chosen` and `ignored` when sorting, and the `accounts`
  with the owner's addresses in each (`{"Gmail": {"owner": [...]}}`).

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
from caixa.master import ALIAS_KINDS, CATEGORIES, SORTED, Master

NAME = "owner.json"
SCHEMA = 1


def path(box: Box) -> Path:
    return box.caixa_dir / NAME


def load(box: Box) -> dict[str, Any]:
    """The file's contents, with every section present; a missing or damaged file reads as empty
    (a damaged one is kept beside it as `owner.json.damaged`, never overwritten unread)."""
    empty: dict[str, Any] = {
        "schema": SCHEMA,
        "names": [],
        "categories": {},
        "subcategories": [],
        "placed": {},
        "removed": [],
        "mail": _mail({}),
    }
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
    mail = _mail(data.get("mail"))
    subcategories = [
        {"category": s["category"], "path": [str(n) for n in s["path"]][:2]}
        for s in data.get("subcategories", [])
        if isinstance(s, dict) and s.get("category") in SORTED
        and isinstance(s.get("path"), list) and s["path"]
    ]  # fmt: skip
    placed = {
        str(k): [str(n) for n in v][:2]
        for k, v in (data.get("placed") or {}).items()
        if isinstance(v, list) and v
    }
    return {
        "schema": SCHEMA,
        "names": names,
        "categories": categories,
        "subcategories": subcategories,
        "placed": placed,
        "removed": removed,
        "mail": mail,
    }


def _mail(section: Any) -> dict[str, Any]:
    """The mail section: senders kept in cleaning and ignored in sorting (addresses, lower case),
    and the accounts with the owner's addresses in each."""
    given = section if isinstance(section, dict) else {}

    def addresses(name: str) -> list[str]:
        values = given.get(name)
        found = values if isinstance(values, list) else []
        return sorted({str(a).strip().lower() for a in found if str(a).strip()})

    accounts = given.get("accounts")
    return {
        "kept": addresses("kept"),
        "chosen": addresses("chosen"),
        "ignored": addresses("ignored"),
        "accounts": accounts if isinstance(accounts, dict) else {},
    }


def set_mail_decision(box: Box, addresses: Iterable[str], kind: str, on: bool = True) -> None:
    """Choose senders to import (`chosen`) or ignore them (`ignored`); a sender is never both, so
    deciding one takes them off the other. `on=False` forgets the decision."""
    if kind not in ("chosen", "ignored"):
        raise ValueError("kind must be 'chosen' or 'ignored'")
    other = "ignored" if kind == "chosen" else "chosen"
    data = load(box)
    given = {a.strip().lower() for a in addresses if a.strip()}
    mine, theirs = set(data["mail"][kind]), set(data["mail"][other])
    if on:
        mine |= given
        theirs -= given
    else:
        mine -= given
    data["mail"][kind], data["mail"][other] = sorted(mine), sorted(theirs)
    _write(box, data)


def mail_owner(box: Box, account: str) -> list[str]:
    """The owner's addresses the owner confirmed for an account (empty when not confirmed yet)."""
    entry = load(box)["mail"]["accounts"].get(account)
    found = entry.get("owner") if isinstance(entry, dict) else None
    return sorted({str(a).lower() for a in found}) if isinstance(found, list) else []


def set_mail_owner(box: Box, account: str, addresses: Iterable[str]) -> list[str]:
    """Confirm the owner's addresses for an account."""
    data = load(box)
    chosen = sorted({a.strip().lower() for a in addresses if a.strip()})
    entry = data["mail"]["accounts"].get(account)
    data["mail"]["accounts"][account] = {
        **(entry if isinstance(entry, dict) else {}),
        "owner": chosen,
    }
    _write(box, data)
    return chosen


def mail_kept(box: Box) -> list[str]:
    """The senders the owner kept when cleaning mail (their mail is never left out)."""
    return list(load(box)["mail"]["kept"])


def set_mail_kept(box: Box, addresses: Iterable[str], keep: bool = True) -> list[str]:
    """Keep these senders (or stop keeping them); returns the kept senders."""
    data = load(box)
    chosen = {a.strip().lower() for a in addresses if a.strip()}
    kept = set(data["mail"]["kept"])
    kept = kept | chosen if keep else kept - chosen
    data["mail"]["kept"] = sorted(kept)
    _write(box, data)
    return list(data["mail"]["kept"])


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
    for entry in data["subcategories"]:
        try:
            master.ensure_subcategory(entry["category"], entry["path"])
        except ValueError:
            continue  # (a path the file got wrong is left out)
    for name, category in data["categories"].items():
        person = master.add_person(name)  # (the person, new or already there)
        if master.category(person) is None:
            path = data["placed"].get(name)
            sub = None
            if path and category in SORTED:
                try:
                    sub = master.ensure_subcategory(category, path)
                except ValueError:
                    sub = None
            master.set_category([person], category, sub)
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
    tree = master.subcategories()
    data["subcategories"] = [
        {"category": category, "path": path}
        for category, path in (master.subcategory_path(s["id"]) for s in tree)
    ]
    data["placed"] = {
        p.name: master.subcategory_path(sub)[1]
        for p in sorted(master.people(), key=lambda p: p.name.casefold())
        if (sub := master.subcategory(p.id)) is not None
    }
    _write(box, data)


def forget_names(box: Box) -> None:
    """Drop the names and categories (the removed list stays)."""
    data = load(box)
    data["names"], data["categories"], data["placed"] = [], {}, {}
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
