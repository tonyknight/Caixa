"""Sorting an mbox's senders: who is known, who is to sort, and what a choice brings.

Everything here works from the index and plain sets (the owner's addresses, the box's people, the
owner's decisions), so it is tested without a box; the service fills those from the box.

- **Who is listed:** every sender of the source except the owner, and every address the owner wrote
  to that never wrote back (no mails of its own): a person the owner wrote to must be reachable by a
  choice, so the owner's unanswered mail can reach their page.
- **Known:** an address that is an alias of a person in the box (known by address, chosen to begin
  with), or a sender who used a box person's name (known by name: shown as such, and chosen only
  when the owner says so, since names collide more often than addresses).
- **Decisions:** what the owner chose or ignored. Ignoring wins over choosing; an explicit choice is
  needed for anyone not known by address.
- **What a choice brings:** every thread a chosen sender wrote in, whole, and every thread in which
  the owner wrote to a chosen address, even unanswered; in a mailing-list thread, only the mails of
  the owner, of the box's people and of the chosen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from caixa.mail.index import MailIndex

#: The Sort mail window's categories, in its order.
KEYS = ("known", "to_sort", "to_import", "ignored", "imported")
LABELS = {
    "known": "Known",
    "to_sort": "To sort",
    "to_import": "To import",
    "ignored": "Ignored",
    "imported": "Imported",
}
#: Headers that make a thread a mailing list's.
LIST_SIGNALS = ("list-id", "list-post")


@dataclass(frozen=True)
class Row:
    name: str
    address: str
    mails: int
    size: int
    known_by: Optional[str]  # "address", "name" or None
    person: Optional[str]  # the box person they are (or may be), by name
    owner_wrote: int  # how many of the owner's mails were addressed to them
    chosen: bool


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    senders: int
    mails: int
    size: int
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class Selection:
    """What importing the chosen senders would bring: the mails (by position) of each thread."""

    threads: dict[str, list[int]]
    mails: int
    size: int


def _owner_wrote(index: "MailIndex", owner: set[str]) -> dict[str, int]:
    """How many of the owner's mails (in every source) were addressed to each address."""
    wrote: dict[str, int] = {}
    if not owner:
        return wrote
    marks = ", ".join("?" for _ in owner)
    for (recipients,) in index.connection.execute(
        f"SELECT recipients FROM mails WHERE sender_address IN ({marks})", tuple(owner)
    ):
        for _, _, address in json.loads(recipients):
            wrote[address] = wrote.get(address, 0) + 1
    return wrote


def listing(
    index: "MailIndex",
    source_id: int,
    owner: set[str],
    known: dict[str, str],
    names: dict[str, str],
    chosen: set[str],
    ignored: set[str],
    imported: set[str],
) -> list[Category]:
    """The source's senders in the Sort mail window's categories."""
    owner = {a.lower() for a in owner}
    wrote = _owner_wrote(index, owner)
    people: dict[str, tuple[str, int, int]] = {}  # address → (name, mails, size)
    for address, names_json, mails, size in index.connection.execute(
        "SELECT address, names, mails, size FROM senders WHERE source_id = ?", (source_id,)
    ):
        used = json.loads(names_json)
        people[address] = (used[0] if used else "", int(mails), int(size))
    # The owner's correspondents who never wrote back, with the name the owner's mail gave them.
    marks = ", ".join("?" for _ in owner) or "NULL"
    for (recipients,) in index.connection.execute(
        f"SELECT recipients FROM mails WHERE source_id = ? AND sender_address IN ({marks})",
        (source_id, *owner),
    ):
        for _, name, address in json.loads(recipients):
            if address not in people:
                people[address] = (name, 0, 0)
            elif not people[address][0] and name:
                people[address] = (name, *people[address][1:])
    rows: dict[str, list[Row]] = {key: [] for key in KEYS}
    for address, (name, mails, size) in people.items():
        if address in owner:
            continue
        if address in known:
            by: Optional[str] = "address"
            person: Optional[str] = known[address]
        elif name and name.strip().casefold() in names:
            by, person = "name", names[name.strip().casefold()]
        else:
            by, person = None, None
        is_chosen = address not in ignored and (address in chosen or by == "address")
        row = Row(
            name or address, address, mails, size, by, person, wrote.get(address, 0), is_chosen
        )
        if address in imported:
            rows["imported"].append(row)
        elif address in ignored:
            rows["ignored"].append(row)
        else:
            if by:
                rows["known"].append(row)
            if is_chosen:
                rows["to_import"].append(row)
            if not by and not is_chosen:
                rows["to_sort"].append(row)
    found = []
    for key in KEYS:
        if key == "to_sort":
            ordered = sorted(
                rows[key], key=lambda r: (-r.owner_wrote, -r.mails, r.name.casefold(), r.address)
            )
        else:
            ordered = sorted(rows[key], key=lambda r: (-r.mails, r.name.casefold(), r.address))
        found.append(
            Category(
                key,
                LABELS[key],
                len(ordered),
                sum(r.mails for r in ordered),
                sum(r.size for r in ordered),
                tuple(ordered),
            )
        )
    return found


def selection(
    index: "MailIndex", source_id: int, chosen: set[str], owner: set[str], people: set[str]
) -> Selection:
    """The threads (and their mails, by position) that importing the chosen senders brings."""
    chosen = {a.lower() for a in chosen}
    owner = {a.lower() for a in owner}
    allowed = owner | {a.lower() for a in people} | chosen
    threads: dict[str, list[tuple[int, Optional[str], int, bool]]] = {}
    wanted: set[str] = set()
    for key, position, sender, recipients, signals, length in index.connection.execute(
        "SELECT thread_key, position, sender_address, recipients, signals, length FROM mails "
        "WHERE source_id = ? ORDER BY thread_key, position",
        (source_id,),
    ):
        listed = any(s in json.loads(signals) for s in LIST_SIGNALS)
        threads.setdefault(key, []).append((int(position), sender, int(length), listed))
        if sender in chosen or (
            sender in owner and any(a in chosen for _, _, a in json.loads(recipients))
        ):
            wanted.add(key)
    picked: dict[str, list[int]] = {}
    count = size = 0
    for key in sorted(wanted):
        mails = threads[key]
        if any(listed for *_, listed in mails):  # a mailing list's thread
            mails = [m for m in mails if m[1] in allowed]
        if mails:
            picked[key] = [m[0] for m in mails]
            count += len(mails)
            size += sum(m[2] for m in mails)
    return Selection(picked, count, size)
