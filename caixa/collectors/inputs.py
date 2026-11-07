"""Turning what a person points at (a file, a folder or a zip) into the inputs a collector reads.

A zip is unpacked into a working folder first, safely: a member whose path would land outside that
folder is refused. A folder is searched for what the collector reads (every WhatsApp `_chat.txt`,
every Meta thread, …). A plain file is used as it is.
"""

from __future__ import annotations

import hashlib
import zipfile
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Callable, Optional


class InputError(Exception):
    """The source can't be used (not found, nothing in it, an unsafe zip).

    `summary` is the one-sentence answer; `details` are further lines that help find the cause. The
    text of the error is both, one per line, so a log, a job and a screen all carry them.
    """

    def __init__(self, message: str, details: Sequence[str] = ()) -> None:
        self.summary = message
        self.details = list(details)
        super().__init__("\n".join([message, *self.details]))


def shape(name: str) -> str:
    """A file name with the person taken out: letters become x (X for capitals), digits become 9.

    What is left shows the pattern (`(9999-99-99) 99 99 99 - Xxxxx Xxxxxxx.amr`) and the type of
    file, so it can be shown and pasted without repeating anyone's name, number or date.
    """
    stem, dot, suffix = name.rpartition(".")
    if not dot or not suffix or " " in suffix:
        stem, suffix, dot = name, "", ""

    def hide(text: str) -> str:
        return "".join(
            "9" if c.isdigit() else ("X" if c.isupper() else "x") if c.isalpha() else c
            for c in text
        )

    return hide(stem) + dot + suffix.lower()


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
        raise InputError(
            f"{archive.name} is not a readable zip file.",
            [
                f"The file is {archive.stat().st_size} bytes. A real zip begins with the letters PK; "
                "this does not (a download that stopped early, or a different kind of file with a "
                ".zip name, would look like this)."
            ],
        ) from error
    marker.write_text("done\n", encoding="utf-8")
    return target


def resolve(
    source: Path,
    find: Callable[[Path], list[Path]],
    workdir: Path,
    accept_files: bool = True,
    expects: str = "",
    hints: Optional[Callable[[list[Path]], list[str]]] = None,
) -> list[Path]:
    """The concrete inputs for `source`: itself (a file), or what `find` locates inside a folder or
    an unpacked zip. Raises `InputError` when there is nothing to read; then `expects` says what was
    being looked for and `hints` (given the files that were there) may say what looks wrong."""
    if not source.exists():
        raise InputError(f"Not found: {source}", _missing(source))
    folder: Optional[Path] = None
    if source.is_file() and source.suffix.lower() == ".zip":
        folder = unpack(source, workdir)
        found = find(folder)
    elif source.is_dir():
        folder = source
        found = find(source)
    elif accept_files:
        found = [source]
    else:
        found = []
    if not found:
        raise InputError(
            f"Nothing to import was found in {source}.",
            _what_was_seen(source, folder, expects, hints),
        )
    return sorted(found)


def _missing(source: Path) -> list[str]:
    parent = source.parent
    if parent.is_dir():
        count = sum(1 for _ in parent.iterdir())
        return [f"Its folder is there ({parent}, {count} items) but nothing in it has that name."]
    return [f"Its folder is not there either: {parent}. Check the spelling of the whole path."]


def _is_system(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return parts[0] == "__MACOSX" or any(part.startswith(".") for part in parts)


def _what_was_seen(
    source: Path,
    folder: Optional[Path],
    expects: str,
    hints: Optional[Callable[[list[Path]], list[str]]],
) -> list[str]:
    lines: list[str] = []
    if folder is None:
        lines.append(
            f"What Caixa saw: a single file ({shape(source.name)}), but this source needs a "
            "folder or a .zip."
        )
    else:
        kind = "a zip" if source.is_file() else "a folder"
        every = sorted(p for p in folder.rglob("*") if p.is_file() and p.name != ".unpacked")
        files = [p for p in every if not _is_system(p, folder)]
        ignored = len(every) - len(files)
        if not files:
            lines.append(f"What Caixa saw: {kind} that is empty.")
        else:
            folders = len({p.parent for p in files} - {folder})
            where = f" in {folders} folder{'s' if folders != 1 else ''}" if folders else ""
            lines.append(
                f"What Caixa saw: {kind} with {len(files)} file{'s' if len(files) != 1 else ''}{where}."
            )
            types = Counter(p.suffix.lower() or "(no extension)" for p in files)
            lines.append(
                "File types: " + ", ".join(f"{n} {t}" for t, n in types.most_common(6)) + "."
            )
            examples = ", ".join(f"'{shape(p.name)}'" for p in files[:5])
            lines.append(f"Examples (letters shown as x, digits as 9): {examples}.")
        if ignored:
            lines.append(f"{ignored} hidden or Mac system files were ignored.")
        inner = [p for p in files if p.suffix.lower() == ".zip"]
        if inner:
            lines.append(
                f"It holds another .zip ({len(inner)}): unzip it and choose that folder, or "
                "choose the inner zip itself."
            )
        if hints and files:
            lines.extend(hints(files))
    if expects:
        lines.append(f"Looking for: {expects}.")
    return lines
