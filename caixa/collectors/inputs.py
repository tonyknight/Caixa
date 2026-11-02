"""Turning what a person points at (a file, a folder or a zip) into the inputs a collector reads.

A zip is unpacked into a working folder first, safely: a member whose path would land outside that
folder is refused. A folder is searched for what the collector reads (every WhatsApp `_chat.txt`,
every Meta thread, …). A plain file is used as it is.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Callable


class InputError(Exception):
    """The source can't be used (not found, nothing in it, an unsafe zip)."""


def unpack(archive: Path, workdir: Path) -> Path:
    """Extract a zip into `workdir/<name>-<hash>/` (once); returns that folder."""
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()[:10]
    target = workdir / f"{archive.stem}-{digest}"
    marker = target / ".unpacked"
    if marker.exists():
        return target
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    try:
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                destination = (target / member.filename).resolve()
                if not destination.is_relative_to(root):
                    raise InputError(
                        f"The zip {archive.name} has an unsafe path: {member.filename}"
                    )
            bundle.extractall(target)
    except zipfile.BadZipFile as error:
        raise InputError(f"{archive.name} is not a readable zip file.") from error
    marker.write_text("done\n", encoding="utf-8")
    return target


def resolve(
    source: Path, find: Callable[[Path], list[Path]], workdir: Path, accept_files: bool = True
) -> list[Path]:
    """The concrete inputs for `source`: itself (a file), or what `find` locates inside a folder or
    an unpacked zip. Raises `InputError` when there is nothing to read."""
    if not source.exists():
        raise InputError(f"Not found: {source}")
    if source.is_file() and source.suffix.lower() == ".zip":
        found = find(unpack(source, workdir))
    elif source.is_dir():
        found = find(source)
    elif accept_files:
        found = [source]
    else:
        found = []
    if not found:
        raise InputError(f"Nothing to import was found in {source}.")
    return sorted(found)
