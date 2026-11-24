"""The document pages: one page of cards for each year and author, and one for the documents
waiting in `Unrecognized/`, drawn by Caixa with its own templates on Chattr's base (the same Nord
look, light and dark).

    Documents/PDF/<YYYY>/<Author>/<Author>.html        that author's documents of that year
    Documents/PDF/Unrecognized/Unrecognized.html       those whose author or date is not known yet

A page sits beside its documents, so every link is relative and the pages work opened from disk.
Each card shows what is known about one document (title, date at its precision, author, type and
category, tags, its name in the box and the one it came with, the summary marked as a model's, and
how it was read and checked) and **Open**, which shows the PDF over the page (`document.js`), or
links to it without scripts.

`draw_documents` writes only the pages whose content changed, removes the pages that no longer have
documents, and remembers what it wrote (`.caixa/documents-pages.json`) so reset and undo find them.
"""

from __future__ import annotations

import calendar
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Optional
from urllib.parse import quote

from caixa.box import Box
from caixa.documents import records
from caixa.documents.archive import DOCUMENTS, UNRECOGNIZED
from caixa.documents.evidence import TYPE_LABELS

TEMPLATES = Path(__file__).resolve().parent / "templates"
RECORD = "documents-pages.json"

CATEGORY_LABELS = {
    "financial": "Financial", "legal": "Legal", "personal": "Personal",
    "correspondence": "Correspondence", "business": "Business", "other": "Other",
}  # fmt: skip
#: Why a document waits for review, in words.
REASONS = {
    "locked": "Locked with a password",
    "probable_duplicate": "Probably the same as another document",
    "ocr_failed": "OCR failed: kept as it came",
    "conflict:date": "The file name says another year or date",
    "conflict:type": "The file name says another kind of document",
    "conflict:author": "The file name names another author",
    "no_date": "No date",
    "no_author": "No author",
    "no_title": "No title",
    "no_type": "Not known what it is",
    "unverified_date": "Its date was not found on its page",
    "unverified_author": "Its author was not found in its text",
    "ai_unusable": "The model's reading could not be used",
}
OCR_WORDS = {
    "done": "Text read by OCR",
    "partial": "Text partly read by OCR",
    "needs_ocr": "Scanned: not searchable yet",
    "failed": "OCR failed",
}
AI_WORDS = {
    "pending": "Not read by a model yet",
    "processing": "Being read by a model",
    "failed": "The model could not read it",
}


@dataclass
class Drawn:
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    pages: int = 0


def _environment() -> Any:
    import chattr
    from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape

    chattrs = Path(chattr.__file__).resolve().parent / "templates"
    return Environment(
        loader=ChoiceLoader([FileSystemLoader(str(TEMPLATES)), FileSystemLoader(str(chattrs))]),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=False,
    )


def _when(date: Optional[str]) -> tuple[Optional[str], str]:
    """(an ISO date for `<time>`, the date as a person reads it, at its precision)."""
    if not date:
        return None, "Undated"
    parts = date.split("-")
    if len(parts) == 3:
        return date, f"{int(parts[2])} {calendar.month_name[int(parts[1])]} {parts[0]}"
    if len(parts) == 2:
        return f"{date}-01", f"{calendar.month_name[int(parts[1])]} {parts[0]}"
    return f"{date}-01-01", date


