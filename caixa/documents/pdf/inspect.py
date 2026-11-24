"""Inspecting a PDF page by page: is its text usable, or does the page need OCR?

Each page is measured (`measure`), then given one class (`classify`):

- `text`: digital text a person can read and a computer can extract;
- `needs_ocr`: a picture of a page (a scan) with no text, or almost none, on it;
- `ocr_layer`: a picture with invisible text over it, as OCR software leaves it; *poor* when that
  text is mostly not words, so OCR should be done again;
- `broken_text`: visible text whose extraction is garbage (a font with no map to Unicode): the page
  looks right and searches find nothing;
- `blank`: nothing on it.

The measures are plain numbers kept with the page (`quality`), so a later look at a real PDF can
say why a page was judged as it was. The thresholds were set on the synthetic PDF family and are
adjusted on real PDFs.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Optional

#: The share of bad characters (Private Use Area, U+FFFD, controls) above which text is broken.
BROKEN = 0.3
#: The share of invisible characters above which a page's text is an OCR layer.
INVISIBLE = 0.5
#: The share of word-like tokens below which visible text is broken, and an OCR layer poor.
WORDS_BROKEN = 0.35
WORDS_POOR = 0.6
#: A page covered this much by pictures, with fewer characters than `FEW`, is a scan.
COVERED = 0.6
FEW = 40
#: Below this many letters, the share of word-like tokens says nothing.
MEASURABLE = 20

_VOWELS = set("aeiouyáàâãäéèêëíìîïóòôõöúùûüAEIOUYÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜ")
_TOKEN = re.compile(r"\S+")
_EDGES = ".,;:!?()[]{}\"'«»“”‘’-–—/"


def _bad(ch: str) -> bool:
    code = ord(ch)
    return 0xE000 <= code <= 0xF8FF or code == 0xFFFD or (code < 32 and ch not in "\t\n\r")


def _wordlike(token: str) -> bool:
    """Letters only (after punctuation at its edges), with a vowel unless it is one letter."""
    core = token.strip(_EDGES)
    if not core or not any(ch.isalpha() for ch in core):
        return False
    if not all(ch.isalpha() or ch in "'’-" for ch in core):
        return False
    return len(core) == 1 or any(ch in _VOWELS for ch in core)


@dataclass(frozen=True)
class Measures:
    characters: int  # not counting spaces
    bad_share: float
    word_share: float  # word-like tokens among tokens with letters (1.0 when there are none)
    letters: int
    invisible_share: float
    image_cover: float  # 0..1 of the page
    drawings: int


@dataclass(frozen=True)
class PageInspection:
    number: int  # from 1
    page_class: str
    poor: bool  # an OCR layer to be done again
    text: str
    measures: Measures
    width: float
    height: float
    rotation: int

    def quality(self) -> dict[str, Any]:
        """What is kept with the page: its measures, its size and whether its layer is poor."""
        return {
            **asdict(self.measures),
            "poor": self.poor,
            "width": round(self.width, 1),
            "height": round(self.height, 1),
            "rotation": self.rotation,
        }

    @property
    def needs_ocr(self) -> bool:
        return self.page_class in ("needs_ocr", "broken_text") or self.poor


def _cover(page: Any) -> float:
    import pymupdf

    area = abs(page.rect) or 1.0
    boxes = [pymupdf.Rect(info["bbox"]) & page.rect for info in page.get_image_info()]
    boxes = [b for b in boxes if not b.is_empty]
    if not boxes:
        return 0.0
    if len(boxes) == 1:
        return min(1.0, abs(boxes[0]) / area)
    # several pictures: their union on a coarse grid (exact enough to tell a scan from a logo)
    steps = 40
    covered = 0
    for row in range(steps):
        for column in range(steps):
            x = page.rect.x0 + (column + 0.5) * page.rect.width / steps
            y = page.rect.y0 + (row + 0.5) * page.rect.height / steps
            covered += any(b.contains(pymupdf.Point(x, y)) for b in boxes)
    return covered / (steps * steps)


def measure(page: Any) -> Measures:
    """The numbers a page is judged by."""
    text = page.get_text()
    visible = [ch for ch in text if not ch.isspace()]
    characters = len(visible)
    bad = sum(_bad(ch) for ch in visible)
    tokens = [t for t in _TOKEN.findall(text) if any(ch.isalpha() for ch in t)]
    words = sum(_wordlike(t) for t in tokens)
    letters = sum(ch.isalpha() for ch in visible)
    traced = page.get_texttrace()
    drawn = sum(len(span["chars"]) for span in traced) or 1
    invisible = sum(len(span["chars"]) for span in traced if span.get("type") == 3)
    return Measures(
        characters=characters,
        bad_share=round(bad / characters, 3) if characters else 0.0,
        word_share=round(words / len(tokens), 3) if tokens else 1.0,
        letters=letters,
        invisible_share=round(invisible / drawn, 3) if traced else 0.0,
        image_cover=round(_cover(page), 3),
        drawings=len(page.get_drawings()),
    )


def classify(measures: Measures) -> tuple[str, bool]:
    """A page's class and whether it is a poor OCR layer, from its measures."""
    if measures.characters == 0:
        nothing = measures.image_cover < 0.01 and measures.drawings == 0
        return ("blank" if nothing else "needs_ocr"), False
    invisible = measures.invisible_share > INVISIBLE
    if measures.bad_share > BROKEN:
        return ("ocr_layer", True) if invisible else ("broken_text", False)
    measurable = measures.letters >= MEASURABLE
    if invisible:
        return "ocr_layer", measurable and measures.word_share < WORDS_POOR
    if measurable and measures.word_share < WORDS_BROKEN:
        return "broken_text", False
    if measures.image_cover > COVERED and measures.characters < FEW:
        return "needs_ocr", False
    return "text", False


def inspect_pdf(doc: Any) -> list[PageInspection]:
    """Every page of an open (and, if it needs one, unlocked) PDF, inspected."""
    found = []
    for index, page in enumerate(doc):
        measures = measure(page)
        page_class, poor = classify(measures)
        text = page.get_text()
        found.append(
            PageInspection(
                number=index + 1,
                page_class=page_class,
                poor=poor,
                text="" if page_class == "blank" else text,
                measures=measures,
                width=page.mediabox.width,
                height=page.mediabox.height,
                rotation=page.rotation,
            )
        )
    return found


def text_hash(pages: Iterable[str]) -> Optional[str]:
    """A fingerprint of a document's words (case and spacing aside), or None without any: two
    different files with the same text (a statement downloaded twice) share it."""
    words = " ".join(" ".join(pages).casefold().split())
    if not words:
        return None
    return hashlib.sha256(words.encode("utf-8")).hexdigest()


__all__ = ["Measures", "PageInspection", "classify", "inspect_pdf", "measure", "text_hash"]
