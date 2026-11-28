"""caixa documents prepare: both models, beside the box (20261127-01). Synthetic files only."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from caixa import cli
from caixa.box import Box
from caixa.documents import prepare
from caixa.documents.pdf import ocr


def _pdf(path: Path, *lines: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + index * 16), line)
    doc.save(path)
    doc.close()


def test_prepare_copies_both_trees_and_leaves_the_source_and_the_box(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    pdf = folder / "Scan.pdf"
    _pdf(pdf, "Hello from the page")
    before = pdf.read_bytes()
    box = Box.create(tmp_path / "Box", name="Our box")
    settings = (box.caixa_dir / "box.yaml").read_bytes()
    out = tmp_path / "prepared"

    assert (
        cli.main(["documents", "prepare", str(folder), "--out", str(out), "--box", str(box.root)])
        == 0
    )

    assert pdf.read_bytes() == before
    assert (out / "Documents/PDF/Unrecognized/Scan.pdf").read_bytes() == before
    local = tmp_path / "prepared local"
    assert (local / "Documents/PDF/Unrecognized/Scan.pdf").read_bytes() == before
    assert not (out / ".caixa").exists()
    assert not (local / ".caixa").exists()
    assert (box.caixa_dir / "box.yaml").read_bytes() == settings


def test_a_page_drawn_bottom_first_is_read_top_first(tmp_path: Path) -> None:
    pdf = tmp_path / "Letter.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 700), "Sincerely, the closing line")  # drawn first, at the bottom
    page.insert_text((72, 72), "Letterhead Energy Office")  # drawn last, at the top
    doc.save(pdf)
    doc.close()
    seen = prepare.read_document(pdf)
    assert seen.pages[0].index("Letterhead Energy Office") < seen.pages[0].index("Sincerely")


def test_a_text_layer_that_is_not_words_is_read_by_ocr(tmp_path: Path) -> None:
    if "tesseract" not in ocr.tools().versions:
        import pytest

        pytest.skip("Tesseract is not installed")
    words = tmp_path / "words.png"
    drawn = pymupdf.open()
    page = drawn.new_page()
    page.insert_text((72, 72), "Pacific Gas Electric Company")
    page.get_pixmap(dpi=150).save(words)
    drawn.close()
    pdf = tmp_path / "Bill.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 400), ".... 12345 .... 99999 ....")
    page.insert_image(page.rect, filename=str(words))
    doc.save(pdf)
    doc.close()
    seen = prepare.read_document(pdf)
    assert 1 in seen.ocr_pages
    assert "Pacific" in seen.pages[0] or "Electric" in seen.pages[0]


def test_a_cover_sheet_is_skipped(tmp_path: Path) -> None:
    pdf = tmp_path / "Fax.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "FAX COVER")
    doc.new_page().insert_text((72, 72), "The letter itself starts here")
    doc.save(pdf)
    doc.close()
    seen = prepare.read_document(pdf)
    assert seen.cover
    assert seen.pages[0].startswith("The letter itself") or "The letter itself" in seen.pages[0]


def _bill(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Energy Office")
    page.insert_text((72, 100), "Bill issue date 12 March 2024")
    page.insert_text((72, 760), "Issued by Valley Water")
    doc.set_metadata({"author": "Brite:Bill"})
    doc.save(path)
    doc.close()


def test_the_sender_on_the_page_is_the_author_not_the_program(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    _bill(folder / "Bill.pdf")

    def follow(text: str) -> dict[str, str]:
        assert "software" in text.lower()
        return {"author": "Energy Office", "title": "Bill", "date": "2024-03-12"}

    prepare.prepare(folder, tmp_path / "prepared", apple=follow, local=follow)
    filed = (
        tmp_path / "prepared/Documents/PDF/2024/Energy Office/(2024-03-12) Bill - Energy Office.pdf"
    )
    assert filed.is_file()
    assert not list((tmp_path / "prepared/Documents/PDF").rglob("*Brite*"))


def test_an_answer_without_a_date_stays_unrecognized(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    _bill(folder / "Bill.pdf")
    prepare.prepare(
        folder,
        tmp_path / "prepared",
        apple=lambda text: {"author": "Energy Office", "title": "Bill", "date": ""},
        local=lambda text: {"author": "Energy Office", "title": "Bill", "date": ""},
    )
    assert (tmp_path / "prepared/Documents/PDF/Unrecognized/Bill.pdf").is_file()
    assert not (tmp_path / "prepared/Documents/PDF/2024").exists()


def test_two_models_file_under_different_authors(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    _bill(folder / "Bill.pdf")
    prepare.prepare(
        folder,
        tmp_path / "prepared",
        apple=lambda text: {"author": "Energy Office", "title": "Bill", "date": "2024-03-12"},
        local=lambda text: {"author": "Valley Water", "title": "Bill", "date": "2024-03-12"},
    )
    assert (
        tmp_path / "prepared/Documents/PDF/2024/Energy Office/(2024-03-12) Bill - Energy Office.pdf"
    ).is_file()
    assert (
        tmp_path
        / "prepared local/Documents/PDF/2024/Valley Water/(2024-03-12) Bill - Valley Water.pdf"
    ).is_file()


def test_a_missing_author_is_looked_for_on_the_other_region(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    _bill(folder / "Bill.pdf")

    def model(text: str) -> dict[str, str]:
        if "second look" in text:
            assert "Valley Water" in text
            return {"author": "Valley Water", "title": "Bill", "date": "2024-03-12"}
        return {"author": "", "title": "Bill", "date": "2024-03-12"}

    result = prepare.prepare(folder, tmp_path / "prepared", apple=model, local=model)
    assert (tmp_path / "prepared/Documents/PDF/2024/Valley Water").is_dir()
    assert result.files[0].look == "bottom"


def test_apple_not_running_still_files_the_local_copy(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    _bill(folder / "Bill.pdf")
    result = prepare.prepare(
        folder,
        tmp_path / "prepared",
        apple=None,
        local=lambda text: {"author": "Energy Office", "title": "Bill", "date": "2024-03-12"},
        apple_available=False,
    )
    assert result.apple == "not run"
    assert (
        tmp_path
        / "prepared local/Documents/PDF/2024/Energy Office/(2024-03-12) Bill - Energy Office.pdf"
    ).is_file()
    assert (tmp_path / "prepared/Documents/PDF/Unrecognized/Bill.pdf").is_file()


def test_the_top_and_the_bottom_survive_a_short_cut(tmp_path: Path) -> None:
    pdf = tmp_path / "Long.pdf"
    doc = pymupdf.open()
    first = doc.new_page()
    first.insert_text((72, 72), "Letterhead Energy Office")
    first.insert_text((72, 200), "body " * 400)
    last = doc.new_page()
    last.insert_text((72, 200), "middle " * 400)
    last.insert_text((72, 760), "Sincerely the closing line")
    doc.save(pdf)
    doc.close()
    seen = prepare.read_document(pdf)
    short = prepare.prompt(seen, budget=500)
    assert "Letterhead Energy Office" in short
    assert "Sincerely the closing line" in short
