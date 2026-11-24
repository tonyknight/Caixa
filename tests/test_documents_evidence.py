"""What filenames, PDF properties and dates in the text say, before any model reads a document
(ticket 20261124-09)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from caixa.documents.evidence import (
    provisional_facts,
    read_filename,
    read_properties,
    text_dates,
)
from pdf_family import PdfFamily

# --- Filenames -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "date", "precision"),
    [
        ("2024-11 Banco Atlântico Checking Statement.pdf", "2024-11", "month"),
        ("2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf", "2024-06-15", "day"),
        ("2023 Property Tax Bill.pdf", "2023", "year"),
        ("Wells Fargo Checking Statement November 2024.pdf", "2024-11", "month"),
        ("extrato novembro de 2024.pdf", "2024-11", "month"),
        ("Statement Nov 2024.pdf", "2024-11", "month"),
        ("2024_06_15 renewal.pdf", "2024-06-15", "day"),
        ("receipt 20240503.pdf", "2024-05-03", "day"),
        ("Exame Ana Costa 2020.pdf", "2020", "year"),
    ],
)
def test_a_date_in_a_filename(name: str, date: str, precision: str) -> None:
    found = read_filename(name)
    assert found.date is not None
    assert (found.date.value, found.date.precision) == (date, precision)


@pytest.mark.parametrize("name", ["Check 1042 - Canalizações Rui - 450.00.pdf", "Document1.pdf"])
def test_no_date_in_a_filename(name: str) -> None:
    assert read_filename(name).date is None


def test_a_cheque_filename() -> None:
    found = read_filename("Check 1042 - Canalizações Rui - 450.00.pdf")
    assert found.cheque_number == "1042" and found.amounts == ["450.00"]
    assert found.types == ["cheque"]
    assert found.author is None  # the parts after a dash name the payee, not who wrote it


def test_an_author_after_a_dash() -> None:
    found = read_filename("2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf")
    assert found.author == "Seguradora Horizonte" and found.types == ["insurance"]
    assert found.title == "Insurance Renewal"


def test_a_known_author_in_a_filename() -> None:
    found = read_filename(
        "2024-11 Banco Atlantico Checking Statement.pdf", known_authors=["Banco Atlântico"]
    )
    assert found.author == "Banco Atlântico" and found.title == "Checking Statement"
    assert found.types == ["statement"]


@pytest.mark.parametrize(
    "name",
    ["scan_00482.pdf", "Document1.pdf", "download.pdf", "IMG_20241115.pdf", "8f2a9c41d0.pdf",
     "00017.pdf", "untitled (2).pdf", "Scanned Document.pdf"],
)  # fmt: skip
def test_names_that_say_nothing(name: str) -> None:
    assert not read_filename(name).informative


def test_the_misleading_name_reads_as_it_is_written() -> None:
    found = read_filename("2022 Car Insurance.pdf")
    assert found.date is not None and found.date.value == "2022"
    assert found.types == ["insurance"] and found.informative


@pytest.mark.parametrize(
    ("name", "types"),
    [
        ("Fatura de água março.pdf", ["bill"]),
        ("recibo café.pdf", ["invoice"]),
        ("Escritura casa Braga.pdf", ["property_record"]),
        ("Carta do João.pdf", ["correspondence"]),
        ("IRS 2023 imposto.pdf", ["tax"]),
        ("contrato de arrendamento.pdf", ["agreement"]),
    ],
)
def test_type_words_in_both_languages(name: str, types: list[str]) -> None:
    assert read_filename(name).types == types


def test_every_fixture_filename_says_what_its_answers_say(pdf_family: PdfFamily) -> None:
    for fixture in pdf_family.documents:
        if fixture.kind in (
            "corrupted",
            "not_pdf",
            "duplicate",
            "same_text",
            "encrypted",
            "owner_password",
        ):
            continue
        found = read_filename(fixture.name)
        assert found.informative == fixture.filename_informative, fixture.name


# --- Properties ----------------------------------------------------------------------------------


def test_properties_that_mean_something_are_kept() -> None:
    found = read_properties(
        {"title": "Statement", "author": "Banco Atlântico", "creationDate": "D:20241130093000Z",
         "subject": "November", "keywords": "conta, extrato"}
    )  # fmt: skip
    assert found.title == "Statement" and found.author == "Banco Atlântico"
    assert found.created == "2024-11-30" and found.subject == "November"
    assert found.keywords == ["conta", "extrato"]


@pytest.mark.parametrize(
    "properties",
    [
        {"title": "Untitled", "author": "admin"},
        {"title": "Microsoft Word - carta.docx", "author": "Microsoft Office User"},
        {"title": "scan0001.pdf", "author": "ScanSnap Manager"},
        {"title": "   ", "author": "user"},
        {"title": "Document1", "author": "Adobe Acrobat"},
    ],
)
def test_placeholder_and_noise_properties_are_dropped(properties: dict[str, str]) -> None:
    found = read_properties(properties)
    assert found.title is None and found.author is None


def test_a_property_date_with_an_offset() -> None:
    assert read_properties({"modDate": "D:20230420101500+01'00'"}).modified == "2023-04-20"
    assert read_properties({"creationDate": "nonsense"}).created is None


# --- Dates in the text ---------------------------------------------------------------------------


def test_dates_written_in_the_text() -> None:
    pages = [
        (1, "Statement period: November 1, 2024 to November 30, 2024", "pdf"),
        (2, "Data de emissão: 12/03/2024. Porto, 2 de junho de 2019. Ref 2024-11-03", "ocr"),
    ]
    found = text_dates(pages)
    values = [(d.value, d.page, d.source) for d in found]
    assert ("2024-11-01", 1, "pdf") in values and ("2024-11-30", 1, "pdf") in values
    assert ("2024-03-12", 2, "ocr") in values  # day first
    assert ("2019-06-02", 2, "ocr") in values and ("2024-11-03", 2, "ocr") in values
    assert all(d.text for d in found)


def test_impossible_dates_are_not_dates() -> None:
    assert text_dates([(1, "Total 31/02/2024 and 45/13/2020", "pdf")]) == []


def test_at_most_twenty_dates() -> None:
    text = " ".join(f"2024-01-{day:02d}" for day in range(1, 31))
    assert len(text_dates([(1, text, "pdf")])) == 20


# --- What an import can file by ------------------------------------------------------------------


def test_the_statement_is_filed_by_its_filename_and_properties() -> None:
    facts = provisional_facts(
        read_filename("2024-11 Banco Atlântico Checking Statement.pdf"),
        read_properties({"title": "Statement", "author": "Banco Atlântico"}),
    )
    assert facts is not None
    assert (facts.date, facts.title, facts.author) == (
        "2024-11",
        "Checking Statement",
        "Banco Atlântico",
    )


def test_the_renewal_is_filed_by_its_filename() -> None:
    facts = provisional_facts(
        read_filename("2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf"),
        read_properties({"creator": "ScanSnap Manager"}),
    )
    assert facts is not None and facts.author == "Seguradora Horizonte"
    assert facts.date == "2024-06-15" and facts.title == "Insurance Renewal"


@pytest.mark.parametrize(
    ("name", "properties"),
    [
        ("2023 Property Tax Bill.pdf", {"title": "Untitled", "author": "admin"}),
        ("Check 1042 - Canalizações Rui - 450.00.pdf", {}),
        ("scan_00482.pdf", {}),
        ("2022 Car Insurance.pdf", {}),
    ],
)
def test_without_a_date_and_an_author_a_document_is_unrecognized(
    name: str, properties: dict[str, str]
) -> None:
    assert provisional_facts(read_filename(name), read_properties(properties)) is None


def test_a_title_falls_back_to_the_type() -> None:
    facts = provisional_facts(
        read_filename("2024-11 - Banco Atlântico - statement.pdf"),
        read_properties({}),
    )
    assert facts is not None and facts.title in ("statement", "Statement")


# --- In the import (T02) -------------------------------------------------------------------------


@pytest.fixture
def imported(pdf_family: PdfFamily, tmp_path: Path) -> Any:
    from caixa import settings
    from caixa.box import Box
    from caixa.collectors.pdfImport import PdfCollector

    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.ocr": False})  # quicker: OCR plays no part in this
    PdfCollector().run(box, source, {"workers": 1}, lambda step: None)
    return box, source


def _by_name(box: Any) -> dict[str, dict[str, Any]]:
    from caixa.documents import records

    with box.master() as master:
        return {
            d["original_filename"]: records.get_document(master, d["item_id"])
            for d in records.list_documents(master)
        }


def test_an_import_files_what_its_evidence_allows(imported: Any) -> None:
    box, _ = imported
    found = _by_name(box)
    statement = found["2024-11 Banco Atlântico Checking Statement.pdf"]
    assert statement["file_path"] == (
        "Documents/PDF/2024/Banco Atlântico/(2024-11) Checking Statement - Banco Atlântico.pdf"
    )
    assert (statement["date"], statement["date_precision"], statement["author"]) == (
        "2024-11", "month", "Banco Atlântico",
    )  # fmt: skip
    assert statement["title"] == "Checking Statement"
    renewal = found["2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf"]
    assert renewal["file_path"] == (
        "Documents/PDF/2024/Seguradora Horizonte/"
        "(2024-06-15) Insurance Renewal - Seguradora Horizonte.pdf"
    )
    for name in ("scan_00482.pdf", "2023 Property Tax Bill.pdf", "2022 Car Insurance.pdf"):
        assert found[name]["file_path"] == f"Documents/PDF/Unrecognized/{name}", name
        assert found[name]["date"] is None and found[name]["author"] is None


def test_every_fact_keeps_its_source(imported: Any) -> None:
    box, _ = imported
    found = _by_name(box)
    cheque = found["Check 1042 - Canalizações Rui - 450.00.pdf"]
    fields = {(f["field"], f["value"], f["source"]) for f in cheque["fields"]}
    assert ("cheque_number", "1042", "original_filename") in fields
    assert ("amount", "450.00", "original_filename") in fields
    statement = found["2024-11 Banco Atlântico Checking Statement.pdf"]
    by_field = {(f["field"], f["source"]): f for f in statement["fields"]}
    assert by_field[("date", "original_filename")]["evidence"] == "2024-11"
    assert by_field[("author", "pdf_metadata")]["value"] == "Banco Atlântico"
    assert by_field[("date", "original_filename")]["state"] == "applied"
    text_dates_found = [f for f in statement["fields"] if f["field"] == "date_in_text"]
    assert {"2024-11-01", "2024-11-30"} <= {f["value"] for f in text_dates_found}
    assert all(f["page"] for f in text_dates_found)
    tax = found["2023 Property Tax Bill.pdf"]
    assert not [
        f for f in tax["fields"] if f["source"] == "pdf_metadata" and f["field"] == "author"
    ]


def test_the_original_filename_stays_on_the_record(imported: Any) -> None:
    box, _ = imported
    statement = _by_name(box)["2024-11 Banco Atlântico Checking Statement.pdf"]
    assert statement["original_filename"] == "2024-11 Banco Atlântico Checking Statement.pdf"


def test_importing_again_adds_no_fields(imported: Any) -> None:
    from caixa.collectors.pdfImport import PdfCollector

    box, source = imported
    before = {name: len(doc["fields"]) for name, doc in _by_name(box).items()}
    PdfCollector().run(box, source, {"workers": 1}, lambda step: None)
    assert {name: len(doc["fields"]) for name, doc in _by_name(box).items()} == before
