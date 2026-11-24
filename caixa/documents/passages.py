"""Passages: what semantic search compares, cut from each page's text.

A page's text is cut into passages of about `SIZE` characters, each overlapping the one before by
about `OVERLAP` (so a sentence cut in two is whole in one of them), cut where a sentence or a word
ends. Each passage keeps where it starts and ends in its page's text.
"""

from __future__ import annotations

import re

SIZE = 1000
OVERLAP = 150
_SPACE = re.compile(r"\s")


def _trimmed(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def split(text: str, size: int = SIZE, overlap: int = OVERLAP) -> list[tuple[int, int, str]]:
    """(start, end, passage) for the passages of `text` (see the module text)."""
    length = len(text)
    found: list[tuple[int, int, str]] = []
    start = 0
    while start < length:
        end = min(length, start + size)
        if end < length:
            window = text[start + size // 2 : end + 1]
            sentence = max(window.rfind(". "), window.rfind(".\n"))
            spaces = [m.start() for m in _SPACE.finditer(window)]
            if sentence >= 0:
                end = start + size // 2 + sentence + 1
            elif spaces:
                end = start + size // 2 + spaces[-1]
        first, last = _trimmed(text, start, end)
        if last > first:
            found.append((first, last, text[first:last]))
        if end >= length:
            break
        following = max(end - overlap, start + 1)
        if following > 0 and not text[following - 1].isspace():
            space = _SPACE.search(text, following)
            following = space.end() if space and space.start() < end else end
        start = following
    return found


__all__ = ["OVERLAP", "SIZE", "split"]
