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


# --- Organized file names (20261128-01, D30) ------------------------------------------------------

import json  # noqa: E402

from organized_family import FIXTURES, OrganizedFamily, build_organized  # noqa: E402


@pytest.fixture
def organized(tmp_path: Path) -> OrganizedFamily:
    return build_organized(tmp_path / "organized")


def _organized_run(family: OrganizedFamily, tmp_path: Path, box: Path | None = None) -> None:
    prepare.prepare(family.root, tmp_path / "prepared", box, apple=family.model("apple"),
                    local=family.model("local"), organized=True)  # fmt: skip


def _records(out: Path) -> dict[str, dict]:
    lines = (out / "report.jsonl").read_text(encoding="utf-8").splitlines()
    return {r["name"]: r for r in map(json.loads, lines) if r["event"] == "diff"}


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
def test_each_organized_name_is_filed_as_its_known_answer(
    organized: OrganizedFamily, tmp_path: Path, fixture: object
) -> None:
    _organized_run(organized, tmp_path)
    for root in (tmp_path / "prepared", tmp_path / "prepared local"):
        assert (root / "Documents/PDF" / fixture.filed).is_file(), root  # type: ignore[attr-defined]
    record = _records(tmp_path / "prepared")[fixture.name]  # type: ignore[attr-defined]
    assert record["organized"] == fixture.outcome  # type: ignore[attr-defined]
    assert record.get("tags", []) == list(fixture.tags)  # type: ignore[attr-defined]


def test_a_replaced_date_says_from_to_and_why(organized: OrganizedFamily, tmp_path: Path) -> None:
    _organized_run(organized, tmp_path)
    records = _records(tmp_path / "prepared")
    impossible = records["(2024-02-30) Electricity bill (Energia do Norte) [Utilities].pdf"]
    assert (impossible["from"], impossible["to"]) == ("2024-02-30", "2024-02-28")
    assert "impossible" in impossible["why"]
    contradicted = records["(2021-05-10) Insurance renewal (Seguradora Horizonte) [Insurance].pdf"]
    assert (contradicted["from"], contradicted["to"]) == ("2021-05-10", "2022-05-10")
    assert "page" in contradicted["why"]
    waiting = records["(2023-02-30) Gas bill (Energia do Norte).pdf"]
    assert "impossible" in waiting["why"] and "to" not in waiting


def test_without_the_flag_organized_names_are_prepared_as_before(
    organized: OrganizedFamily, tmp_path: Path
) -> None:
    prepare.prepare(organized.root, tmp_path / "prepared", apple=organized.model("apple"),
                    local=organized.model("local"))  # fmt: skip
    pdf = tmp_path / "prepared/Documents/PDF"
    assert (pdf / "2024/Águas do Vale/(2024-03-12) Document - Águas do Vale.pdf").is_file()
    assert "organized" not in _records(tmp_path / "prepared")[FIXTURES[0].name]


def test_the_owners_author_is_kept_even_when_rejected(
    organized: OrganizedFamily, tmp_path: Path
) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    author_knowledge.save(box, author_knowledge.Knowledge(
        rejected=["Energia do Norte"],
        instead=[{"said": "Energia do Norte", "use": "Someone Else"}],
    ))  # fmt: skip
    _organized_run(organized, tmp_path, box.root)
    filed = tmp_path / "prepared/Documents/PDF/2024/Energia do Norte"
    assert (filed / "(2024-02-28) Electricity bill (Energia do Norte) [Utilities].pdf").is_file()


def test_the_report_tells_each_name_and_holds_no_page_text(
    organized: OrganizedFamily, tmp_path: Path
) -> None:
    _organized_run(organized, tmp_path)
    report = (tmp_path / "prepared/report.txt").read_text(encoding="utf-8")
    assert "organized names" in report
    assert "kept: 4" in report and "date replaced: 2" in report
    assert "no author: 1" in report and "waiting: 1" in report and "not organized: 1" in report
    assert "2024-02-30 → 2024-02-28" in report and "2021-05-10 → 2022-05-10" in report
    everything = report + (tmp_path / "prepared/report.jsonl").read_text(encoding="utf-8")
    for words in ("Thank you for your custom", "Policy renewed", "Querida Maria", "23,40"):
        assert words not in everything


