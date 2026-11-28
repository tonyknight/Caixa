"""Organized file names (D30, as amended): `(YYYY-MM-DD) Subject (Author) [Tag].pdf` and the
forms like it, read with no model.

Some owners have named their PDFs well already, each in their own way. `read_organized` reads
such a name, wherever its parts are:

- the date in brackets at the start, as `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; a date that cannot be
  (`2024-02-30`, month `13`) is kept as written and marked `impossible`, never trimmed;
- the author: every `( … )` after the date names it, except a month name, a number or a copy
  number. The same name twice is one author; of two different names the last is the author, so
  `Lease (signed copy) (Rui Pereira)` is a lease by Rui Pereira. `(Author) Subject`,
  `Subject - (Author) - [Tag]` and `Subject (Author) [Tag]` all name theirs;
- the tags: every `[ … ]` (one in brackets of its own, `[(Name)]`, is `Name`), each once;
- a copy number: a trailing ` (2)`, ` 2` or ` - 2`, kept apart;
- the subject: what is left, ` - ` being a separator. An author at its start or end is taken
  out, and one inside it kept as its words (`August (Energia do Norte) Bill`).

The author and the tags are optional; a date and a subject are not. A name that does not fit
gives `None`, and is imported as any other PDF. `rewrite` changes one part of a name where it is
written, for the owner's corrections.

`on_page` says whether a date is written on the pages at its own precision, and `compatible`
whether two dates can be the same day (one is the other, or a coarser form of it); together they
decide whether the page contradicts a name's date (see `reconcile`).
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
_COPY = re.compile(r"\s*\((\d{1,3})\)$|(?:\s+-)?\s+(\d{1,2})$")
_TAGS = re.compile(r"\[([^\[\]]+)\]")
_GROUP = re.compile(r"\(([^()]+)\)")
_SEPARATORS = re.compile(r"\s+-\s+(?:-\s+)*")
_EDGES = " -_[]()"


@dataclass
class OrganizedName:
    """What an organized file name says."""

    name: str  # the whole file name, as it is
    date: str  # as written: YYYY, YYYY-MM or YYYY-MM-DD
    precision: str  # year | month | day
    impossible: bool  # a month or a day that cannot be
    subject: str
    author: Optional[str] = None  # the last of `authors`
    tags: list[str] = field(default_factory=list)
    copy: Optional[str] = None  # "(2)", or "2" for a bare copy number
    authors: list[str] = field(default_factory=list)  # every name in ( … ), each once


def _not_an_author(text: str) -> bool:
    plain = _plain(text).strip(" .")
    return plain in MONTHS or not any(character.isalpha() for character in plain)


def _key(text: str) -> str:
    return " ".join(text.casefold().split())


def _without(rest: str, author: str) -> str:
    """The subject's text with the author's brackets taken off: at its start or its end (a stray
    letter or bracket glued to it included), and kept as its words inside it."""
    pattern = r"\(\s*" + r"\s+".join(map(re.escape, author.split())) + r"\s*\)"
    rest = re.sub(r"^\s*" + pattern + r"(?=[\s-]|$)", " ", rest)  # at its start
    rest = re.sub(r"[\s-]*[A-Za-z]?" + pattern + r"[A-Za-z]?[\])]*\s*$", " ", rest)  # at its end
    return re.sub(pattern, author, rest)  # inside it


def _tidy(text: str) -> str:
    text = _SEPARATORS.sub(" - ", f" {text} ")
    text = " ".join(text.split())
    while text and (text[0] in _EDGES or text[-1] in _EDGES):
        before = text
        text = text.strip(" -_")
        if text.endswith(("]", ")")) and text.count(text[-1]) > text.count("[("[text[-1] == ")"]):
            text = text[:-1]
        if text.startswith(("[", "(")) and text.count(text[0]) > text.count("])"[text[0] == "("]):
            text = text[1:]
        if text == before:
            break
    return text


def _trailing_tags(rest: str) -> str:
    """`rest` without the tags and separators at its end."""
    while True:
        trimmed = re.sub(r"[\s-]*\[[^\[\]]*\][\s-]*$", "", rest)
        if trimmed == rest:
            return rest
        rest = trimmed


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
    if numbered and rest[: numbered.start()].strip():
        copy = f"({numbered.group(1)})" if numbered.group(1) else numbered.group(2)
        rest = rest[: numbered.start()].rstrip()
    tags: list[str] = []
    for tag in _TAGS.findall(rest):
        text = " ".join(tag.strip().strip("()").split())
        if text and _key(text) not in {_key(t) for t in tags}:
            tags.append(text)
    outside = _TAGS.sub(" ", rest)
    authors: list[str] = []
    for group in _GROUP.findall(outside):
        text = " ".join(group.split())
        if not _not_an_author(text) and _key(text) not in {_key(a) for a in authors}:
            authors.append(text)
    author = authors[-1] if authors else None
    rest = _trailing_tags(rest)
    subject = _trailing_tags(_without(rest, author)) if author else rest
    subject = _tidy(subject)
    if not subject:
        return None
    return OrganizedName(
        filename, date, precision, impossible, subject, author, tags, copy, authors
    )


def with_date(filename: str, date: str) -> str:
    """The same name with only its date replaced."""
    return _DATE.sub(f"({date})", filename, count=1)


def compose(name: OrganizedName, date: str, subject: str, author: Optional[str]) -> str:
    """The owner's name written again in their own pattern, with this date, subject and author
    (no author: no brackets), and its tags and copy number as they were."""
    parts = [f"({date}) {' '.join(subject.split())}"]
    if author:
        parts.append(f"({' '.join(author.split())})")
    parts += [f"[{tag}]" for tag in name.tags]
    if name.copy:
        parts.append(name.copy)
    return " ".join(parts) + PurePath(name.name).suffix


def rewrite(
    name: OrganizedName,
    date: Optional[str] = None,
    subject: Optional[str] = None,
    author: Optional[str] = None,
) -> str:
    """The owner's name with only these parts changed, where they are written: the date; the
    author's brackets (or, when the name had none, the author put after the subject); the
    subject's words. When a part cannot be found as written, the name is written again with
    `compose`."""
    text = name.name
    if author and author != name.author:
        if name.author:
            pattern = r"\(\s*" + r"\s+".join(map(re.escape, name.author.split())) + r"\s*\)"
            text = re.sub(pattern, f"({author})", text)
        elif name.subject in text:
            text = text.replace(name.subject, f"{name.subject} ({author})", 1)
        else:
            return compose(name, date or name.date, subject or name.subject, author)
    if subject and subject != name.subject:
        if name.subject not in text:
            return compose(name, date or name.date, subject, author or name.author)
        text = text.replace(name.subject, subject, 1)
    if date and date != name.date:
        text = with_date(text, date)
    return text


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


__all__ = [
    "OrganizedName", "compatible", "compose", "on_page", "read_organized", "rewrite", "with_date",
]  # fmt: skip
