"""The fast paths of a redraw give exactly what the slow ones gave: a page's data island escaped
in one pass, and stored files found under their root with each folder resolved once (a symlink
or `..` that leads out of the root is refused, as before)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from chattr import blobs
from chattr.pages import _ISLAND_ESCAPES, island_json


def _slow(document: object) -> str:  # what island_json did before
    import json

    text = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    return "".join(_ISLAND_ESCAPES.get(ch, ch) for ch in text)


def test_the_island_is_escaped_as_before() -> None:
    awkward = {
        "body": "</script><script>alert(1)</script> & <b>",
        "lines": "a b c",
        "names": ["Ana Costa", "João", "😀", "\x00\x1f"],
        "n": 3,
    }
    assert island_json(awkward) == _slow(awkward)
    assert "</script>" not in island_json(awkward) and " " not in island_json(awkward)


def _old(storage_path: str, roots: list[Path]):  # what filing._locate did before
    for root in roots:
        candidate = (root / storage_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(root):
            return candidate, root
    return None


@pytest.fixture
def roots(tmp_path: Path) -> list[Path]:
    box, staging, outside = tmp_path / "box", tmp_path / "staging", tmp_path / "outside"
    for folder in (box / "People" / "Ana Costa", staging / "ab", outside):
        folder.mkdir(parents=True)
    (box / "People" / "Ana Costa" / "photo.jpg").write_bytes(b"x")
    (staging / "ab" / "abcd.png").write_bytes(b"y")
    (outside / "secret.txt").write_bytes(b"z")
    os.symlink(outside / "secret.txt", box / "People" / "link.txt")  # a file leading out
    os.symlink(outside, box / "People" / "away")  # a folder leading out
    os.symlink(box / "People" / "Ana Costa" / "photo.jpg", box / "People" / "inside.jpg")
    return [box.resolve(), staging.resolve()]


@pytest.mark.parametrize(
    "stored",
    [
        "People/Ana Costa/photo.jpg",
        "ab/abcd.png",
        "People/Ana Costa/missing.jpg",
        "People/../../outside/secret.txt",
        "People/link.txt",
        "People/away/secret.txt",
        "People/inside.jpg",
        "People/Ana Costa",
        "People/Ana Costa/..",
    ],
)
def test_a_stored_file_is_found_as_before(roots: list[Path], stored: str) -> None:
    finder = blobs.Finder()
    assert finder.find(stored, roots) == _old(stored, roots)
    assert finder.find(stored, roots) == _old(stored, roots)  # (and again, from its cache)


def test_nothing_outside_the_roots_is_ever_found(roots: list[Path]) -> None:
    finder = blobs.Finder()
    for stored in ("People/link.txt", "People/away/secret.txt", "People/../../outside/secret.txt"):
        assert finder.find(stored, roots) is None
