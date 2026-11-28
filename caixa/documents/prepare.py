"""Read a folder of PDFs with both models, beside any box, and compare where they file.

One run preprocesses every PDF once, asks Apple Intelligence and the local model the same
question, and files each answer under the output path (Apple) and `<output> local` (the local
model). Nothing is written into a box, and the originals are only read. See D28.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from caixa.documents.archive import DOCUMENTS, FORMAT_FOLDERS, _target
from caixa.naming import free_path

#: A first page this short, or saying so, is a cover in front of the document.
_COVER = re.compile(r"fax cover|transmission report|scan cover", re.IGNORECASE)


@dataclass
class Read:
    """One PDF after preprocessing, shared by both models."""

    name: str
    pages: list[str]  # reading order; a cover sheet is not among them
    ocr_pages: list[int] = field(default_factory=list)  # page numbers that were pictures of text
    cover: bool = False


def _not_words(text: str) -> bool:
    """A text layer of punctuation and digits: it looks like text and says nothing."""
    visible = [character for character in text if not character.isspace()]
    letters = sum(character.isalpha() for character in visible)
    return len(visible) >= 15 and letters < 20


def _ordered(page: object) -> str:
    return str(page.get_text(sort=True))  # type: ignore[attr-defined]


def _ocr(page: object) -> str:
    textpage = page.get_textpage_ocr(language="eng", dpi=150, full=True)  # type: ignore[attr-defined]
    return str(page.get_text(textpage=textpage, sort=True))  # type: ignore[attr-defined]


def _is_cover(text: str) -> bool:
    letters = sum(character.isalpha() for character in text)
    return bool(_COVER.search(text)) or letters < 40


def read_document(path: Path) -> Read:
    """The pages a model is shown: in reading order, with unreadable text read by OCR, and a
    cover sheet left out."""
    import pymupdf

    pages: list[str] = []
    ocr_pages: list[int] = []
    with pymupdf.open(path) as doc:
        for number, page in enumerate(doc, start=1):
            text = _ordered(page)
            if _not_words(text):
                try:
                    text = _ocr(page) or text
                except Exception:
                    pass  # the punctuation stays; the record still says OCR was needed
                ocr_pages.append(number)
            pages.append(" ".join(text.split()))
    cover = len(pages) > 1 and _is_cover(pages[0])
    if cover:
        pages = pages[1:]
    return Read(path.name, pages, ocr_pages, cover)


def prompt(document: Read, budget: int = 6000) -> str:
    """What a model is sent. The top of the first page and the bottom of the last are kept whole
    even when the rest is cut to `budget`."""
    top = document.pages[0][:500]
    bottom = document.pages[-1][-500:]
    kept = f"[top of the first page]\n{top}\n[bottom of the last page]\n{bottom}\n"
    body = "\n".join(document.pages)
    room = budget - len(kept)
    if room < 0:
        return kept[:budget]
    if len(body) > room:
        body = body[:room]
    return kept + body


def local_root(out: Path) -> Path:
    """The local model's folder, beside the one asked for: `prepared` and `prepared local`."""
    return out.with_name(out.name + " local")


def _pdfs(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf" and not path.name.startswith(".")
    )


def _copy(root: Path, source: Path) -> Path:
    """A copy filed as unrecognized, byte for byte. The source is only read."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    relative = _target(source.name, digest, None, "pdf")
    folder = root / DOCUMENTS / FORMAT_FOLDERS["pdf"] / relative.parent
    target = free_path(folder, relative.name, digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def prepare(folder: Path, out: Path, box: Optional[Path] = None) -> None:
    """File every PDF in `folder` into both trees. `box` is accepted and not written (T01: no
    model yet, so both copies wait in Unrecognized)."""
    del box  # read later, for the model Settings names; never written
    for source in _pdfs(folder):
        for root in (out, local_root(out)):
            _copy(root, source)
