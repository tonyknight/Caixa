"""Synthetic PDFs named the organized way (D30, ticket 20261128-01), with their known answers.

Each file has the page it shows, what two stand-in models say about it (`apple` and `local`), and
where `caixa documents prepare --organized` should file it, and why. Everyone and everything named
is synthetic: the family of `pdf_family.py` and invented institutions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import pymupdf


@dataclass
class OrganizedFixture:
    name: str  # the file's name, as the owner wrote it
    lines: tuple[str, ...]  # its one page
    apple: dict[str, Any]  # what each stand-in model answers
    local: dict[str, Any]
    filed: str  # where it should go, relative to Documents/PDF/
    outcome: str  # kept | date replaced | no author | waiting | not organized
    tags: tuple[str, ...] = ()
    date_quote: Optional[str] = None  # the words on the page that give the model's date


def _answer(author: Optional[str], date: Optional[str], kind: str = "bill") -> dict[str, Any]:
    return {"kind": kind, "author": author, "title": "Document", "date": date}


FIXTURES: tuple[OrganizedFixture, ...] = (
    OrganizedFixture(
        "(2024-03-12) Water bill (Águas do Vale) [Utilities].pdf",
        ("Águas do Vale", "Fatura", "Data: 12 de março de 2024", "Total: 23,40 EUR"),
        _answer("Águas do Vale", "2024-03-12"),
        _answer("Aguas do Vale SA", "2024-03-12"),
        "2024/Águas do Vale/(2024-03-12) Water bill (Águas do Vale) [Utilities].pdf",
        "kept",
        ("Utilities",),
        "12 de março de 2024",
    ),
    OrganizedFixture(
        "(2024-02-30) Electricity bill (Energia do Norte) [Utilities].pdf",
        ("Energia do Norte", "Electricity bill", "Bill date: February 28, 2024"),
        _answer("Energia do Norte", "2024-02-28"),
        _answer("Energia do Norte", "2024-02-28"),
        "2024/Energia do Norte/(2024-02-28) Electricity bill (Energia do Norte) [Utilities].pdf",
        "date replaced",
        ("Utilities",),
        "February 28, 2024",
    ),
    OrganizedFixture(
        "(2023-02-30) Gas bill (Energia do Norte).pdf",
        ("Energia do Norte", "Gas bill", "Thank you for your custom"),
        _answer("Energia do Norte", None),
        _answer("Energia do Norte", None),
        "Unrecognized/(2023-02-30) Gas bill (Energia do Norte).pdf",
        "waiting",
    ),
    OrganizedFixture(
        "(2021-05-10) Insurance renewal (Seguradora Horizonte) [Insurance].pdf",
        ("Seguradora Horizonte", "Renewal notice", "Policy renewed on 2022-05-10"),
        _answer("Seguradora Horizonte", "2022-05-10", "insurance"),
        _answer("Seguradora Horizonte", "2022-05-10", "insurance"),
        "2022/Seguradora Horizonte/"
        "(2022-05-10) Insurance renewal (Seguradora Horizonte) [Insurance].pdf",
        "date replaced",
        ("Insurance",),
        "2022-05-10",
    ),
    OrganizedFixture(
        "(2024-04-02) Payment due (Águas do Vale).pdf",
        ("Águas do Vale", "Issued 12 March 2024", "Pay by 2024-04-02"),
        _answer("Águas do Vale", "2024-03-12"),
        _answer("Águas do Vale", "2024-03-12"),
        "2024/Águas do Vale/(2024-04-02) Payment due (Águas do Vale).pdf",
        "kept",  # the name's date is on the page, among its other dates
        (),
        "12 March 2024",
    ),
    OrganizedFixture(
        "(2024-03) Statement (Banco Atlântico) [Banking] [Joint].pdf",
        ("Banco Atlântico", "Statement period 01/03/2024 to 31/03/2024"),
        _answer("Banco Atlântico", "2024-03-31", "statement"),
        _answer("Banco Atlântico", "2024-03-31", "statement"),
        "2024/Banco Atlântico/(2024-03) Statement (Banco Atlântico) [Banking] [Joint].pdf",
        "kept",  # a coarser date than the page's is not a contradiction
        ("Banking", "Joint"),
        "31/03/2024",
    ),
    OrganizedFixture(
        "(2023-11-05) Letter from João [Family].pdf",
        ("Braga, 5 de novembro de 2023", "Querida Maria,", "Um abraço, João Costa"),
        _answer("João Costa", "2023-11-05", "correspondence"),
        _answer("joão  costa", "2023-11-05", "correspondence"),
        "2023/João Costa/(2023-11-05) Letter from João [Family].pdf",
        "kept",  # no author in the name: the one both models give chooses the folder
        ("Family",),
        "5 de novembro de 2023",
    ),
    OrganizedFixture(
        "(2020) Old receipt [Receipts].pdf",
        ("Receipt", "Thank you"),
        _answer("Café Central", "2020", "receipt"),
        _answer("Livraria Estrela", "2020", "receipt"),
        "Unrecognized/(2020) Old receipt [Receipts].pdf",
        "no author",  # the models do not agree
        ("Receipts",),
    ),
    OrganizedFixture(
        "scan_00482.pdf",
        ("Clínica Santa Luzia", "Consulta", "15 de junho de 2022"),
        _answer("Clínica Santa Luzia", "2022-06-15", "medical"),
        _answer("Clínica Santa Luzia", "2022-06-15", "medical"),
        "2022/Clínica Santa Luzia/(2022-06-15) Document - Clínica Santa Luzia.pdf",
        "not organized",  # prepared as any PDF (D28)
        (),
        "15 de junho de 2022",
    ),
)


@dataclass
class OrganizedFamily:
    root: Path
    fixtures: tuple[OrganizedFixture, ...] = FIXTURES
    asked: dict[str, list[str]] = field(default_factory=lambda: {"apple": [], "local": []})

    def get(self, name: str) -> OrganizedFixture:
        return next(fixture for fixture in self.fixtures if fixture.name == name)

    def model(self, which: str) -> Callable[[str], dict[str, Any]]:
        """A stand-in model answering from the known answers, by the file name it is shown."""

        def answer(text: str) -> dict[str, Any]:
            self.asked[which].append(text)
            name = next(
                line[len("File name: ") :] for line in text.splitlines()
                if line.startswith("File name: ")
            )  # fmt: skip
            return dict(getattr(self.get(name), which))

        return answer


#: The import's types and categories for the fixtures' kinds.
_TYPES = {"receipt": "other", "medical": "medical"}
_CATEGORIES = {"bill": "financial", "statement": "financial", "insurance": "financial",
               "correspondence": "correspondence", "medical": "personal", "other": "other"}  # fmt: skip
SUMMARY = (
    "A document of the synthetic family, read by a stand-in model for the tests of organized "
    "names in the import, written long enough to count as a summary of thirty words or more."
)


def respond(request: dict[str, Any]) -> dict[str, Any]:
    """A stand-in endpoint answering the import's schema (`caixa.documents.enrich`) from each
    fixture's `apple` answer: its author quoted when the page names it, its date with
    `date_quote`. A type's own fields are all left null."""
    import json

    asked = next(m["content"] for m in request["messages"] if m["role"] == "user")
    schema = (request.get("response_format") or {}).get("json_schema", {}).get("schema", {})
    if "Document type:" in asked or "already known to be" in request["messages"][0]["content"]:
        answer: dict[str, Any] = {name: None for name in schema.get("properties", {})}
    else:
        name = next(line[len("File name: "):] for line in asked.splitlines()
                    if line.startswith("File name: "))  # fmt: skip
        fixture = next(f for f in FIXTURES if f.name == name)
        said = fixture.apple
        page = " ".join(fixture.lines)
        kind = _TYPES.get(str(said.get("kind")), str(said.get("kind")))
        author = said.get("author")
        date = said.get("date")
        answer = {
            "category": _CATEGORIES.get(kind, "other"),
            "type": kind,
            "title": "Document",
            "author": {"name": author, "evidence": author if author and author in page else None,
                       "page": 1 if author and author in page else None} if author else None,
            "date": {"value": date, "precision": {4: "year", 7: "month"}.get(len(date), "day"),
                     "kind": "issue", "evidence": fixture.date_quote,
                     "page": 1 if fixture.date_quote else None} if date else None,
            "other_dates": [], "people": [], "organizations": [], "tags": ["model tag"],
            "summary": SUMMARY, "filename_conflicts": [],
        }  # fmt: skip
    return {"choices": [{"message": {"content": json.dumps(answer, ensure_ascii=False)}}]}


def build_organized(folder: Path) -> OrganizedFamily:
    """Write every organized-name fixture into `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    for fixture in FIXTURES:
        doc = pymupdf.open()
        page = doc.new_page()
        for index, line in enumerate(fixture.lines):
            page.insert_text((72, 72 + index * 18), line, fontname="helv")
        doc.set_metadata({"creationDate": "D:20250101000000Z", "modDate": "D:20250101000000Z"})
        doc.save(folder / fixture.name)
        doc.close()
    return OrganizedFamily(folder)


__all__ = ["FIXTURES", "OrganizedFamily", "OrganizedFixture", "build_organized", "respond"]
