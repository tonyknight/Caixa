"""Where a document is filed in the box, and how its file gets there.

    Documents/<FORMAT>/<YYYY>/<Author>/(DATE) Title - Author.<ext>
    Documents/<FORMAT>/Unrecognized/<original name>

A document whose date, author and title are known is filed by year and author under its archival
name (`caixa.naming`); any other waits in `Unrecognized/`, at the root of its format's folder,
under its own name made safe. A different file with the same name gets ` (2)`; the same file is
recognised by its SHA-256. Files are copied through a `.part` file that is checked against the
hash before it takes its name, so a box never holds half a document.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from caixa.box import Box
from caixa.naming import (
    NamingDate,
    NamingError,
    archival_name,
    folder_name,
    free_path,
    original_name,
)

DOCUMENTS = "Documents"
UNRECOGNIZED = "Unrecognized"
#: The folder of each format inside `Documents/`.
FORMAT_FOLDERS = {"pdf": "PDF"}


@dataclass(frozen=True)
class Facts:
    """What naming and filing a document needs: its naming date, title and author."""

    date: Optional[str] = None  # YYYY, YYYY-MM or YYYY-MM-DD
    title: Optional[str] = None
    author: Optional[str] = None

    @property
    def complete(self) -> bool:
        return bool(self.date and self.title and self.author)


def format_folder(box: Box, format: str = "pdf") -> Path:
    return box.root / DOCUMENTS / FORMAT_FOLDERS[format]


def _target(
    source_name: str,
    sha256: str,
    facts: Optional[Facts],
    format: str,
    filename: Optional[str] = None,
) -> Path:
    """The folder and name a document should have, relative to its format's folder. With
    `filename` (an organized name, D30), that is its name, in its year and author's folder or in
    Unrecognized."""
    if filename:
        if facts is not None and facts.complete:
            return Path(str(facts.date)[:4]) / folder_name(str(facts.author)) / filename
        return Path(UNRECOGNIZED) / filename
    extension = Path(source_name).suffix or f".{format}"
    if facts is not None and facts.complete:
        try:
            date = NamingDate.parse(str(facts.date))
            name = archival_name(date, str(facts.title), facts.author, extension)
            return Path(str(date.year)) / folder_name(str(facts.author)) / name
        except NamingError:
            pass  # filed as unrecognized, under its own name
    try:
        name = original_name(source_name)
    except NamingError:
        name = f"{sha256[:12]}{extension.lower()}"  # no usable name of its own: its content's
    return Path(UNRECOGNIZED) / name


def place(
    box: Box,
    source_name: str,
    sha256: str,
    facts: Optional[Facts],
    format: str = "pdf",
    current: Optional[str] = None,
    filename: Optional[str] = None,
) -> str:
    """The box-relative path a document is filed at: by year and author when `facts` are
    complete, else in `Unrecognized/`. `current` is where it is now (it keeps that path when it
    would get the same name). `filename` keeps an organized name (see `_target`)."""
    base = format_folder(box, format)
    wanted = base / _target(source_name, sha256, facts, format, filename)
    if current is not None and (box.root / current) == wanted:
        return current
    return free_path(wanted.parent, wanted.name, sha256).relative_to(box.root).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_into(box: Box, source: Path, relative: str, sha256: str) -> None:
    """Copy `source` to `relative` in the box, byte for byte: through a `.part` file that must
    hold `sha256` before it is renamed. The source is only read."""
    target = box.root / relative
    if target.is_file() and _sha256(target) == sha256:
        return  # already there
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    try:
        shutil.copyfile(source, part)
        if _sha256(part) != sha256:
            raise OSError(f"The copy of {source.name} does not match it; nothing was filed.")
        os.replace(part, target)
    finally:
        part.unlink(missing_ok=True)


__all__ = ["DOCUMENTS", "Facts", "UNRECOGNIZED", "copy_into", "format_folder", "place"]
