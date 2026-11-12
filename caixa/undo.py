"""Undo for imports: what the box was like before, kept so it can be put back.

Before an import, Caixa copies its databases and working files into `.caixa/undo/<job>/` and lists
the box's files. While that snapshot is the newest, every file the box moves (a person is named and
their files follow) is noted on it. Undoing an import:

1. puts back every file that was moved since, newest move first;
2. removes every file that is in the box now and was not in it then;
3. puts the databases and working files back as they were;

after which the pages are redrawn from the restored databases. Changes made to people since the
import go too (they live in the same databases); the snapshot counts them so a person can be told.

Only the newest snapshot can be undone, then the one before it, and so on. The last `KEEP` are kept.
Nothing here touches the export a person imported from, or the `Inbox` folder.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from caixa.box import INBOX, Box

KEEP = 3
#: Parts of `.caixa/work` that are scratch space, not state: never copied, never restored.
_SCRATCH = {"incoming", "imports", "temp", "Output"}
_SMALL = 5 * 1024 * 1024  # working files larger than this (other than databases) are not state


def _home(box: Box) -> Path:
    return box.caixa_dir / "undo"


def _snapshot(box: Box, job: int) -> Path:
    return _home(box) / f"{job:06d}"


def visible_files(box: Box) -> set[str]:
    """Every file a person can see in the box (not Caixa's own folder, not the Inbox)."""
    root = box.root
    found = set()
    for folder, names, files in os.walk(root):
        if Path(folder) == root:
            names[:] = [n for n in names if n not in (box.caixa_dir.name, INBOX)]
        for name in files:
            found.add((Path(folder) / name).relative_to(root).as_posix())
    return found


def _state_files(box: Box) -> list[str]:
    """Caixa's own state, relative to `.caixa`: the master database, the list of pages, and each
    collector's databases and settings."""
    caixa = box.caixa_dir
    found = [name for name in ("caixa.sqlite", "pages.json") if (caixa / name).is_file()]
    work = caixa / "work"
    for folder, names, files in os.walk(work):
        names[:] = [n for n in names if n not in _SCRATCH]
        for name in files:
            path = Path(folder) / name
            if name.endswith(("-wal", "-shm", ".part")):
                continue
            if name.endswith(".sqlite") or path.stat().st_size <= _SMALL:
                found.append(path.relative_to(caixa).as_posix())
    return sorted(found)


def _copy_database(source: Path, target: Path) -> None:
    """A consistent copy of a SQLite database, whatever is in its write-ahead log."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)) as old:
        with closing(sqlite3.connect(target)) as new:
            old.backup(new)


def _restore_database(saved: Path, live: Path) -> None:
    live.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(saved)) as old, closing(sqlite3.connect(live)) as new:
        old.backup(new)  # replaces the live database's contents in place, safely


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


# --- Taking a snapshot --------------------------------------------------------------------------


def begin(box: Box, job: int, collector: str, source: str) -> None:
    """Keep the box's state as it is now, before import `job` changes it."""
    folder = _snapshot(box, job)
    shutil.rmtree(folder, ignore_errors=True)
    (folder / "files").mkdir(parents=True)
    state = _state_files(box)
    for relative in state:
        source_file, target = box.caixa_dir / relative, folder / "files" / relative
        if relative.endswith(".sqlite"):
            _copy_database(source_file, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target)
    (folder / "before.txt").write_text("\n".join(sorted(visible_files(box))), encoding="utf-8")
    _write(
        folder / "meta.json",
        {
            "job": job,
            "collector": collector,
            "source": source,
            "taken": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "state": state,
            "moved": [],
            "people_changes": 0,
            "complete": False,
        },
    )
    for old in sorted(_home(box).iterdir())[:-KEEP]:
        shutil.rmtree(old, ignore_errors=True)


def finish(box: Box, job: int) -> None:
    """The import has ended (well or badly): from now on it can be undone."""
    meta = _snapshot(box, job) / "meta.json"
    data = _read(meta)
    if data:
        data["complete"] = True
        _write(meta, data)


def latest(box: Box) -> Optional[dict[str, Any]]:
    """The newest snapshot's record (the import that can be undone), or None."""
    home = _home(box)
    if not home.is_dir():
        return None
    for folder in sorted(home.iterdir(), reverse=True):
        data = _read(folder / "meta.json")
        if data.get("complete"):
            return data
    return None


def note_moves(box: Box, moved: Iterable[Iterable[str]]) -> None:
    """Files changed place (`from`, `to`, relative to the box): remember, so undo can put them back."""
    pairs = [list(pair) for pair in moved]
    data = latest(box)
    if not pairs or data is None:
        return
    data["moved"] = [*data.get("moved", []), *pairs]
    _write(_snapshot(box, int(data["job"])) / "meta.json", data)


def note_people_change(box: Box) -> None:
    """Someone was named, renamed or merged: undoing the newest import would undo that too."""
    data = latest(box)
    if data is not None:
        data["people_changes"] = int(data.get("people_changes", 0)) + 1
        _write(_snapshot(box, int(data["job"])) / "meta.json", data)


# --- Putting it back ----------------------------------------------------------------------------


def _tidy(folder: Path, stop: Path) -> None:
    while folder != stop and folder.is_relative_to(stop) and folder.is_dir():
        try:
            folder.rmdir()
        except OSError:
            return
        folder = folder.parent


def restore(box: Box, job: int) -> dict[str, int]:
    """Put the box back as it was before import `job`. Returns what was done, in numbers."""
    folder = _snapshot(box, job)
    data = _read(folder / "meta.json")
    if not data:
        raise FileNotFoundError(f"There is no snapshot for import {job}.")
    root = box.root.resolve()

    def inside(relative: str) -> Optional[Path]:
        path = (root / relative).resolve()
        hidden = path.is_relative_to(box.caixa_dir.resolve())
        return path if path.is_relative_to(root) and not hidden else None

    back = 0
    for origin, place in reversed(data.get("moved", [])):
        here, there = inside(place), inside(origin)
        if here and there and here.is_file() and not there.exists():
            there.parent.mkdir(parents=True, exist_ok=True)
            os.replace(here, there)
            _tidy(here.parent, root)
            back += 1

    before = set((folder / "before.txt").read_text(encoding="utf-8").splitlines())
    removed = 0
    for relative in sorted(visible_files(box) - before):
        path = inside(relative)
        if path and path.is_file():
            path.unlink()
            _tidy(path.parent, root)
            removed += 1

    kept = set(data.get("state", []))
    for relative in _state_files(box):
        if relative not in kept:  # made by the import: it was not there before
            live = box.caixa_dir / relative
            live.unlink(missing_ok=True)
            for extra in ("-wal", "-shm"):
                live.with_name(live.name + extra).unlink(missing_ok=True)
    for relative in kept:
        saved, live = folder / "files" / relative, box.caixa_dir / relative
        if not saved.is_file():
            continue
        if relative.endswith(".sqlite"):
            _restore_database(saved, live)
        else:
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, live)
    for name in ("People", "Groups", "Mail"):  # the folders a box always has
        (root / name).mkdir(exist_ok=True)
    shutil.rmtree(folder, ignore_errors=True)
    return {"files_removed": removed, "files_put_back": back}
