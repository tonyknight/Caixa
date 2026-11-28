"""What the owner has taught Caixa about authors, kept in the box and read by `prepare`.

`.caixa/author-knowledge.json` holds three lists and nothing from a page (D29):

- **accepted:** authors the owner has confirmed;
- **rejected:** names that are not authors here (an invented city, a software name, `null`, a
  year). The box's owner is never rejected;
- **instead:** a name a model said, the author to use, and the document's kind when the lesson
  came from correcting one document. A rename or a merge has no kind.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

FILE = "author-knowledge.json"


def _same(one: str, other: str) -> bool:
    return " ".join(one.casefold().split()) == " ".join(other.casefold().split())


def _clean(name: str) -> str:
    return " ".join(name.split())


@dataclass
class Knowledge:
    accepted: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    instead: list[dict[str, str]] = field(default_factory=list)

    def _has(self, names: list[str], name: str) -> bool:
        return any(_same(kept, name) for kept in names)


def path_of(box: object) -> Path:
    return Path(box.caixa_dir) / FILE  # type: ignore[attr-defined]


def load(box: object) -> Knowledge:
    """The box's lessons, or three empty lists when the file is not there yet."""
    file = path_of(box)
    try:
        saved = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Knowledge()
    if not isinstance(saved, dict):
        return Knowledge()

    def strings(key: str) -> list[str]:
        found = saved.get(key)
        return [str(item) for item in found if str(item).strip()] if isinstance(found, list) else []

    lessons = []
    for item in saved.get("instead") or []:
        if isinstance(item, dict) and item.get("said") and item.get("use"):
            lesson = {"said": str(item["said"]), "use": str(item["use"])}
            if item.get("kind"):
                lesson["kind"] = str(item["kind"])
            lessons.append(lesson)
    return Knowledge(strings("accepted"), strings("rejected"), lessons)


def save(box: object, known: Knowledge) -> None:
    """Write the file for the owner alone."""
    file = path_of(box)
    file.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "accepted": list(known.accepted),
        "rejected": list(known.rejected),
        "instead": list(known.instead),
    }
    part = file.with_name(file.name + ".part")
    handle = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        json.dump(body, out, ensure_ascii=False, indent=2)
        out.write("\n")
    os.chmod(part, 0o600)
    os.replace(part, file)
    os.chmod(file, 0o600)


def _accept(known: Knowledge, name: str) -> None:
    name = _clean(name)
    if name and not known._has(known.accepted, name):
        known.accepted.append(name)


def _reject(known: Knowledge, name: str, owner: Optional[str]) -> None:
    """Reject `name` unless it is the owner or already an accepted author."""
    name = _clean(name)
    if not name:
        return
    if owner and _same(name, owner):
        return
    if known._has(known.accepted, name) or known._has(known.rejected, name):
        return
    known.rejected.append(name)


def _remember(known: Knowledge, said: str, use: str, kind: Optional[str]) -> None:
    said, use = _clean(said), _clean(use)
    if not said or not use or _same(said, use):
        return
    for lesson in known.instead:
        if _same(lesson["said"], said) and lesson.get("kind") == (kind or None):
            lesson["use"] = use
            return
    lesson = {"said": said, "use": use}
    if kind:
        lesson["kind"] = kind
    known.instead.append(lesson)


def learn_correction(
    known: Knowledge, said: str, use: str, kind: Optional[str], owner: Optional[str]
) -> None:
    """One document was corrected from `said` to `use`. The owner is never rejected."""
    _accept(known, use)
    _reject(known, said, owner)
    _remember(known, said, use, kind or None)


def learn_rename(known: Knowledge, said: str, use: str, owner: Optional[str]) -> None:
    """A rename or a merge: `said` means `use` on every document. The owner is never rejected."""
    _accept(known, use)
    _remember(known, said, use, None)


def apply(known: Knowledge, author: str, kind: Optional[str] = None) -> Optional[str]:
    """The author to file, or None when a rejected name has no lesson.

    A lesson for this document's kind wins over a lesson that applies to every kind.
    """
    author = _clean(author)
    fallback: Optional[str] = None
    for lesson in known.instead:
        if not _same(lesson["said"], author):
            continue
        if kind and lesson.get("kind") == kind:
            author = _clean(lesson["use"])
            fallback = None
            break
        if not lesson.get("kind") and fallback is None:
            fallback = _clean(lesson["use"])
    else:
        if fallback:
            author = fallback
    if known._has(known.rejected, author):
        return None
    return author or None
