"""Store files by the hash of their content.

A file is written once, at `<root>/<first two hex digits>/<sha256><extension>`, however many times
it turns up. Attachments pulled out of mail (which exist only inside the mailbox) are kept this
way; the hash is what the archive records, and what lets identical files collapse.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
from pathlib import Path
from typing import Callable, Optional, Union


def store_by_hash(root: Union[str, Path], data: bytes, suffix: str = "") -> tuple[str, str]:
    """Write `data` under its SHA-256; returns `(sha256, path relative to root)`.

    The suffix is cleaned to letters and digits (at most 10), lower case, so a hostile file name
    can't escape the folder.
    """
    digest = hashlib.sha256(data).hexdigest()
    extension = re.sub(r"[^a-z0-9]", "", suffix.lower())[:10]
    relative = f"{digest[:2]}/{digest}" + (f".{extension}" if extension else "")
    target = Path(root) / relative
    if not target.exists():
        _place(target, lambda temporary: temporary.write_bytes(data))
    return digest, relative


def _place(target: Path, write: Callable[[Path], object]) -> None:
    """Write a file through a temporary file of this writer's own, then move it into place.

    Never a half-written file under its final name. Several writers may store the same file at
    once (a mail import's worker processes): each has its own temporary file, so none moves
    another's away, and the last move leaves the same bytes."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{os.getpid()}-{secrets.token_hex(4)}.part")
    try:
        write(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def store_file_by_hash(root: Union[str, Path], source: Union[str, Path], digest: str) -> str:
    """Copy the file `source` (whose SHA-256 is `digest`) under its hash; returns the path relative
    to `root`. The file is copied, never moved, and never read into memory whole."""
    extension = re.sub(r"[^a-z0-9]", "", Path(source).suffix.lower())[:10]
    relative = f"{digest[:2]}/{digest}" + (f".{extension}" if extension else "")
    target = Path(root) / relative
    if not target.exists():
        _place(target, lambda temporary: shutil.copyfile(source, temporary))
    return relative


class Finder:
    """Find the file a stored path means under one of several roots.

    As `(root / path).resolve()` kept only when it is a file inside `root`: a symlink or `..`
    leading out of the root is refused. Each folder is resolved once (a redraw looks up tens of
    thousands of files in a few hundred folders), so use one finder for one run: a folder that is
    moved or replaced by a link meanwhile is not seen again.
    """

    def __init__(self) -> None:
        self._folders: dict[str, str] = {}

    def find(self, storage_path: str, roots: list[Path]) -> Optional[tuple[Path, Path]]:
        for root in roots:
            folder, name = os.path.split(os.path.join(root, storage_path))
            real = self._folders.get(folder)
            if real is None:
                real = self._folders[folder] = os.path.realpath(folder)
            candidate = os.path.join(real, name)
            if os.path.islink(candidate) or name in ("", ".", ".."):
                candidate = os.path.realpath(candidate)
            inside = candidate.startswith(str(root).rstrip(os.sep) + os.sep)
            if inside and os.path.isfile(candidate):
                return Path(candidate), root
        return None