def test_every_record_tells_its_preprocessing(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "FAX COVER")
    doc.new_page().insert_text((72, 72), "The letter itself starts here")
    doc.save(folder / "Fax.pdf")
    doc.close()
    _bill(folder / "Bill.pdf")

    def model(text: str) -> dict[str, str]:
        if "second look" in text:
            return {"author": "Valley Water", "title": "Bill", "date": "2024-03-12"}
        return {"author": "", "title": "Bill", "date": "2024-03-12"}

    prepare.prepare(folder, tmp_path / "prepared", apple=model, local=None)
    records = _records(tmp_path / "prepared")
    assert records["Fax.pdf"]["cover"] is True and records["Fax.pdf"]["ocr_pages"] == []
    assert records["Bill.pdf"]["look"] == "bottom" and records["Bill.pdf"]["cover"] is False


def test_the_command_takes_the_flag(organized: OrganizedFamily, tmp_path: Path, capsys) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    out = tmp_path / "prepared"
    argv = ["documents", "prepare", str(organized.root), "--out", str(out), "--box",
            str(box.root), "--organized"]  # fmt: skip
    assert cli.main(argv) == 0  # no model here: the owner's names alone
    assert "organized names" in capsys.readouterr().out
    water = "2024/Águas do Vale/(2024-03-12) Water bill (Águas do Vale) [Utilities].pdf"
    assert (out / "Documents/PDF" / water).is_file()
    assert (out / "Documents/PDF/Unrecognized/(2023-11-05) Letter from João [Family].pdf").is_file()


# --- The whitelist (20261128-01 T03) --------------------------------------------------------------


def _box_files(box: Box) -> dict[str, bytes]:
    return {
        str(path.relative_to(box.root)): path.read_bytes()
        for path in sorted(box.root.rglob("*"))
        if path.is_file()
    }


def test_organized_names_teach_the_box_and_nothing_else_is_written(
    organized: OrganizedFamily, tmp_path: Path
) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    author_knowledge.save(box, author_knowledge.Knowledge(rejected=["Seguradora Horizonte"]))
    before = _box_files(box)
    _organized_run(organized, tmp_path, box.root)
    after = _box_files(box)
    changed = {name for name in after if before.get(name) != after[name]}
    assert changed == {".caixa/author-knowledge.json"}
    known = author_knowledge.load(box)
    # in the order the files are read; the models' João Costa is not learned
    assert known.accepted == [
        "Seguradora Horizonte", "Energia do Norte", "Banco Atlântico", "Águas do Vale",
    ]  # fmt: skip
    assert known.rejected == []
    assert known.tags == ["Receipts", "Insurance", "Family", "Utilities", "Banking", "Joint"]
    text = (box.caixa_dir / "author-knowledge.json").read_text(encoding="utf-8")
    for words in ("Thank you", "Policy renewed", "Querida", "Water bill"):
        assert words not in text


def test_without_the_flag_the_box_is_only_read(organized: OrganizedFamily, tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    before = _box_files(box)
    prepare.prepare(organized.root, tmp_path / "prepared", box.root,
                    apple=organized.model("apple"), local=organized.model("local"))  # fmt: skip
    assert _box_files(box) == before


def test_the_report_lists_what_was_learned(organized: OrganizedFamily, tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    _organized_run(organized, tmp_path, box.root)
    report = (tmp_path / "prepared/report.txt").read_text(encoding="utf-8")
    authors = "Seguradora Horizonte, Energia do Norte, Banco Atlântico, Águas do Vale"
    assert f"authors learned (4): {authors}" in report
    assert "tags learned (6): Receipts, Insurance, Family, Utilities, Banking, Joint" in report
    _organized_run(organized, tmp_path / "again", box.root)
    again = (tmp_path / "again/prepared/report.txt").read_text(encoding="utf-8")
    assert "authors learned (0)" in again and "already known: 4 authors, 6 tags" in again


def test_with_no_box_nothing_is_learned_and_the_report_says_so(
    organized: OrganizedFamily, tmp_path: Path
) -> None:
    _organized_run(organized, tmp_path)
    report = (tmp_path / "prepared/report.txt").read_text(encoding="utf-8")
    assert "not saved: no box was given (--box)" in report
