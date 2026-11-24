"""Validating a processed PDF before it is accepted (ticket 20261124-07).

Each failure is made on purpose from a good file (a page dropped, resized, rotated, blanked,
moved; text lost; no text where OCR ran) and must fail the check that names it.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

import pymupdf
import pytest

from caixa.documents.pdf import ocr
from caixa.documents.pdf.inspect import inspect_pdf
from caixa.documents.pdf.validate import validate
from pdf_family import PdfFamily

TOOLS = ocr.tools()
needs_tools = pytest.mark.skipif(not TOOLS.ready, reason=f"OCR tools missing: {TOOLS.missing}")

STATEMENT = "2024-11 Banco Atlântico Checking Statement.pdf"


def _changed(source: Path, target: Path, change: Callable[[Any], None]) -> Path:
    doc = pymupdf.open(source)
    change(doc)
    doc.save(target)
    doc.close()
    return target


def _failed(result: Any) -> set[str]:
    return {check.name for check in result.checks if not check.passed}


def test_an_unchanged_copy_passes(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / STATEMENT
    copy = tmp_path / "copy.pdf"
    shutil.copyfile(source, copy)
    result = validate(source, copy, [])
    assert result.passed, [c for c in result.checks if not c.passed]
    names = {check.name for check in result.checks}
    assert {"exists", "opens", "unlocked", "structure", "pages", "sizes", "text", "pictures",
            "appearance"} <= names  # fmt: skip


@needs_tools
@pytest.mark.parametrize(
    "name",
    [
        "scan_00482.pdf",
        "download.pdf",
        "old_ocr_contract.pdf",
        "Check 1042 - Canalizações Rui - 450.00.pdf",
    ],
)
def test_every_ocrd_fixture_passes(pdf_family: PdfFamily, tmp_path: Path, name: str) -> None:
    source = pdf_family.root / name
    with pymupdf.open(source) as doc:
        inspection = [
            {"number": p.number, "page_class": p.page_class, "poor": p.poor, "text": p.text}
            for p in inspect_pdf(doc)
        ]
    outcome = ocr.ocr_document(source, tmp_path / "out.pdf", inspection, "eng")
    assert outcome.output is not None
    result = validate(source, outcome.output, outcome.settings["pages"])
    assert result.passed, [c for c in result.checks if not c.passed]


def test_an_empty_file_fails(pdf_family: PdfFamily, tmp_path: Path) -> None:
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    result = validate(pdf_family.root / STATEMENT, empty, [])
    assert not result.passed and "exists" in _failed(result)


def test_a_file_that_is_not_a_pdf_fails(pdf_family: PdfFamily, tmp_path: Path) -> None:
    false = tmp_path / "false.pdf"
    false.write_text("not a pdf")
    result = validate(pdf_family.root / STATEMENT, false, [])
    assert not result.passed and "opens" in _failed(result)


def test_a_missing_page_fails(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / STATEMENT
    short = _changed(source, tmp_path / "short.pdf", lambda doc: doc.delete_page(1))
    assert "pages" in _failed(validate(source, short, []))


def test_a_resized_page_fails(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / STATEMENT
    bigger = _changed(
        source,
        tmp_path / "bigger.pdf",
        lambda doc: doc[0].set_mediabox(pymupdf.Rect(0, 0, 612, 1008)),
    )
    assert "sizes" in _failed(validate(source, bigger, []))


def test_a_rotated_page_fails(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / STATEMENT
    turned = _changed(source, tmp_path / "turned.pdf", lambda doc: doc[1].set_rotation(90))
    assert "sizes" in _failed(validate(source, turned, []))


def test_a_page_drawn_over_fails_its_appearance(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / "scan_00482.pdf"

    def blank(doc: Any) -> None:
        doc[0].draw_rect(doc[0].rect, color=(1, 1, 1), fill=(1, 1, 1))

    blanked = _changed(source, tmp_path / "blanked.pdf", blank)
    assert "appearance" in _failed(validate(source, blanked, []))


def test_moved_pages_fail(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / STATEMENT
    moved = _changed(source, tmp_path / "moved.pdf", lambda doc: doc.move_page(1, 0))
    assert "text" in _failed(validate(source, moved, []))


def test_text_lost_from_a_digital_page_fails(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / STATEMENT
    flat = pymupdf.open()
    with pymupdf.open(source) as doc:
        for page in doc:
            picture = page.get_pixmap(dpi=150)
            new = flat.new_page(width=page.rect.width, height=page.rect.height)
            new.insert_image(new.rect, pixmap=picture)
    flat.save(tmp_path / "flat.pdf")
    failed = _failed(validate(source, tmp_path / "flat.pdf", []))
    assert "text" in failed


def test_no_text_where_ocr_ran_fails(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / "scan_00482.pdf"
    copy = tmp_path / "copy.pdf"
    shutil.copyfile(source, copy)
    assert "ocr_text" in _failed(validate(source, copy, [1]))


def test_lost_pictures_fail(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / "download.pdf"

    def strip(doc: Any) -> None:
        for xref, *_ in doc[1].get_images():
            doc[1].delete_image(xref)

    stripped = _changed(source, tmp_path / "stripped.pdf", strip)
    assert "pictures" in _failed(validate(source, stripped, []))


def test_structural_problems_are_reported(
    pdf_family: PdfFamily, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pikepdf = pytest.importorskip("pikepdf")
    monkeypatch.setattr(
        pikepdf.Pdf,
        "check_pdf_syntax",
        lambda self, progress=None: ["ERROR: object 7: invalid stream length"],
    )
    source = pdf_family.root / STATEMENT
    copy = tmp_path / "copy.pdf"
    shutil.copyfile(source, copy)
    result = validate(source, copy, [])
    assert "structure" in _failed(result)
    assert "invalid stream length" in next(c for c in result.checks if c.name == "structure").detail


def test_structural_warnings_are_noted_but_do_not_fail(
    pdf_family: PdfFamily, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pikepdf = pytest.importorskip("pikepdf")
    monkeypatch.setattr(
        pikepdf.Pdf, "check_pdf_syntax", lambda self, progress=None: ["WARNING: xref has a gap"]
    )
    source = pdf_family.root / STATEMENT
    result = validate(source, source, [])
    structure = next(c for c in result.checks if c.name == "structure")
    assert structure.passed and "xref has a gap" in structure.detail


def test_a_report_is_plain_values(pdf_family: PdfFamily, tmp_path: Path) -> None:
    source = pdf_family.root / STATEMENT
    report = validate(source, source, []).report()
    assert report["passed"] is True and isinstance(report["checks"], list)
    assert set(report["checks"][0]) == {"name", "passed", "detail"}
