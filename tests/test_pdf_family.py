"""The synthetic PDF family is what it claims to be (ticket 20261124-01).

Every later documents ticket tests against these files, so their own properties are checked here:
which pages carry text and which are only pictures, which text is invisible or broken, and that
every word the known answers place on a page is really there.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pymupdf
import pytest

from pdf_family import PASSWORD, PdfFamily, build_pdf_family, zip_family

STATEMENT_NAME = "2024-11 Banco Atlântico Checking Statement.pdf"

PRIVATE_USE = range(0xE000, 0xF900)
UNREADABLE = ("corrupted", "not_pdf")


def _text(path: Path, page: int) -> str:
    with pymupdf.open(path) as doc:
        return str(doc[page].get_text())


def test_every_fixture_has_its_pages(pdf_family: PdfFamily) -> None:
    assert len(pdf_family.documents) >= 12
    for fixture in pdf_family.documents:
        if fixture.kind in UNREADABLE:
            continue
        with pymupdf.open(pdf_family.root / fixture.path) as doc:
            if doc.needs_pass:
                doc.authenticate(PASSWORD)
            assert doc.page_count == len(fixture.pages), fixture.path


def test_scanned_pages_are_pictures_without_text(pdf_family: PdfFamily) -> None:
    scanned = [
        (f, i) for f in pdf_family.documents for i, k in enumerate(f.pages) if k == "needs_ocr"
    ]
    assert len(scanned) >= 3
    for fixture, index in scanned:
        with pymupdf.open(pdf_family.root / fixture.path) as doc:
            page = doc[index]
            assert page.get_text().strip() == "", fixture.path
            assert len(page.get_images()) == 1


def test_ocr_layers_are_invisible_text_over_a_picture(pdf_family: PdfFamily) -> None:
    layered = [
        (f, i) for f in pdf_family.documents for i, k in enumerate(f.pages) if k == "ocr_layer"
    ]
    assert len(layered) >= 2
    for fixture, index in layered:
        with pymupdf.open(pdf_family.root / fixture.path) as doc:
            page = doc[index]
            assert len(page.get_images()) == 1
            spans = [
                span
                for block in page.get_text("rawdict")["blocks"]
                for line in block.get("lines", [])
                for span in line["spans"]
            ]
            assert spans, fixture.path
            # Text in render mode 3 is drawn with nothing: a render without the picture is blank.
            assert "3 Tr" in page.read_contents().decode("latin-1")


def test_broken_text_extracts_to_the_private_use_area_but_looks_like_text(
    pdf_family: PdfFamily,
) -> None:
    broken = [
        (f, i) for f in pdf_family.documents for i, k in enumerate(f.pages) if k == "broken_text"
    ]
    assert broken
    for fixture, index in broken:
        text = _text(pdf_family.root / fixture.path, index).replace("\n", "").replace(" ", "")
        assert text and sum(ord(c) in PRIVATE_USE for c in text) / len(text) > 0.9
        with pymupdf.open(pdf_family.root / fixture.path) as doc:
            pixmap = doc[index].get_pixmap(dpi=40, colorspace=pymupdf.csGRAY)
            assert min(pixmap.samples) < 128  # something dark is drawn: the text shows


def test_rotated_and_odd_sized_pages(pdf_family: PdfFamily) -> None:
    receipt = pdf_family.get("receipt_rotated.pdf")
    with pymupdf.open(pdf_family.root / receipt.path) as doc:
        page = doc[0]
        assert page.rotation == 90
        assert page.mediabox.width < 300 < page.mediabox.height


def test_blank_pages_are_blank(pdf_family: PdfFamily) -> None:
    blank = [(f, i) for f in pdf_family.documents for i, k in enumerate(f.pages) if k == "blank"]
    assert blank
    for fixture, index in blank:
        assert _text(pdf_family.root / fixture.path, index).strip() == ""


def test_the_words_of_the_answers_are_on_their_pages(pdf_family: PdfFamily) -> None:
    for fixture in pdf_family.documents:
        for word, page in fixture.words.items():
            readable = fixture.pages[page] == "text" or (
                fixture.pages[page] == "ocr_layer" and fixture.kind != "poor_ocr"
            )
            if readable:
                assert word.casefold() in _text(pdf_family.root / fixture.path, page).casefold(), (
                    fixture.path,
                    word,
                )


def test_known_answers_are_written_beside_the_files(pdf_family: PdfFamily) -> None:
    answers = json.loads((pdf_family.root / "answers.json").read_text(encoding="utf-8"))
    assert {a["path"] for a in answers} == {f.path for f in pdf_family.documents}
    statement = next(a for a in answers if a["path"].endswith("Checking Statement.pdf"))
    assert statement["author"] == "Banco Atlântico"
    assert statement["date"] == "2024-11-30" and statement["precision"] == "day"
    assert statement["date_kind"] == "statement_end"


def test_the_misleading_filename_is_marked(pdf_family: PdfFamily) -> None:
    misleading = pdf_family.get("2022 Car Insurance.pdf")
    assert misleading.conflicts and misleading.type == "bill"


def test_two_builds_are_byte_identical(tmp_path: Path) -> None:
    first = build_pdf_family(tmp_path / "a")
    second = build_pdf_family(tmp_path / "b")
    for one in first.documents:
        if one.kind in ("encrypted", "owner_password"):
            continue
        a = (first.root / one.path).read_bytes()
        b = (second.root / one.path).read_bytes()
        assert a == b, one.path


@pytest.mark.parametrize("language", ["en", "pt"])
def test_both_languages_are_present(pdf_family: PdfFamily, language: str) -> None:
    assert any(f.language == language for f in pdf_family.documents)


# --- The awkward files (T02) -------------------------------------------------------------------


def test_a_password_protected_pdf_needs_its_password(pdf_family: PdfFamily) -> None:
    locked = pdf_family.get("extrato_protegido.pdf")
    with pymupdf.open(pdf_family.root / locked.path) as doc:
        assert doc.needs_pass
        assert doc.authenticate(PASSWORD)
        assert doc.page_count == len(locked.pages)


def test_an_owner_password_only_pdf_opens_without_one(pdf_family: PdfFamily) -> None:
    restricted = pdf_family.get("apolice_restrita.pdf")
    with pymupdf.open(pdf_family.root / restricted.path) as doc:
        assert not doc.needs_pass and doc.metadata["encryption"]
        assert "Seguradora Horizonte" in doc[0].get_text()


def test_a_damaged_pdf_opens_only_repaired_and_empty(pdf_family: PdfFamily) -> None:
    damaged = pdf_family.get("damaged_scan.pdf")
    assert damaged.kind == "corrupted"
    with pymupdf.open(pdf_family.root / damaged.path) as doc:
        assert doc.is_repaired  # MuPDF rebuilt it: what was on it is gone
        assert all(not p.get_text().strip() and not p.get_images() for p in doc)


def test_a_false_pdf_does_not_open(pdf_family: PdfFamily) -> None:
    false = pdf_family.get("not_really.pdf")
    assert false.kind == "not_pdf"
    with pytest.raises(pymupdf.FileDataError):
        pymupdf.open(pdf_family.root / false.path)


def test_an_exact_duplicate_lives_in_a_subfolder(pdf_family: PdfFamily) -> None:
    copy = pdf_family.get("statement copy.pdf")
    assert copy.path.startswith("Arquivo/2024/")
    original = pdf_family.root / STATEMENT_NAME
    assert (pdf_family.root / copy.path).read_bytes() == original.read_bytes()
    assert copy.duplicate_of == STATEMENT_NAME


def test_the_same_text_in_different_bytes(pdf_family: PdfFamily) -> None:
    again = pdf_family.get("Banco Atlântico November 2024 (1).pdf")
    original = pdf_family.root / STATEMENT_NAME
    assert (pdf_family.root / again.path).read_bytes() != original.read_bytes()
    with pymupdf.open(original) as a, pymupdf.open(pdf_family.root / again.path) as b:
        assert [p.get_text() for p in a] == [p.get_text() for p in b]
    assert again.same_text_as == STATEMENT_NAME


def test_a_file_that_is_not_a_pdf_is_beside_them(pdf_family: PdfFamily) -> None:
    assert (pdf_family.root / "Arquivo" / "notes.txt").is_file()


def test_the_family_zips_with_its_folders(pdf_family: PdfFamily, tmp_path: Path) -> None:
    archive = zip_family(pdf_family.root, tmp_path / "pdfs.zip")
    with zipfile.ZipFile(archive) as zipped:
        names = set(zipped.namelist())
    assert {f.path for f in pdf_family.documents} <= names
    assert "answers.json" not in names
