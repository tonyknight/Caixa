"""A stand-in for a local model reading documents, for tests: it answers Caixa's classification
request from the PDF family's known answers, quoting its evidence from the pages it was sent.

`DocumentModel(family).respond` plugs into Chattr's `StubServer` (`server.respond = …`). It finds
the file name in the request, looks up that fixture, and answers in the classification schema:
type, category, title, author and date with quotes taken from the pages in the request (so they
verify), people, filename conflicts and a summary of 30–50 words.

Ways to misbehave, by file name: `not_json` answers prose, `schema` answers JSON that breaks the
schema, `twice` misbehaves only on the first attempt. (An HTTP error is the server's `status`.)
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Optional

from caixa.documents.evidence import text_dates
from pdf_family import PdfFamily

_PAGE = re.compile(r"^--- Page (\d+)[^\n]*---\n(.*?)(?=^--- Page |\Z)", re.M | re.S)
_MONTH_NAMES = {
    1: ("january", "janeiro"), 2: ("february", "fevereiro"), 3: ("march", "marco"),
    4: ("april", "abril"), 5: ("may", "maio"), 6: ("june", "junho"), 7: ("july", "julho"),
    8: ("august", "agosto"), 9: ("september", "setembro"), 10: ("october", "outubro"),
    11: ("november", "novembro"), 12: ("december", "dezembro"),
}  # fmt: skip


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join(
        "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().split()
    )


def pages_of(prompt: str) -> dict[int, str]:
    return {int(m.group(1)): m.group(2) for m in _PAGE.finditer(prompt)}


def _quote(pages: dict[int, str], wanted: str) -> tuple[Optional[str], Optional[int]]:
    """`wanted` as written on one of the pages (accents and case aside), and that page."""
    for number, text in sorted(pages.items()):
        plain = _plain(text)
        at = plain.find(_plain(wanted))
        if at >= 0:
            return wanted, number
    return None, None


def _date_quote(pages: dict[int, str], value: str) -> tuple[Optional[str], Optional[int]]:
    found = text_dates([(n, t, "pdf") for n, t in sorted(pages.items())])
    for one in found:
        if one.value == value:
            return one.text, one.page
    if len(value) == 4:
        for number, text in sorted(pages.items()):
            match = re.search(rf"[^\n]*\b{value}\b[^\n]*", text)
            if match:
                return match.group(0).strip(), number
    if len(value) == 7:
        month = _MONTH_NAMES[int(value[5:])]
        for number, text in sorted(pages.items()):
            plain = _plain(text)
            if any(name in plain for name in month) and value[:4] in plain:
                return value[:4], number
    return None, None


class DocumentModel:
    def __init__(self, family: PdfFamily, misbehave: Optional[dict[str, str]] = None) -> None:
        self.family = family
        self.misbehave = dict(misbehave or {})
        self.asked: dict[str, int] = {}

    def answer_for(self, name: str, pages: dict[int, str]) -> dict[str, Any]:
        try:
            fixture = self.family.get(name)
        except KeyError:
            fixture = None
        if fixture is None or fixture.type is None:
            return {
                "category": "other", "type": "other", "title": name.rsplit(".", 1)[0],
                "author": None, "date": None, "other_dates": [], "people": [],
                "organizations": [], "tags": [], "filename_conflicts": [],
                "summary": " ".join(["A document whose contents could not be told apart"] * 6),
            }  # fmt: skip
        author = None
        if fixture.author:
            quote, page = _quote(pages, fixture.author)
            author = {"name": fixture.author, "evidence": quote, "page": page}
        date = None
        if fixture.date:
            quote, page = _date_quote(pages, fixture.date)
            date = {
                "value": fixture.date, "precision": fixture.precision,
                "kind": fixture.date_kind, "evidence": quote, "page": page,
            }  # fmt: skip
        summary = (
            f"A {fixture.type} titled {fixture.title}"
            + (f" from {fixture.author}" if fixture.author else "")
            + (f", dated {fixture.date}" if fixture.date else "")
            + ". It is part of the family's papers, kept with the other documents of the same "
            "kind and year, and it names the people and the amounts that matter for it."
        )
        return {
            "category": fixture.category,
            "type": fixture.type,
            "title": fixture.title,
            "author": author,
            "date": date,
            "other_dates": [],
            "people": list(fixture.people),
            "organizations": (
                [fixture.author] if fixture.author and fixture.author not in fixture.people else []
            ),
            "tags": [],
            "filename_conflicts": list(fixture.conflicts),
            "summary": summary,
        }

    def respond(self, request: dict[str, Any]) -> dict[str, Any]:
        prompt = request["messages"][-1]["content"]
        first = next(m for m in request["messages"] if m["role"] == "user")["content"]
        found = re.search(r"^File name: (.+)$", first, re.M)
        name = found.group(1).strip() if found else ""
        self.asked[name] = self.asked.get(name, 0) + 1
        mode = self.misbehave.get(name, "")
        if mode == "twice" and self.asked[name] == 1:
            mode = "not_json"
        if mode == "not_json":
            return {"choices": [{"message": {"content": "This looks like a bank statement."}}]}
        if mode == "schema":
            return {"choices": [{"message": {"content": json.dumps({"type": 42})}}]}
        answer = self.answer_for(
            name, pages_of(first if prompt.startswith("That answer") else prompt)
        )
        return {"choices": [{"message": {"content": json.dumps(answer, ensure_ascii=False)}}]}


__all__ = ["DocumentModel", "pages_of"]
