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

from caixa.documents.archive import DOCUMENTS, FORMAT_FOLDERS, Facts, _target
from caixa.naming import free_path

_MISSING = object()
INSTRUCTION = (
    "You read one document and answer with one JSON object: "
    '{"kind", "author", "title", "date"}. '
    "The author is who issued or sent it, named on the page. Never use a software name, "
    "such as Brite:Bill, as the author. "
    "The date is the one that names the document: a bill's issue date, the end of a "
    "statement's period, a tax year, or the day a letter was written. "
    "Write it as YYYY, YYYY-MM or YYYY-MM-DD, and never invent a day. "
    "Use null for what the page does not say."
)

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


@dataclass
class Filed:
    name: str
    look: str  # "answer" when the first reply was enough, "bottom" when the second look was


@dataclass
class Run:
    files: list[Filed]
    apple: str  # "ran" or "not run"


def _software(name: str) -> bool:
    plain = " ".join(re.sub(r"[^a-z0-9]+", " ", name.lower()).split())
    return plain in {"brite", "brite bill", "pro api", "pro document"} or plain.startswith("brite ")


def _facts(answer: object) -> Facts:
    if not isinstance(answer, dict):
        return Facts()
    author = str(answer.get("author") or "").strip()
    if _software(author):
        author = ""
    return Facts(
        date=str(answer.get("date") or "").strip() or None,
        title=str(answer.get("title") or "").strip() or None,
        author=author or None,
    )


def _parse(raw: str) -> Facts:
    from caixa.documents.enrich import parse_answer

    try:
        return _facts(parse_answer(raw))
    except (ValueError, TypeError):
        return Facts()


def _ask(model: object, text: str) -> Facts:
    if model is None:
        return Facts()
    chat = getattr(model, "chat", None)
    if callable(chat):
        raw, _ = chat(
            [
                {"role": "system", "content": INSTRUCTION},
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        return _parse(str(raw))
    answer = model(INSTRUCTION + "\n" + text)  # type: ignore[operator]
    return _facts(answer)


def _question(document: Read, second: bool) -> str:
    if not second:
        return prompt(document)
    bottom = document.pages[-1][-800:]
    return f"second look\n[bottom of the last page]\n{bottom}\n"


def _decide(model: object, document: Read) -> tuple[Facts, str]:
    found = _ask(model, _question(document, False))
    if found.complete:
        return found, "answer"
    again = _ask(model, _question(document, True))
    if again.author and not found.author:
        found = Facts(
            date=found.date or again.date, title=found.title or again.title, author=again.author
        )
    if again.date and not found.date:
        found = Facts(date=again.date, title=found.title or again.title, author=found.author)
    if again.title and not found.title:
        found = Facts(date=found.date, title=again.title, author=found.author)
    return found, "bottom" if found.complete else "answer"


def _place(root: Path, source: Path, facts: Facts) -> None:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    relative = _target(source.name, digest, facts if facts.complete else None, "pdf")
    folder = root / DOCUMENTS / FORMAT_FOLDERS["pdf"] / relative.parent
    target = free_path(folder, relative.name, digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(source, target)


def _from_box(box: Optional[Path]) -> tuple[object, object, str]:
    """The two models Settings names. The box is only read."""
    local: object = None
    apple: object = None
    state = "not run"
    if box is not None:
        from caixa.box import Box
        from caixa.documents.enrich import EnrichUnavailable, provider
        from caixa import settings

        values = settings.load(Box.open(box))
        try:
            local, _ = provider(values)
        except EnrichUnavailable:
            local = None
    from caixa import apple_intelligence

    if apple_intelligence.available():
        apple = apple_intelligence.AppleIntelligence(1)
        state = "ran"
    return apple, local, state


def prepare(
    folder: Path,
    out: Path,
    box: Optional[Path] = None,
    *,
    apple: object = _MISSING,
    local: object = _MISSING,
    apple_available: Optional[bool] = None,
) -> Run:
    """File every PDF for both models. Pass `apple` and `local` (callables or chat clients) in
    tests; otherwise they are taken from `box`, which is not written."""
    if apple is _MISSING and local is _MISSING:
        apple, local, state = _from_box(box)
    else:
        state = (
            "ran"
            if apple_available or (apple_available is None and apple is not None)
            else "not run"
        )
        if apple_available is False:
            apple = None
    files: list[Filed] = []
    for source in _pdfs(folder):
        document = read_document(source)
        look = "answer"
        for model, root in ((apple, out), (local, local_root(out))):
            facts, which = _decide(model, document) if model is not None else (Facts(), "answer")
            if model is not None and which == "bottom":
                look = "bottom"
            _place(root, source, facts)
        files.append(Filed(source.name, look))
    return Run(files, state)
