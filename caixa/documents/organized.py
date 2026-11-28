"""Organized file names (D30): `(YYYY-MM-DD) Subject (Author) [Tag] [Tag].pdf`, read with no model.

Some owners have named their PDFs well already. `read_organized` reads such a name:

- the date in brackets at the start, as `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; a date that cannot be
  (`2024-02-30`, month `13`) is kept as written and marked `impossible`, never trimmed;
- the subject that follows;
- the author: the **last** `( … )` before the tags, so `Lease (signed copy) (Rui Pereira)` is the
  subject `Lease (signed copy)` by `Rui Pereira`. A month name or a number in those brackets is
  part of the subject, not an author;
- the tags: every `[ … ]` at the end;
- a copy number such as ` (2)` (as `free_path` adds to a second file of the same name), kept
  apart.

The author and the tags are optional; a date and a subject are not. A name that does not fit
gives `None`, and is prepared as any other PDF.

`on_page` says whether a date is written on the pages at its own precision, and `compatible`
whether two dates can be the same day (one is the other, or a coarser form of it); together they
decide whether the page contradicts a name's date (see `prepare`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Iterable, Optional

from caixa.documents.evidence import _MONTH, MONTHS, _plain, _valid, text_dates

_NAME = re.compile(
    r"^\((?P<year>\d{4})(?:-(?P<month>\d{2})(?:-(?P<day>\d{2}))?)?\)\s+(?P<rest>.+)$"
)
_DATE = re.compile(r"^\(\d{4}(?:-\d{2}){0,2}\)")
_COPY = re.compile(r"\s*\((\d{1,3})\)$")
_TAG = re.compile(r"\s*\[([^\[\]]+)\]$")
_LAST = re.compile(r"\s*\(([^()]+)\)$")


@dataclass
class OrganizedName:
    """What an organized file name says."""

    name: str  # the whole file name, as it is
    date: str  # as written: YYYY, YYYY-MM or YYYY-MM-DD
    precision: str  # year | month | day
    impossible: bool  # a month or a day that cannot be
    subject: str
    author: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    copy: Optional[str] = None  # "(2)"


def _not_an_author(text: str) -> bool:
    plain = _plain(text).strip(" .")
    return plain in MONTHS or not any(character.isalpha() for character in plain)


def read_organized(filename: str) -> Optional[OrganizedName]:
    """The parts of an organized name, or `None` when it does not fit (see the module text)."""
    path = PurePath(filename)
    found = _NAME.match(path.stem.strip())
    if not found:
        return None
    year, month, day = found.group("year"), found.group("month"), found.group("day")
    date = "-".join(part for part in (year, month, day) if part)
    precision = "day" if day else "month" if month else "year"
    if day:
        impossible = not _valid(int(year), int(month), int(day))
    elif month:
        impossible = not 1 <= int(month) <= 12
    else:
        impossible = False
    rest = found.group("rest").strip()
    copy = None
    numbered = _COPY.search(rest)
    if numbered:
        copy, rest = f"({numbered.group(1)})", rest[: numbered.start()].rstrip()
    tags: list[str] = []
    while (tag := _TAG.search(rest)) is not None:
        tags.insert(0, " ".join(tag.group(1).split()))
        rest = rest[: tag.start()].rstrip()
    author = None
    last = _LAST.search(rest)
    if last and rest[: last.start()].strip() and not _not_an_author(last.group(1)):
        author, rest = " ".join(last.group(1).split()), rest[: last.start()].rstrip()
    subject = " ".join(rest.split())
    if not subject:
        return None
    return OrganizedName(filename, date, precision, impossible, subject, author, tags, copy)


def with_date(filename: str, date: str) -> str:
    """The same name with only its date replaced."""
    return _DATE.sub(f"({date})", filename, count=1)


def compatible(one: str, other: str) -> bool:
    """Whether two dates can name the same day: equal, or one a coarser form of the other."""
    return one == other or one.startswith(other + "-") or other.startswith(one + "-")


def on_page(date: str, pages: Iterable[str]) -> bool:
    """Whether `date` is written on the pages at its own precision: a full date among the page's
    dates; a month or a year when a date in it is written, or the month and year, or the year,
    are written alone."""
    texts = [text or "" for text in pages]
    written = [d.value for d in text_dates((n, t, "pdf") for n, t in enumerate(texts, start=1))]
    if len(date) == 10:
        return date in written
    if any(value.startswith(date + "-") for value in written):
        return True
    year = date[:4]
    for text in texts:
        if len(date) == 4:
            if re.search(rf"(?<!\d){year}(?!\d)", text):
                return True
            continue
        month = int(date[5:7])
        if re.search(
            rf"(?<![\d/]){month:02d}/{year}(?![\d/])|(?<!\d){year}-{month:02d}(?![\d-])", text
        ):
            return True
        for found in re.finditer(rf"\b({_MONTH})\.?\s+(?:de\s+)?(\d{{4}})\b", _plain(text)):
            if MONTHS[found.group(1)] == month and found.group(2) == year:
                return True
    return False


__all__ = ["OrganizedName", "compatible", "on_page", "read_organized", "with_date"]
