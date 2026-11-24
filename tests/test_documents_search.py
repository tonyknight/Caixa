"""Searching the words of documents (ticket 20261124-08): `caixa.documents.search`, the
`documents.search` method and `caixa documents search`."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa import cli
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import records
from caixa.documents.pdf import ocr
from caixa.documents.search import fts_query, search
from pdf_family import PdfFamily

OCR = ocr.tools().ready
needs_ocr = pytest.mark.skipif(not OCR, reason="OCR tools missing here")


@pytest.fixture(scope="module")
def box(pdf_family: PdfFamily, tmp_path_factory: pytest.TempPathFactory) -> Box:
    base = tmp_path_factory.mktemp("search")
    source = base / "pdfs"
    shutil.copytree(pdf_family.root, source)
    made = Box.create(base / "Box", name="Our box")
    PdfCollector().run(made, source, {"workers": 2}, lambda step: None)
    with made.master() as master:  # a few facts to filter by (enrichment gives them later)
        for listed in records.list_documents(master):
            name = listed["original_filename"]
            record = records.load_record(master, listed["item_id"])
            if name.startswith("2024-11 Banco"):
                record.type, record.author, record.date, record.date_precision = (
                    "statement", "Banco Atlântico", "2024-11-30", "day",
                )  # fmt: skip
                record.category = "financial"
            elif name == "scan_00482.pdf":
                record.type, record.author, record.date, record.date_precision = (
                    "bill", "Águas do Vale", "2024-03", "month",
                )  # fmt: skip
                record.category = "financial"
            elif name == "Exame Ana Costa 2020.pdf":
                record.type, record.date, record.date_precision = "medical", "2020", "year"
                record.category = "personal"
            else:
                continue
            records.save_document(master, record, None)
        statement = next(
            d
            for d in records.list_documents(master)
            if d["original_filename"].startswith("2024-11")
        )
        records.set_tags(master, statement["item_id"], ["banking"], "ai_inference")
    return made


def _hits(box: Box, query: str, **filters: Any) -> list[dict[str, Any]]:
    with box.master(read_only=True) as master:
        return search(master, query, **filters)


def _names(hits: list[dict[str, Any]]) -> set[str]:
    return {h["original_filename"] for h in hits}


# --- The query ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "query"),
    [
        ("statement", '"statement"'),
        ("Banco Atlântico", '"Banco" "Atlântico"'),
        ('"Checking Statement" 4821', '"Checking Statement" "4821"'),
        ("450.00", '"450.00"'),
        ("super*", '"super"*'),
        ('NOT OR AND "unclosed', '"NOT" "OR" "AND" "unclosed"'),
        ('say "hi"there', '"say" "hi" "there"'),
        ("   ", ""),
    ],
)
def test_what_is_typed_becomes_a_safe_query(typed: str, query: str) -> None:
    assert fts_query(typed) == query


# --- Searching ---------------------------------------------------------------------------------


@needs_ocr
@pytest.mark.parametrize(
    ("word", "name", "page"), [("77812", "scan_00482.pdf", 1), ("55031", "download.pdf", 2)]
)
def test_a_word_only_on_a_scan_is_found(box: Box, word: str, name: str, page: int) -> None:
    hits = _hits(box, word)
    hit = next(h for h in hits if h["original_filename"] == name)
    assert hit["page"] == page and hit["source"] == "ocr"


def test_a_phrase(box: Box) -> None:
    assert "2024-11 Banco Atlântico Checking Statement.pdf" in _names(
        _hits(box, '"Supermercado Sol"')
    )
    assert _hits(box, '"Sol Supermercado"') == []


def test_a_prefix(box: Box) -> None:
    assert "2024-11 Banco Atlântico Checking Statement.pdf" in _names(_hits(box, "Supermerc*"))


@pytest.mark.parametrize(
    ("typed", "name"),
    [
        ("1042", "2024-11 Banco Atlântico Checking Statement.pdf"),  # cheque 1042 on the statement
        ("450.00", "2024-11 Banco Atlântico Checking Statement.pdf"),
        ("4821", "2024-11 Banco Atlântico Checking Statement.pdf"),
        ("FT 2024/118", "download.pdf"),
        ("HZ-55120", "2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf"),
    ],
)
def test_numbers_amounts_and_references(box: Box, typed: str, name: str) -> None:
    assert name in _names(_hits(box, typed))


def test_accents_do_not_matter(box: Box) -> None:
    assert _names(_hits(box, "atlantico")) == _names(_hits(box, "Atlântico"))
    assert "Exame Ana Costa 2020.pdf" in _names(_hits(box, "clinica"))


def test_a_hit_says_where_it_is(box: Box) -> None:
    hit, *_ = _hits(box, '"Supermercado Sol"')
    assert hit["page"] == 2 and hit["source"] == "pdf"
    assert "[Supermercado Sol]" in hit["snippet"]  # a phrase is marked as one
    assert hit["file_path"].startswith("Documents/PDF/") and hit["item_id"].startswith("pdf:")
    assert hit["title"] == "Checking Statement" or hit["title"] is None


def test_the_best_hits_come_first(box: Box) -> None:
    hits = _hits(box, "Banco")
    assert hits == sorted(hits, key=lambda h: h["rank"])


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"type": "statement"}, {"2024-11 Banco Atlântico Checking Statement.pdf"}),
        (
            {"category": "financial", "author": "Banco Atlantico"},
            {"2024-11 Banco Atlântico Checking Statement.pdf"},
        ),
        ({"tag": "banking"}, {"2024-11 Banco Atlântico Checking Statement.pdf"}),
        (
            {"date_from": "2024-01-01", "date_to": "2024-12-31", "type": "statement"},
            {"2024-11 Banco Atlântico Checking Statement.pdf"},
        ),
        ({"date_from": "2025-01-01"}, set()),
    ],
)
def test_filters_narrow(box: Box, filters: dict[str, Any], expected: set[str]) -> None:
    assert _names(_hits(box, "Maria", **filters)) == expected


def test_filters_without_words_list_their_documents(box: Box) -> None:
    hits = _hits(box, "", date_from="2020", date_to="2020")
    assert _names(hits) == {"Exame Ana Costa 2020.pdf"} and hits[0]["page"] == 1


def test_a_partial_date_falls_in_its_range(box: Box) -> None:
    assert "scan_00482.pdf" in _names(_hits(box, "", date_from="2024-03-01", date_to="2024-03-31"))


def test_nothing_typed_and_no_filters_finds_nothing(box: Box) -> None:
    assert _hits(box, "  ") == []


def test_status_filters(box: Box) -> None:
    locked = _hits(box, "", status="needs_review")
    assert "extrato_protegido.pdf" in _names(locked)
    if OCR:
        assert "scan_00482.pdf" in _names(_hits(box, "", ocr_status="done"))


def test_the_limit(box: Box) -> None:
    assert len(_hits(box, "Maria", limit=2)) == 2


# --- Service and command line (T02) -----------------------------------------------------------


@pytest.fixture
def service(box: Box) -> Iterator[Any]:
    from caixa.service import Service

    made = Service(roots=[box.root.parent], read_only=True)
    made.box_open(str(box.root))
    yield made
    made.close()


def test_the_service_searches(service: Any) -> None:
    found = service.call("documents.search", {"query": "4821", "type": "statement"})
    assert found["query"] == '"4821"'
    assert {h["original_filename"] for h in found["hits"]} == {
        "2024-11 Banco Atlântico Checking Statement.pdf"
    }


def test_the_command_searches(box: Box, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["documents", "search", '"Supermercado Sol"', "--box", str(box.root)]) == 0
    out = capsys.readouterr().out
    assert "Checking Statement" in out and "page 2" in out and "[Supermercado Sol]" in out
    assert (
        cli.main(
            ["documents", "search", "4821", "--type", "statement", "--box", str(box.root), "--json"]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["hits"][0]["page"] == 1
    assert cli.main(["documents", "search", "nowhere-to-be-found", "--box", str(box.root)]) == 0
    assert "Nothing found" in capsys.readouterr().out
