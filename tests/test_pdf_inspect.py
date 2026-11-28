"""Inspecting PDFs page by page (ticket 20261124-05): which pages have usable text, which are
pictures that need OCR, which carry an OCR layer (good or poor), whose text is broken, and which
are blank."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from caixa.documents.pdf.inspect import classify, inspect_pdf, measure, text_hash
from pdf_family import PASSWORD, PdfFamily

SKIPPED = ("corrupted", "not_pdf")


def _readable(pdf_family: PdfFamily) -> list[Any]:
    return [f for f in pdf_family.documents if f.kind not in SKIPPED]


def test_every_page_gets_the_class_its_answers_name(pdf_family: PdfFamily) -> None:
    for fixture in _readable(pdf_family):
        with pymupdf.open(pdf_family.root / fixture.path) as doc:
            if doc.needs_pass:
                doc.authenticate(PASSWORD)
            found = tuple(page.page_class for page in inspect_pdf(doc))
        assert found == fixture.pages, fixture.path


def test_a_poor_ocr_layer_is_marked_poor(pdf_family: PdfFamily) -> None:
    for name, poor in (
        ("old_ocr_contract.pdf", True),
        ("2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf", False),
    ):
        with pymupdf.open(pdf_family.root / pdf_family.get(name).path) as doc:
            pages = inspect_pdf(doc)
        assert all(page.poor is poor for page in pages), name


def test_the_measures_of_a_digital_page(pdf_family: PdfFamily) -> None:
    fixture = pdf_family.get("2024-11 Banco Atlântico Checking Statement.pdf")
    with pymupdf.open(pdf_family.root / fixture.path) as doc:
        measured = measure(doc[0])
    assert measured.characters > 100 and measured.bad_share == 0
    assert measured.word_share > 0.6 and measured.invisible_share == 0
    assert measured.image_cover == 0


def test_the_measures_of_a_scanned_page(pdf_family: PdfFamily) -> None:
    with pymupdf.open(pdf_family.root / "scan_00482.pdf") as doc:
        measured = measure(doc[0])
    assert measured.characters == 0 and measured.image_cover > 0.95


def test_broken_text_is_mostly_bad_characters(pdf_family: PdfFamily) -> None:
    with pymupdf.open(pdf_family.root / "extrato_marco.pdf") as doc:
        measured = measure(doc[0])
    assert measured.bad_share > 0.9 and classify(measured) == ("broken_text", False)


def test_an_inspection_carries_the_page_text(pdf_family: PdfFamily) -> None:
    with pymupdf.open(pdf_family.root / "download.pdf") as doc:
        first, second = inspect_pdf(doc)
    assert "FT 2024/118" in first.text and second.text == ""
    assert first.number == 1 and second.number == 2
    assert first.quality()["characters"] == first.measures.characters


def test_garbled_ascii_reads_as_broken_text() -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    garbage = "x#9 q@ zz+ 7&k ^^v %$ ##q pl@ 0x0x ~~~ qqq ;;; " * 4
    page.insert_text((60, 80), garbage[:90], fontsize=10)
    page.insert_text((60, 100), garbage[90:180], fontsize=10)
    (inspected,) = inspect_pdf(doc)
    assert inspected.page_class == "broken_text"


def test_the_text_hash_ignores_spacing_and_case() -> None:
    assert text_hash(["Banco  Atlântico\n", "Conta 4821"]) == text_hash(
        ["banco atlântico conta", "4821"]
    )
    assert text_hash(["Banco"]) != text_hash(["Banca"])
    assert text_hash(["", "  \n"]) is None


# --- In the import (T02) ---------------------------------------------------------------------


@pytest.fixture
def imported(pdf_family: PdfFamily, tmp_path: Path) -> dict[str, Any]:
    from caixa.box import Box
    from caixa.collectors.pdfImport import PdfCollector
    from caixa.documents import records

    from caixa import settings

    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.ocr": False})  # what inspection alone decides
    PdfCollector().run(box, source, {}, lambda step: None)
    with box.master() as master:
        found = {
            d["original_filename"]: records.get_document(master, d["item_id"])
            for d in records.list_documents(master)
        }
        pages = {
            name: [
                dict(r)
                for r in master.connection.execute(
                    "SELECT page, text, source, class, quality FROM document_pages "
                    "WHERE item_id = ? ORDER BY page",
                    (doc["item_id"],),
                )
            ]
            for name, doc in found.items()
        }
    return {"documents": found, "pages": pages}


def test_imported_pages_keep_their_text_and_class(imported: dict[str, Any]) -> None:
    statement = imported["pages"]["2024-11 Banco Atlântico Checking Statement.pdf"]
    assert [p["class"] for p in statement] == ["text", "text"]
    assert "Supermercado Sol" in statement[1]["text"] and statement[1]["source"] == "pdf"
    assert '"characters"' in statement[0]["quality"]
    assert [p["class"] for p in imported["pages"]["download.pdf"]] == ["text", "needs_ocr"]


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("scan_00482.pdf", "needs_ocr"),
        ("download.pdf", "needs_ocr"),
        ("extrato_marco.pdf", "needs_ocr"),
        ("old_ocr_contract.pdf", "needs_ocr"),
        ("2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf", "not_needed"),
        ("2024-11 Banco Atlântico Checking Statement.pdf", "not_needed"),
        ("receipt_rotated.pdf", "not_needed"),
    ],
)
def test_the_ocr_status_says_what_needs_ocr(
    imported: dict[str, Any], name: str, status: str
) -> None:
    assert imported["documents"][name]["ocr_status"] == status


def test_the_same_text_in_another_file_is_a_probable_duplicate(imported: dict[str, Any]) -> None:
    again = imported["documents"]["Banco Atlântico November 2024 (1).pdf"]
    original = imported["documents"]["2024-11 Banco Atlântico Checking Statement.pdf"]
    assert (
        again["review"] == ["probable_duplicate"] and again["processing_status"] == "needs_review"
    )
    assert original["review"] == [] and again["text_hash"] == original["text_hash"]


def test_documents_without_text_are_not_duplicates_of_each_other(imported: dict[str, Any]) -> None:
    for name in ("scan_00482.pdf", "Check 1042 - Canalizações Rui - 450.00.pdf"):
        assert imported["documents"][name]["text_hash"] is None
        assert "probable_duplicate" not in imported["documents"][name]["review"]


def test_the_preview_counts_pages_that_may_need_ocr(pdf_family: PdfFamily, tmp_path: Path) -> None:
    from caixa.collectors.pdfImport import PdfCollector

    preview = PdfCollector().preview(pdf_family.root, {}, None)
    # scan, cheque, the mixed file's receipt, the broken statement, the poor contract's two pages
    assert any(w.startswith("6 pages may need OCR") for w in preview.warnings), preview.warnings


# --- Reading order and one unreadable-text rule (20261128-02, D31) --------------------------------


def _one_page(*lines: tuple[float, str], render_mode: int = 0) -> Any:
    doc = pymupdf.open()
    page = doc.new_page()
    for y, text in lines:
        page.insert_text((72, y), text, fontsize=11, render_mode=render_mode)
    return doc


def test_a_page_drawn_bottom_first_is_stored_top_first() -> None:
    doc = _one_page((760, "Yours sincerely, the closing"), (72, "Valley Water, the letterhead"))
    (inspected,) = inspect_pdf(doc)
    assert inspected.text.index("letterhead") < inspected.text.index("closing")


def test_a_layer_of_digits_and_punctuation_is_broken_text() -> None:
    doc = _one_page((72, ".... 12345 .... 99999 ...."), (90, "## 0042 // 7731 ::"))
    (inspected,) = inspect_pdf(doc)
    assert inspected.page_class == "broken_text"
    assert inspected.measures.letter_share < 0.25


def test_a_short_page_of_words_is_text() -> None:
    doc = _one_page((72, "Receipt"), (90, "Thank you"))
    (inspected,) = inspect_pdf(doc)
    assert inspected.page_class == "text" and not inspected.needs_ocr


def test_a_short_page_of_words_and_numbers_is_text() -> None:
    doc = _one_page((72, "Total 23,40 EUR"), (90, "Paid 12/03/2024"))
    (inspected,) = inspect_pdf(doc)
    assert inspected.page_class == "text"


def test_an_ocr_layer_of_digits_stays_an_ocr_layer() -> None:
    doc = _one_page((72, "0042 7731 99999 12345 0000"), render_mode=3)
    page = doc[0]
    page.insert_image(
        page.rect, pixmap=pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), 0)
    )
    (inspected,) = inspect_pdf(doc)
    assert inspected.page_class == "ocr_layer"
