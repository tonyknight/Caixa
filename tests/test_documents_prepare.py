"""caixa documents prepare: both models, beside the box (20261127-01). Synthetic files only."""

from __future__ import annotations

from pathlib import Path

import pytest
import pymupdf

from caixa import cli, settings
from caixa.box import Box
from caixa.documents import author_knowledge, prepare
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


def test_the_local_run_uses_the_endpoint_even_when_apple_is_chosen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(
        box,
        {
            "summaries.provider": "apple",
            "summaries.endpoint": "http://127.0.0.1:11434/v1",
            "summaries.model": "gemma",
        },
    )
    monkeypatch.setattr("caixa.apple_intelligence.available", lambda: True)
    made: dict[str, str] = {}

    class Endpoint:
        def __init__(
            self, address: str, name: str, api_key: str | None = None, **kwargs: object
        ) -> None:
            made["address"] = address
            made["name"] = name
            made["key"] = api_key or ""

    monkeypatch.setattr(prepare, "OpenAICompatibleTranslator", Endpoint)
    monkeypatch.setattr("caixa.translation.Keys.get", lambda self, endpoint: "secret-key")
    _apple, local, state, local_name = prepare.models_for(box.root)
    assert state == "ran"
    assert type(local) is Endpoint
    assert made == {
        "address": "http://127.0.0.1:11434/v1",
        "name": "gemma",
        "key": "secret-key",
    }
    assert local_name == "gemma"
    assert type(local).__name__ != "AppleIntelligence"


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


def test_the_report_diffs_the_trees_and_keeps_no_page_text(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    secret = "The kettle boiled at noon on the platform."
    agreed = folder / "Agreed.pdf"
    _bill(agreed)
    doc = pymupdf.open(agreed)
    doc[0].insert_text((72, 400), secret)
    doc.saveIncr()
    doc.close()
    split = folder / "Split.pdf"
    _bill(split)
    only = folder / "Only.pdf"
    _bill(only)

    def apple(text: str) -> dict[str, str]:
        if "Only.pdf" in text:
            return {"author": "", "title": "", "date": ""}
        author = "Energy Office" if "Agreed.pdf" in text else "North Power"
        return {"author": author, "title": "Bill", "date": "2024-03-12"}

    def local(text: str) -> dict[str, str]:
        if "Only.pdf" in text:
            return {"author": "Energy Office", "title": "Bill", "date": "2024-03-12"}
        author = "Energy Office" if "Agreed.pdf" in text else "South Power"
        return {"author": author, "title": "Bill", "date": "2024-03-12"}

    prepare.prepare(folder, tmp_path / "prepared", apple=apple, local=local)
    report = (tmp_path / "prepared" / "report.txt").read_text()
    assert "same place: 1" in report
    assert "different places: 1" in report
    assert "filed by one: 1" in report
    assert "North Power" in report and "South Power" in report
    assert "Energy Office" in report
    assert secret not in report
    assert "Apple Intelligence" in report and "local" in report
    events = (tmp_path / "prepared" / "report.jsonl").read_text().splitlines()
    assert events and '"same"' in events[0] or any('"same"' in line for line in events)


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


def test_a_rejected_author_is_not_filed(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    author_knowledge.save(box, author_knowledge.Knowledge(rejected=["City of Springfield"]))
    folder = tmp_path / "pdfs"
    folder.mkdir()
    _bill(folder / "Bill.pdf")
    prepare.prepare(
        folder,
        tmp_path / "prepared",
        box.root,
        apple=lambda text: {
            "kind": "bill",
            "author": "City of Springfield",
            "title": "Bill",
            "date": "2024-03-12",
        },
        local=None,
    )
    assert (tmp_path / "prepared/Documents/PDF/Unrecognized/Bill.pdf").is_file()
    assert not (tmp_path / "prepared/Documents/PDF/2024").exists()


def test_an_instead_files_under_the_kept_author_and_the_lists_are_shown(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    author_knowledge.save(
        box,
        author_knowledge.Knowledge(
            accepted=["PG&E"],
            rejected=["City of Springfield"],
            instead=[{"said": "City of Springfield", "use": "PG&E", "kind": "bill"}],
        ),
    )
    folder = tmp_path / "pdfs"
    folder.mkdir()
    _bill(folder / "Bill.pdf")
    seen: list[str] = []

    def model(text: str) -> dict[str, str]:
        seen.append(text)
        return {
            "kind": "bill",
            "author": "City of Springfield",
            "title": "Bill",
            "date": "2024-03-12",
        }

    prepare.prepare(folder, tmp_path / "prepared", box.root, apple=model, local=None)
    filed = tmp_path / "prepared/Documents/PDF/2024/PG&E/(2024-03-12) Bill - PG&E.pdf"
    assert filed.is_file()
    assert "PG&E" in seen[0] and "City of Springfield" in seen[0]


def test_a_box_without_the_file_prepares_as_before(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    folder = tmp_path / "pdfs"
    folder.mkdir()
    _bill(folder / "Bill.pdf")

    def model(text: str) -> dict[str, str]:
        assert "Accepted authors" not in text
        return {"author": "Energy Office", "title": "Bill", "date": "2024-03-12"}

    prepare.prepare(folder, tmp_path / "prepared", box.root, apple=model, local=None)
    assert (
        tmp_path / "prepared/Documents/PDF/2024/Energy Office/(2024-03-12) Bill - Energy Office.pdf"
    ).is_file()
