"""Starting a box again: take out everything that was imported, keep how the box is set up.

A box being tried out is rebuilt many times. Resetting it removes:

- the pages and the files Caixa filed (photos, recordings, mail attachments) above `.caixa/`, and
  the box's `index.html`;
- what Caixa knows about them: the master database's items and people, each collector's working
  data, the undo snapshots, the list of imports and their logs.

It keeps:

- the box itself: its name, its folder, its `README.md`, its `Inbox/` and anything in it;
- its settings (`box.yaml`): contacts, translation, speech-to-text, privacy;
- the owner, so the box is still for the same person;
- unless asked not to, the names given by hand (a number linked to a person, a rename, a merge):
  they apply again on the next import.

Only files Caixa wrote are deleted: a file someone put in a person's folder stays, and is reported.
Nothing here touches the exports a person imported from, or Caixa's own per-user folder (where the
translation key is).
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chattr.filing import playable_copy

from caixa.box import Box

#: The folders Caixa writes into above `.caixa/`.
WRITTEN = ("People", "Groups", "Mail")
#: Inside `.caixa/`: what goes with the data (the settings file, box.yaml, is not among them).
STATE = ("work", "undo", "logs", "pages.json", "jobs.sqlite", "caixa.sqlite")


@dataclass
class Reset:
    removed: int = 0  # files deleted above .caixa/
    left: list[str] = field(default_factory=list)  # files above .caixa/ Caixa did not write
    names_kept: int = 0  # names given by hand that were kept


def _written_files(box: Box) -> set[Path]:
    """Every file above `.caixa/` that Caixa wrote: its pages and the attachments it filed."""
    root = box.root.resolve()
    found: set[Path] = set()
    try:
        pages = json.loads((box.caixa_dir / "pages.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pages = []
    for relative in pages if isinstance(pages, list) else []:
        if isinstance(relative, str):
            found.add((root / relative).resolve())
    database = box.caixa_dir / "work" / "chattr" / "Database" / "chattr.sqlite"
    if database.is_file():
        with closing(sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)) as db:
            try:
                rows = db.execute("SELECT DISTINCT storage_path FROM attachments").fetchall()
            except sqlite3.Error:
                rows = []
        for (relative,) in rows:
            if relative:
                file = (root / relative).resolve()
                found.add(file)
                copy = playable_copy(file)  # a copy an older version made beside it
                if copy is not None:
                    found.add(copy)
    found.add((root / "index.html").resolve())
    return {
        f for f in found if f.is_relative_to(root) and ".caixa" not in f.relative_to(root).parts
    }


def _hand_names(box: Box) -> tuple[str | None, list[dict[str, Any]]]:
    """The owner's name, and every name given by hand (each with the person it names)."""
    if not box.master_path.exists():
        return None, []
    with box.master() as master:
        people = {p.id: p for p in master.people()}
        owner = next((p.name for p in people.values() if p.is_owner), None)
        names = [
            {"person": people[a.person_id].name, "value": a.value, "kind": a.kind,
             "service": a.service}
            for a in master.aliases()
            if a.source == "human" and a.person_id in people
        ]  # fmt: skip
    return owner, names


def reset_box(box: Box, forget_names: bool = False) -> Reset:
    """Take out everything imported into `box`; see the module text."""
    result = Reset()
    root = box.root.resolve()
    for file in sorted(_written_files(box)):
        if file.is_file() or file.is_symlink():
            file.unlink()
            result.removed += 1
    for name in WRITTEN:
        folder = root / name
        if not folder.is_dir():
            continue
        for left in sorted(p for p in folder.rglob("*") if p.is_file()):
            result.left.append(left.relative_to(root).as_posix())
        for inner in sorted((p for p in folder.rglob("*") if p.is_dir()), reverse=True):
            if not any(inner.iterdir()):
                inner.rmdir()

    owner, names = _hand_names(box)
    for part in STATE:
        state = box.caixa_dir / part
        if state.is_dir():
            shutil.rmtree(state)
        elif state.exists():
            state.unlink()
        for extra in (box.caixa_dir / f"{part}-wal", box.caixa_dir / f"{part}-shm"):
            extra.unlink(missing_ok=True)
    for sub in ("work", "logs"):
        (box.caixa_dir / sub).mkdir(parents=True, exist_ok=True)
    for folder_name in WRITTEN:
        (root / folder_name).mkdir(exist_ok=True)

    with box.master() as master:
        if owner:
            master.add_person(owner, is_owner=True)
        if not forget_names:
            for alias in names:
                person = master.person_id(alias["person"]) or master.add_person(alias["person"])
                master.add_alias(person, alias["value"], alias["kind"], service=alias["service"])
                result.names_kept += 1
        master.commit()
    return result
