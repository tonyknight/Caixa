"""OCR of the pages that need it (ticket 20261124-06), with OCRmyPDF and Tesseract.

The OCR tests run where both are installed (the development container has them) and say why they
are skipped elsewhere; the path without them is a requirement of its own and always runs.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import pymupdf
import pytest

from caixa.documents.pdf import ocr
from caixa.documents.pdf.inspect import inspect_pdf
from pdf_family import PdfFamily

TOOLS = ocr.tools()
needs_tools = pytest.mark.skipif(
    not TOOLS.ready, reason=f"OCR tools missing here: {', '.join(TOOLS.missing)}"
)


def _inspection(path: Path) -> list[dict[str, Any]]:
    with pymupdf.open(path) as doc:
        return [
            {
                "number": p.number,
                "page_class": p.page_class,
                "poor": p.poor,
                "needs_ocr": p.needs_ocr,
                "text": p.text,
            }
            for p in inspect_pdf(doc)
        ]


def _ocr(pdf_family: PdfFamily, tmp_path: Path, name: str) -> tuple[ocr.OcrOutcome, Path]:
    source = pdf_family.root / pdf_family.get(name).path
    outcome = ocr.ocr_document(source, tmp_path / "out.pdf", _inspection(source), "eng")
    return outcome, source


@needs_tools
@pytest.mark.parametrize(
    ("name", "word"),
    [("scan_00482.pdf", "77812"), ("Check 1042 - Canalizações Rui - 450.00.pdf", "1042")],
)
def test_a_scan_gets_a_text_layer_with_its_words(
    pdf_family: PdfFamily, tmp_path: Path, name: str, word: str
) -> None:
    outcome, source = _ocr(pdf_family, tmp_path, name)
    assert outcome.status == "done" and outcome.mode == "skip_text"
    assert outcome.output is not None and outcome.output.is_file()
    with pymupdf.open(outcome.output) as doc:
        assert word in doc[0].get_text()
        assert doc.page_count == 1
    assert word in outcome.texts[1]
    assert outcome.tool == "ocrmypdf" and outcome.versions["ocrmypdf"]
    assert outcome.settings["pages"] == [1] and outcome.settings["languages"] == "eng"


@needs_tools
def test_a_mixed_pdf_is_ocrd_only_where_it_is_scanned(
    pdf_family: PdfFamily, tmp_path: Path
) -> None:
    outcome, source = _ocr(pdf_family, tmp_path, "download.pdf")
    assert outcome.status == "done" and outcome.settings["pages"] == [2]
    assert set(outcome.texts) == {2} and "55031" in outcome.texts[2]
    with pymupdf.open(source) as before, pymupdf.open(outcome.output) as after:
        assert after[0].get_text() == before[0].get_text()  # the digital page keeps its text
        assert after[0].get_images() == []  # and is not turned into a picture
        assert len(after[1].get_images()) == 1


@needs_tools
def test_a_poor_ocr_layer_is_done_again(pdf_family: PdfFamily, tmp_path: Path) -> None:
    outcome, _ = _ocr(pdf_family, tmp_path, "old_ocr_contract.pdf")
    assert outcome.status == "done" and outcome.mode == "redo_ocr"
    assert outcome.settings["pages"] == [1, 2]
    assert "Rental Agreement" in outcome.texts[1] and "@" not in outcome.texts[1][:20]


@needs_tools
def test_a_page_with_broken_text_is_read_but_not_rewritten(
    pdf_family: PdfFamily, tmp_path: Path
) -> None:
    outcome, _ = _ocr(pdf_family, tmp_path, "extrato_marco.pdf")
    assert outcome.status == "done" and outcome.output is None  # the file stays as it is
    assert "4821" in outcome.texts[1]
    assert outcome.settings["read_only_pages"] == [1]


def test_a_digital_pdf_needs_nothing(pdf_family: PdfFamily, tmp_path: Path) -> None:
    outcome, _ = _ocr(pdf_family, tmp_path, "2024-11 Banco Atlântico Checking Statement.pdf")
    assert outcome.status == "not_needed" and outcome.output is None and outcome.texts == {}
    assert not (tmp_path / "out.pdf").exists()


def test_without_the_tools_the_pages_still_need_ocr(
    pdf_family: PdfFamily, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    found = ocr.tools()
    assert not found.ready and "tesseract" in found.missing
    assert "brew install ocrmypdf" in found.advice
    outcome, _ = _ocr(pdf_family, tmp_path, "scan_00482.pdf")
    assert outcome.status == "needs_ocr" and outcome.output is None
    assert "tesseract" in (outcome.error or "")


@needs_tools
def test_a_failure_leaves_no_output(
    pdf_family: PdfFamily, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ocrmypdf

    def broken(*args: Any, **kwargs: Any) -> None:
        Path(args[1]).write_bytes(b"half a file")
        raise RuntimeError("Tesseract stopped")

    monkeypatch.setattr(ocrmypdf, "ocr", broken)
    outcome, _ = _ocr(pdf_family, tmp_path, "scan_00482.pdf")
    assert outcome.status == "failed" and outcome.output is None
    assert "Tesseract stopped" in (outcome.error or "")
    assert not (tmp_path / "out.pdf").exists()


@needs_tools
def test_the_tools_report_their_versions_and_languages() -> None:
    assert TOOLS.ready and TOOLS.versions["ocrmypdf"] and TOOLS.versions["tesseract"]
    assert "eng" in TOOLS.languages


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- In the import (T02) ---------------------------------------------------------------------


@pytest.fixture
def family(pdf_family: PdfFamily, tmp_path: Path) -> Path:
    copy = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, copy)
    return copy


def _import(tmp_path: Path, family: Path, **settings: Any) -> Any:
    from caixa import settings as box_settings
    from caixa.box import Box
    from caixa.collectors.pdfImport import PdfCollector

    box = Box.create(tmp_path / "Box", name="Our box")
    if settings:
        box_settings.save(box, settings)
    result = PdfCollector().run(box, family, {"workers": 1}, lambda step: None)
    return box, result


def _document(box: Any, name: str) -> dict[str, Any]:
    from caixa.documents import records

    with box.master() as master:
        for listed in records.list_documents(master):
            if listed["original_filename"] == name:
                found = records.get_document(master, listed["item_id"])
                found["pages_rows"] = [
                    dict(r)
                    for r in master.connection.execute(
                        "SELECT page, text, source FROM document_pages WHERE item_id = ? "
                        "ORDER BY page",
                        (listed["item_id"],),
                    )
                ]
                return found
    raise KeyError(name)


@needs_tools
def test_an_import_files_ocrd_copies_of_scans(family: Path, tmp_path: Path) -> None:
    box, _ = _import(tmp_path, family)
    scan = _document(box, "scan_00482.pdf")
    assert scan["ocr_status"] == "done"
    assert scan["archived_sha256"] != scan["source_sha256"] == _sha(family / "scan_00482.pdf")
    assert _sha(box.root / scan["file_path"]) == scan["archived_sha256"]
    (page,) = scan["pages_rows"]
    assert page["source"] == "ocr" and "77812" in page["text"]
    run = next(r for r in scan["runs"] if r["stage"] == "ocr")
    assert run["tool"] == "ocrmypdf" and run["version"] and run["result"] == "done"
    mixed = _document(box, "download.pdf")
    assert [p["source"] for p in mixed["pages_rows"]] == ["pdf", "ocr"]
    broken = _document(box, "extrato_marco.pdf")
    assert broken["ocr_status"] == "done" and broken["archived_sha256"] == broken["source_sha256"]
    assert broken["pages_rows"][0]["source"] == "ocr" and "4821" in broken["pages_rows"][0]["text"]
    statement = _document(box, "2024-11 Banco Atlântico Checking Statement.pdf")
    assert statement["ocr_status"] == "not_needed"
    assert statement["archived_sha256"] == statement["source_sha256"]
    leftovers = list((box.caixa_dir / "work" / "documents").rglob("*.pdf"))
    assert [p for p in leftovers if "unpacked" not in p.parts] == []


def test_with_ocr_off_scans_still_need_it(family: Path, tmp_path: Path) -> None:
    box, result = _import(tmp_path, family, **{"documents.ocr": False})
    scan = _document(box, "scan_00482.pdf")
    assert scan["ocr_status"] == "needs_ocr" and scan["archived_sha256"] == scan["source_sha256"]
    assert scan["pages_rows"][0]["text"] == ""


def test_without_the_tools_the_import_still_files_everything(
    family: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    box, result = _import(tmp_path, family)
    assert result.inserted == 15
    scan = _document(box, "scan_00482.pdf")
    assert scan["ocr_status"] == "needs_ocr"
    run = next(r for r in scan["runs"] if r["stage"] == "ocr")
    assert run["result"] == "needs_ocr" and "tesseract" in (run["report"] or {}).get("error", "")


def test_the_doctor_names_the_ocr_programs() -> None:
    from caixa import diagnostics

    lines = "\n".join(diagnostics._programs())
    for name in ("ocrmypdf", "tesseract", "gs"):
        assert f"{name}:" in lines


# --- Reading order and the one rule, through an import (20261128-02, D31) -------------------------


def _words_picture(tmp_path: Path, words: str) -> Path:
    picture = tmp_path / "words.png"
    drawn = pymupdf.open()
    drawn.new_page().insert_text((72, 72), words, fontsize=14)
    drawn[0].get_pixmap(dpi=150).save(picture)
    drawn.close()
    return picture


def _mixed_family(tmp_path: Path) -> Path:
    """Three one-page PDFs: drawn bottom-first, a digits layer over a picture of words, and a short
    page of real words."""
    folder = tmp_path / "pdfs"
    folder.mkdir()
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 760), "Yours sincerely, the closing")
    page.insert_text((72, 72), "Valley Water, the letterhead")
    doc.save(folder / "Letter.pdf")
    doc.close()
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, filename=str(_words_picture(tmp_path, "Pacific Gas Electric")))
    page.insert_text((72, 400), ".... 12345 .... 99999 ....")
    doc.save(folder / "Bill.pdf")
    doc.close()
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Receipt")
    page.insert_text((72, 90), "Thank you")
    doc.save(folder / "Receipt.pdf")
    doc.close()
    return folder


def test_an_import_stores_reading_order_and_reads_a_digits_layer(tmp_path: Path) -> None:
    if not ocr.tools().ready:
        pytest.skip("OCR tools missing here")
    from caixa import settings
    from caixa.box import Box
    from caixa.collectors.pdfImport import PdfCollector

    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.enrich": False})
    PdfCollector().run(box, _mixed_family(tmp_path), {"workers": 1}, lambda step: None)
    with box.master() as master:
        rows = master.connection.execute(
            "SELECT d.original_filename, p.text, p.source, p.class FROM document_pages p "
            "JOIN documents d ON d.item_id = p.item_id"
        ).fetchall()
    pages = {str(name): (str(text), str(source), str(kind)) for name, text, source, kind in rows}
    letter = pages["Letter.pdf"][0]
    assert letter.index("letterhead") < letter.index("closing")
    text, source, kind = pages["Bill.pdf"]
    assert kind == "broken_text" and source == "ocr"
    assert "Pacific" in text or "Electric" in text
    assert pages["Receipt.pdf"][1:] == ("pdf", "text")
