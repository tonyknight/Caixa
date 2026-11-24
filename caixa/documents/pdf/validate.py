"""Validating a processed PDF against the one it was made from, before it is accepted.

Processing (OCR) may damage a PDF, so it is never trusted. A processed file is accepted only if
every check passes:

- **structure**: the file exists and is not empty (`exists`); it opens in PyMuPDF without having
  to be repaired (`opens`) and needs no password (`unlocked`); an independent parser, pikepdf,
  finds no structural problem (`structure`; skipped, not failed, where pikepdf is not installed);
- **content**: the same number of pages (`pages`); each the same size and rotation (`sizes`);
  the text of every page that had text still on the same page, so nothing was lost or reordered
  (`text`); text on every page OCR worked on (`ocr_text`); no page with fewer pictures (`pictures`);
- **appearance**: each page drawn from both files looks the same (`appearance`). OCR adds
  invisible text, so the visible page must not change.

A failure is not an error: the result says which checks failed and why, and the import keeps the
unchanged copy instead.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

#: Page sizes may differ by this much (points) and still be the same.
SIZE_TOLERANCE = 0.5
#: The share of a page's words that must still be on it after processing.
TEXT_KEPT = 0.98
#: Appearance: resolution of the comparison renders, and how far (of 255) the mean difference of
#: a whole page, and of any block of `BLOCK` pixels, may go.
RENDER_DPI = 40
MEAN_TOLERANCE = 2.0
BLOCK = 16
BLOCK_TOLERANCE = 24.0
#: A picture smaller than this (pixels a side) does not count (a deleted image's stand-in).
TINY = 4


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Validation:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def add(self, name: str, passed: bool, detail: str = "") -> bool:
        self.checks.append(Check(name, passed, detail))
        return passed

    def report(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": [asdict(check) for check in self.checks]}


def _words(text: str) -> list[str]:
    return text.casefold().split()


def _pictures(page: Any) -> int:
    return sum(
        1 for info in page.get_image_info() if info["width"] > TINY and info["height"] > TINY
    )


def _structure(output: Path) -> tuple[Optional[bool], str]:
    """pikepdf's (qpdf's) check: an error fails, a warning is only noted."""
    try:
        import pikepdf
    except ImportError:
        return None, "pikepdf is not installed: checked by PyMuPDF only"
    try:
        with pikepdf.open(output) as pdf:
            check = getattr(pdf, "check_pdf_syntax", None) or getattr(pdf, "check")
            problems = [str(p) for p in check()]
    except Exception as error:  # pikepdf refuses what it cannot parse
        return False, f"{type(error).__name__}: {error}"
    errors = [p for p in problems if not p.startswith("WARNING")]
    return (not errors), "; ".join((errors or problems)[:5])


def _render(page: Any) -> Any:
    import numpy as np
    import pymupdf

    picture = page.get_pixmap(dpi=RENDER_DPI, colorspace=pymupdf.csGRAY, alpha=False)
    return np.frombuffer(picture.samples, dtype=np.uint8).reshape(picture.height, picture.width)


def _looks_the_same(before: Any, after: Any) -> tuple[bool, str]:
    import numpy as np

    if before.shape != after.shape:
        return (
            False,
            f"drawn at {after.shape[1]}×{after.shape[0]}, was {before.shape[1]}×{before.shape[0]}",
        )
    difference = np.abs(before.astype(np.int16) - after.astype(np.int16))
    mean = float(difference.mean())
    rows, columns = difference.shape[0] // BLOCK, difference.shape[1] // BLOCK
    worst = 0.0
    if rows and columns:
        blocks = difference[: rows * BLOCK, : columns * BLOCK].reshape(rows, BLOCK, columns, BLOCK)
        worst = float(blocks.mean(axis=(1, 3)).max())
    same = mean <= MEAN_TOLERANCE and worst <= BLOCK_TOLERANCE
    return same, f"mean difference {mean:.2f}, largest in a block {worst:.1f}"


def validate(source: Path, output: Path, ocr_pages: Sequence[int]) -> Validation:
    """Check `output` (a processed copy of `source`) as the module text says. `ocr_pages` are
    the pages (from 1) OCR gave a text layer: they must have text, and may have new text."""
    import pymupdf

    pymupdf.TOOLS.mupdf_display_errors(False)
    result = Validation()
    if not result.add("exists", output.is_file() and output.stat().st_size > 0, str(output.name)):
        return result
    try:
        after = pymupdf.open(output)
    except Exception as error:
        result.add("opens", False, f"{type(error).__name__}: {error}")
        return result
    with after, pymupdf.open(source) as before:
        if not result.add(
            "opens", not after.is_repaired, "it had to be repaired" if after.is_repaired else ""
        ):
            return result
        if not result.add(
            "unlocked", not after.needs_pass, "it needs a password" if after.needs_pass else ""
        ):
            return result
        structure, detail = _structure(output)
        result.add(
            "structure",
            structure is not False,
            detail if structure is not None else f"skipped: {detail}",
        )
        if not result.add("pages", after.page_count == before.page_count,
                          f"{after.page_count} pages, was {before.page_count}"):  # fmt: skip
            return result
        sizes, text, pictures, ocr_text, looks = [], [], [], [], []
        for index in range(before.page_count):
            number = index + 1
            old, new = before[index], after[index]
            if (
                abs(old.mediabox.width - new.mediabox.width) > SIZE_TOLERANCE
                or abs(old.mediabox.height - new.mediabox.height) > SIZE_TOLERANCE
                or old.rotation != new.rotation
            ):
                sizes.append(number)
            if number not in ocr_pages:
                words = _words(old.get_text())
                if words:
                    kept = set(_words(new.get_text()))
                    if sum(word in kept for word in words) / len(words) < TEXT_KEPT:
                        text.append(number)
            elif not new.get_text().strip():
                ocr_text.append(number)
            if _pictures(new) < _pictures(old):
                pictures.append(number)
            same, why = _looks_the_same(_render(old), _render(new))
            if not same:
                looks.append(f"page {number}: {why}")
        result.add("sizes", not sizes, f"pages {sizes} differ in size or rotation" if sizes else "")
        result.add("text", not text, f"pages {text} lost text, or it moved" if text else "")
        result.add(
            "ocr_text", not ocr_text, f"pages {ocr_text} have no text after OCR" if ocr_text else ""
        )
        result.add("pictures", not pictures, f"pages {pictures} lost pictures" if pictures else "")
        result.add("appearance", not looks, "; ".join(looks[:5]))
    return result


__all__ = ["Check", "Validation", "validate"]
