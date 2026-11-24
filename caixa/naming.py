"""Caixa's archival names: how a file brought into a box is named, whatever collected it.

    (DATE) Title - Author.ext

The convention is documented in `docs/Archival names.md`, with examples the tests check against
this module. It extends what Caixa already does for attachments, conversation pages and mboxes
(`(YYYY-MM-DD) name`, ` (2)` on a clash) and is meant for every collector of files: documents
first, photos and videos later.

- **The date** is written at the precision it is known: `(2024-11-30)`, `(2024-11)`, `(2024)`. A
  full date is never made up from a partial one (`NamingDate`).
- **The title** says what the thing is, without repeating the date or the author.
- **The author** (issuer, sender, creator) follows a dash; it is left out when unknown.
- **Characters** a file system refuses are replaced (`clean`), and a name written in capitals is
  given ordinary capitals.
- **Length**: a name is cut after `LIMIT` characters (the extension and any ` (2)` aside), at a word.
- **Clashes**: a different file with the same name gets ` (2)`, ` (3)`… (`free_path`); the same
  file is recognised by its SHA-256.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import Optional

#: The most characters of a name before its extension (and before any ` (2)`).
LIMIT = 110
#: A name part written in capitals with more letters than this is given ordinary capitals.
SHOUTING = 5
#: Words that stay lower case inside a title made from capitals (English and Portuguese).
JOINING = frozenset(
    "a o e de da do das dos em no na nos nas para por of the and for in on to at".split()
)
#: A title cut shorter than this to fit an author is cut as a whole name instead.
SHORTEST_TITLE = 12

_SPACES = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_DROPPED = str.maketrans({"*": None, "?": None, "<": None, ">": None, '"': "'"})
_DASHED = str.maketrans({"/": "-", "\\": "-", "|": "-"})
_DATE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")
_LEADING_DATE = re.compile(r"^\(?\d{4}(?:-\d{2}(?:-\d{2})?)?\)?(?:\s*[-–,:]\s*|\s+)")


class NamingError(ValueError):
    """A name cannot be made from what was given."""


@dataclass(frozen=True)
class NamingDate:
    """A date at the precision it is known: `day`, `month` or `year`."""

    value: str
    precision: str

    @classmethod
    def parse(cls, value: str) -> "NamingDate":
        match = _DATE.match(value or "")
        if not match:
            raise NamingError(f"{value!r} is not a date (YYYY, YYYY-MM or YYYY-MM-DD).")
        year, month, day = match.groups()
        try:
            _date(int(year), int(month or 1), int(day or 1))
        except ValueError as error:
            raise NamingError(f"{value!r} is not a date: {error}.") from None
        precision = "day" if day else "month" if month else "year"
        return cls(value, precision)

    @property
    def year(self) -> int:
        return int(self.value[:4])

    @property
    def prefix(self) -> str:
        return f"({self.value})"


def _calm(word: str) -> str:
    """One word of a name written in capitals, in ordinary capitals."""
    if "." in word:  # an abbreviation: S.A., N.A.
        return word
    return word[:1].upper() + word[1:].lower()


def _unshout(text: str) -> str:
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) <= SHOUTING or any(ch.islower() for ch in letters):
        return text
    words = text.split(" ")
    calmed = [_calm(word) for word in words]
    for index, word in enumerate(calmed[1:], start=1):
        if word.lower() in JOINING:
            calmed[index] = word.lower()
    return " ".join(calmed)


def clean(text: Optional[str], capitals: bool = True) -> str:
    """A part of a name made safe for any file system: NFC; control characters out; `/ \\ |` as
    `-`, `:` as ` - `, `* ? < >` out, `"` as `'`; spaces collapsed; no dot, space or dash at
    either end. With `capitals`, a part written all in capitals gets ordinary capitals."""
    result = unicodedata.normalize("NFC", text or "")
    result = re.sub(r"[\t\n\r\f\v]", " ", result)
    result = _CONTROL.sub("", result)
    result = result.translate(_DROPPED).translate(_DASHED).replace(":", " - ")
    result = _SPACES.sub(" ", result).strip(" .-")
    return _unshout(result) if capitals else result


def _cut(text: str, limit: int) -> str:
    """`text` within `limit` characters, cut where a word ends when one ends late enough."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if text[limit] != " ":
        space = cut.rfind(" ")
        if space > limit // 2:
            cut = cut[:space]
    return cut.rstrip(" -.,;")


def _without(title: str, author: str) -> str:
    """The title without the author at its start or end, when something is left."""
    pattern = re.escape(author)
    for form in (rf"^{pattern}(?:\s*[-–,:]\s*|\s+)", rf"(?:\s*[-–,:]\s*|\s+){pattern}$"):
        shorter = re.sub(form, "", title, flags=re.IGNORECASE).strip(" .-")
        if shorter and shorter != title:
            return shorter
    return title


def _extension(extension: str) -> str:
    extension = extension.strip().lower()
    return extension if not extension or extension.startswith(".") else f".{extension}"


def archival_name(
    date: NamingDate, title: str, author: Optional[str] = None, extension: str = ".pdf"
) -> str:
    """`(DATE) Title - Author.ext`, or `(DATE) Title.ext` without an author, within `LIMIT`."""
    who = clean(author) if author else ""
    what = _LEADING_DATE.sub("", clean(title)).strip(" .-")
    if who:
        what = _without(what, who)
    if not what:
        raise NamingError(f"A name needs a title; {title!r} has none.")
    head, tail = f"{date.prefix} ", f" - {who}" if who else ""
    stem = head + what + tail
    if len(stem) > LIMIT:
        room = LIMIT - len(head) - len(tail)
        stem = head + _cut(what, room) + tail if room >= SHORTEST_TITLE else _cut(stem, LIMIT)
    return stem + _extension(extension)


def original_name(filename: str) -> str:
    """A file's own name made safe (capitals as they are), within `LIMIT`: how a file Caixa could
    not name yet is kept."""
    path = Path(filename.strip())
    stem = _cut(clean(path.stem, capitals=False), LIMIT)
    if not stem:
        raise NamingError(f"{filename!r} has no usable name.")
    return stem + _extension(path.suffix)


def folder_name(text: str) -> str:
    """A folder named after an author (or anything else), cleaned like a part of a name."""
    name = _cut(clean(text), LIMIT)
    if not name:
        raise NamingError(f"{text!r} cannot name a folder.")
    return name


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def free_path(folder: Path, name: str, sha256: Optional[str] = None) -> Path:
    """`folder/name`, or the first `stem (2).ext`, `stem (3).ext`… not held by another file. A
    file there with the same `sha256` is the same file, and its path is returned."""
    path = Path(name)
    stem, extension = path.stem, path.suffix
    number = 1
    while True:
        candidate = folder / (name if number == 1 else f"{stem} ({number}){extension}")
        if not candidate.exists():
            return candidate
        if sha256 and candidate.is_file() and _sha256(candidate) == sha256:
            return candidate
        number += 1


__all__ = [
    "LIMIT",
    "NamingDate",
    "NamingError",
    "archival_name",
    "clean",
    "folder_name",
    "free_path",
    "original_name",
]
