"""Writing a Cleaned or Reduced mbox: the chosen mails copied byte for byte, checked, then named.

The original export is never changed: a new mbox is written in the source's own folder, named
`(YYYY-MM-DD) <name> [Cleaned].mbox` or `… [Reduced].mbox`. Its mails are copied from the source in
their original order, byte for byte (so each one is exactly what the export held), into a `.part`
file that is renamed to its final name only after every mail in it has been checked against the
index. A failed check, a cancel or an error leave nothing behind.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Optional

from caixa.mail.index import MailError

TAGS = ("Cleaned", "Reduced")
_DATE = re.compile(r"^\(\d{4}-\d{2}-\d{2}\) ")
_TAG = re.compile(r" \[(?:Cleaned|Reduced)\](?: \(\d+\))?$")
MB = 1 << 20


def _apple(path: PurePosixPath) -> bool:
    """Apple Mail exports a mailbox as a folder `<name>.mbox` holding a file named `mbox`."""
    return path.name == "mbox" and path.parent.suffix.lower() == ".mbox"


def output_name(source: str, tag: str, today: date) -> str:
    """`(today) <base> [<tag>].mbox`: the base is the source's name without `.mbox` and without the
    date and tag of an earlier Cleaned or Reduced copy."""
    if tag not in TAGS:
        raise ValueError(f"tag must be one of {TAGS}")
    path = PurePosixPath(source.replace("\\", "/"))
    name = path.parent.name if _apple(path) else path.name
    base = name[:-5] if name.lower().endswith(".mbox") else name
    base = _TAG.sub("", _DATE.sub("", base)).strip() or "mail"
    return f"({today.isoformat()}) {base} [{tag}].mbox"


def output_path(file: Path, member: str, tag: str, today: date) -> Path:
    """Where the new mbox goes: the source's folder (a zip's folder; the folder holding an Apple
    Mail `<name>.mbox`), under a name no file has yet."""
    if member:
        folder, named = file.parent, member
    elif _apple(PurePosixPath(file.as_posix())):
        folder, named = file.parent.parent, file.as_posix()
    else:
        folder, named = file.parent, file.name
    stem = output_name(named, tag, today)[: -len(".mbox")]
    chosen, number = folder / f"{stem}.mbox", 2
    while chosen.exists() or chosen.with_name(chosen.name + ".part").exists():
        chosen, number = folder / f"{stem} ({number}).mbox", number + 1
    return chosen


def human_size(count: int) -> str:
    """1536 → '1.5 KB'."""
    value = float(count)
    for unit in ("bytes", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:,.0f} {unit}" if unit == "bytes" else f"{value:,.1f} {unit}"
        value /= 1024
    return f"{value:,.1f} TB"


def preflight(folder: Path, needed: int, margin: Optional[int] = None) -> None:
    """Refuse, before any work, a folder that cannot be written or has too little room."""
    if not os.access(folder, os.W_OK):
        raise MailError(
            f"{folder} cannot be written, so the new mbox cannot be put beside its source."
        )
    spare = margin if margin is not None else max(64 * MB, needed // 100)
    free = shutil.disk_usage(folder).free
    if free < needed + spare:
        raise MailError(
            f"There is not enough room in {folder}: the new mbox needs about {human_size(needed + spare)} "
            f"and {human_size(free)} is free."
        )