def _statuses(document: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    if document["ocr_status"] in OCR_WORDS:
        found.append(
            {
                "text": OCR_WORDS[document["ocr_status"]],
                "attention": document["ocr_status"] in ("needs_ocr", "failed"),
            }
        )
    if document["validation_status"] == "unchanged_copy":
        found.append({"text": "Kept as it came: OCR's copy failed its checks", "attention": True})
    if document["ai_status"] in AI_WORDS:
        found.append(
            {
                "text": AI_WORDS[document["ai_status"]],
                "attention": document["ai_status"] == "failed",
            }
        )
    for reason in document["review"]:
        found.append({"text": REASONS.get(reason, reason), "attention": True})
    return found


def card(
    document: dict[str, Any],
    tags: list[str],
    page_dir: PurePosixPath,
    known: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """What one card shows (paths relative to the page's folder); `known` is what the owner can
    choose from when correcting it (`caixa.documents.corrections.candidates`)."""
    path = PurePosixPath(document["file_path"])
    iso, when = _when(document["date"])
    href = quote(os.path.relpath(path, page_dir).replace(os.sep, "/"), safe="/()")
    pages = document.get("pages") or 0
    return {
        "id": str(document["item_id"]).split(":", 1)[-1][:16],
        "title": document["title"] or path.stem,
        "iso": iso,
        "when": when,
        "author": document["author"],
        "type": TYPE_LABELS.get(
            document["type"] or "", (document["type"] or "").capitalize() or None
        ),
        "category": CATEGORY_LABELS.get(document["category"] or ""),
        "pages": f"{pages} page{'' if pages == 1 else 's'}" if pages else "",
        "tags": tags,
        "summary": document["summary"],
        "model": document["summary_model"] or "a model",
        "file": path.name,
        "original": document["original_filename"],
        "statuses": _statuses(document),
        "href": href,
        "item": document["item_id"],
        "candidates": json.dumps(
            {
                name: [{"value": c["value"], "label": c["label"]} for c in values[:8]]
                for name, values in (known or {}).items()
                if values
            },
            ensure_ascii=False,
        ),
    }


def _record(box: Box) -> list[str]:
    try:
        found = json.loads((box.caixa_dir / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [p for p in found if isinstance(p, str)] if isinstance(found, list) else []


def _tidy(box: Box, folder: Path) -> None:
    stop = box.root / DOCUMENTS
    while folder != stop and folder.is_relative_to(stop):
        try:
            folder.rmdir()
        except OSError:
            return
        folder = folder.parent


def draw_documents(box: Box) -> Drawn:
    """Draw every document page that changed, remove those no longer needed (see the module)."""
    from caixa.documents.corrections import candidates
    from caixa.documents.enrich import TYPES

    with box.master(read_only=True) as master:
        documents = records.list_documents(master)
        known = {d["item_id"]: candidates(master, d["item_id"]) for d in documents}
        tags: dict[str, list[str]] = defaultdict(list)
        for item_id, tag in master.connection.execute(
            "SELECT item_id, tag FROM document_tags ORDER BY tag"
        ):
            tags[str(item_id)].append(str(tag))
    groups: dict[PurePosixPath, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        folder = PurePosixPath(document["file_path"]).parent
        if folder.parts[:1] == (DOCUMENTS,):
            groups[folder].append(document)
    environment = _environment()
    template = environment.get_template("author.html")
    css = (TEMPLATES / "document.css").read_text(encoding="utf-8")
    drawn = Drawn()
    wanted: list[str] = []
    for folder, members in sorted(groups.items()):
        members.sort(key=lambda d: (d["date"] is None, d["date"] or "", d["title"] or ""))
        unrecognized = folder.name == UNRECOGNIZED
        page = folder / f"{folder.name}.html"
        year = folder.parent.name if not unrecognized else ""
        heading = "Unrecognized documents" if unrecognized else folder.name
        title = heading if unrecognized else f"{folder.name}, {year}"
        dated = [d["date"] for d in members if d["date"]]
        span = ""
        if not unrecognized and dated:
            first, last = _when(min(dated))[1], _when(max(dated))[1]
            span = first if first == last else f"from {first} to {last}"
        html = template.render(
            title=title,
            heading=heading if unrecognized else f"{folder.name} · {year}",
            count=f"{len(members)} document{'' if len(members) == 1 else 's'}",
            span=span,
            home=quote(os.path.relpath("index.html", folder).replace(os.sep, "/"), safe="/"),
            cards=[
                card(d, tags.get(d["item_id"], []), folder, known.get(d["item_id"]))
                for d in members
            ],
            overlay_css=css,
            unrecognized=unrecognized,
            types=[
                {"value": t, "label": TYPE_LABELS.get(t, t.replace("_", " ").capitalize())}
                for t in TYPES
            ],
        )
        target = box.root / page
        wanted.append(page.as_posix())
        drawn.pages += 1
        if target.is_file() and target.read_text(encoding="utf-8") == html:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        part.write_text(html, encoding="utf-8")
        part.replace(target)
        drawn.written.append(page.as_posix())
    if documents:  # the view of them all, Documents/PDF/PDF.html
        from caixa.documents.view import VIEW, view_context

        html = environment.get_template("documents.html").render(
            overlay_css=css, **view_context(documents, tags)
        )
        wanted.append(VIEW)
        drawn.pages += 1
        target = box.root / VIEW
        if not (target.is_file() and target.read_text(encoding="utf-8") == html):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html, encoding="utf-8")
            drawn.written.append(VIEW)
        index = box.root / "index.html"
        if not index.exists() and not (box.caixa_dir / "pages.json").exists():
            # no conversations yet, so Chattr has drawn no index: a small one leads to the documents
            index.write_text(
                environment.get_template("box-index.html").render(
                    title=box.name, view=VIEW, count=len(documents)
                ),
                encoding="utf-8",
            )
    for old in _record(box):
        if old not in wanted:
            gone = box.root / old
            if gone.is_file():
                gone.unlink()
                _tidy(box, gone.parent)
            drawn.removed.append(old)
    (box.caixa_dir / RECORD).write_text(
        json.dumps(sorted(wanted), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return drawn


__all__ = ["Drawn", "RECORD", "card", "draw_documents"]
