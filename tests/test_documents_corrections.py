"""The owner's corrections and the review of documents (ticket 20261124-19)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa import cli, settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import records
from caixa.documents.corrections import CorrectionError, candidates, correct


@pytest.fixture
def box(pdf_family: Any, tmp_path: Path) -> Box:
    """The family imported without OCR or a model: almost everything waits in Unrecognized."""
    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    made = Box.create(tmp_path / "Box", name="Our box")
    settings.save(made, {"documents.ocr": False, "documents.enrich": False})
    PdfCollector().run(made, source, {"workers": 1}, lambda step: None)
    return made


def _by_name(box: Box) -> dict[str, dict[str, Any]]:
    with box.master() as master:
        return {
            d["original_filename"]: records.get_document(master, d["item_id"])
            for d in records.list_documents(master)
        }


def test_an_author_and_a_date_file_an_unrecognized_document(box: Box) -> None:
    scan = _by_name(box)["scan_00482.pdf"]
    assert scan["file_path"] == "Documents/PDF/Unrecognized/scan_00482.pdf"
    with box.master() as master:
        moves = correct(box, master, scan["item_id"], author="Águas do Vale", date="2024-03-12")
    assert moves == [("Documents/PDF/Unrecognized/scan_00482.pdf",
                      "Documents/PDF/2024/Águas do Vale/(2024-03-12) scan_00482 - Águas do Vale.pdf")]  # fmt: skip
    after = _by_name(box)["scan_00482.pdf"]
    assert after["file_path"] == moves[0][1] and (box.root / moves[0][1]).is_file()
    assert (after["author"], after["date"], after["date_precision"]) == (
        "Águas do Vale",
        "2024-03-12",
        "day",
    )
    assert after["processing_status"] == "archived" and after["review"] == []
    owner = {(f["field"], f["value"]) for f in after["fields"] if f["source"] == "user_verified"}
    assert {("author", "Águas do Vale"), ("date", "2024-03-12")} <= owner


def test_a_title_correction_renames_the_file(box: Box) -> None:
    scan = _by_name(box)["scan_00482.pdf"]
    with box.master() as master:
        correct(box, master, scan["item_id"], author="Águas do Vale", date="2024-03")
        moves = correct(box, master, scan["item_id"], title="Water Bill")
    assert (
        moves[-1][1] == "Documents/PDF/2024/Águas do Vale/(2024-03) Water Bill - Águas do Vale.pdf"
    )
    owner_titles = [f for f in _by_name(box)["scan_00482.pdf"]["fields"]
                    if f["source"] == "user_verified" and f["field"] == "title"]  # fmt: skip
    assert len(owner_titles) == 1  # a second correction replaces the first


@pytest.mark.parametrize(
    ("values", "words"),
    [
        ({"date": "12/03/2024"}, "date"),
        ({"date": "2024-02-30"}, "date"),
        ({"author": "  ...  "}, "author"),
        ({"type": "spaceship"}, "type"),
        ({}, "nothing"),
    ],
)
def test_a_value_that_cannot_be_used_is_refused(
    box: Box, values: dict[str, str], words: str
) -> None:
    scan = _by_name(box)["scan_00482.pdf"]
    with box.master() as master, pytest.raises(CorrectionError) as refused:
        correct(box, master, scan["item_id"], **values)
    assert words in str(refused.value).lower()


def test_the_owners_word_survives_reading_again(box: Box, pdf_family: Any) -> None:
    from caixa.documents.enrich import enrich_documents
    from stand_in_documents import DocumentModel
    from stub_server import StubServer

    scan = _by_name(box)["scan_00482.pdf"]
    with box.master() as master:
        correct(
            box,
            master,
            scan["item_id"],
            author="Águas do Vale",
            date="2024-03-12",
            title="Conta da Água",
        )
    server = StubServer()
    server.respond = DocumentModel(pdf_family).respond
    try:
        settings.save(box, {"documents.enrich": True, "summaries.provider": "endpoint",
                            "summaries.endpoint": server.endpoint, "summaries.model": "stand-in"})  # fmt: skip
        enrich_documents(box, item_ids=[scan["item_id"]])
    finally:
        server.close()
    after = _by_name(box)["scan_00482.pdf"]
    assert after["title"] == "Conta da Água" and after["author"] == "Águas do Vale"
    assert after["file_path"].endswith("(2024-03-12) Conta da Água - Águas do Vale.pdf")


def test_candidates_come_with_their_sources(box: Box) -> None:
    statement = _by_name(box)["2024-11 Banco Atlântico Checking Statement.pdf"]
    with box.master() as master:
        found = candidates(master, statement["item_id"])
    authors = {(c["value"], c["source"]) for c in found["author"]}
    assert ("Banco Atlântico", "pdf_metadata") in authors
    assert any(
        c["source"] == "original_filename" and c["value"] == "2024-11" for c in found["date"]
    )
    assert all(
        {"value", "source", "label", "evidence", "page", "state"} <= set(c) for c in found["date"]
    )


@pytest.fixture
def service(box: Box) -> Iterator[Any]:
    from caixa.service import Service

    made = Service(roots=[box.root.parent])
    made.box_open(str(box.root))
    yield made
    made.close()


def test_the_service_corrects_and_the_pages_wait_in_the_window(service: Any, box: Box) -> None:
    scan = _by_name(box)["scan_00482.pdf"]
    service.batch_pages = True  # as Caixa's window does
    changed = service.call(
        "documents.update",
        {"item_id": scan["item_id"], "author": "Águas do Vale", "date": "2024-03"},
    )
    assert changed["document"]["file_path"].startswith("Documents/PDF/2024/Águas do Vale/")
    assert changed["pending"]["changes"] >= 1
    page = box.root / "Documents/PDF/2024/Águas do Vale/Águas do Vale.html"
    assert not page.exists()  # drawn with Update the pages
    job = service.call("people.update", {})["job"]
    done = service.wait(job["id"], 300)
    assert done["status"] == "done", done["error"]
    assert page.is_file()


def test_a_bad_correction_is_refused_by_the_service(service: Any, box: Box) -> None:
    from caixa.service import ServiceError

    scan = _by_name(box)["scan_00482.pdf"]
    with pytest.raises(ServiceError) as refused:
        service.call("documents.update", {"item_id": scan["item_id"], "date": "soon"})
    assert refused.value.kind == "invalid_params"


def test_the_review_lists_what_waits(service: Any) -> None:
    review = service.call("documents.review", {})["documents"]
    names = {d["original_filename"] for d in review}
    assert "extrato_protegido.pdf" in names  # locked
    locked = next(d for d in review if d["original_filename"] == "extrato_protegido.pdf")
    assert locked["reasons"] == ["Locked with a password"] and "candidates" in locked


def test_the_commands(box: Box, capsys: pytest.CaptureFixture[str]) -> None:
    scan = _by_name(box)["scan_00482.pdf"]
    root = str(box.root)
    assert cli.main(["documents", "update", scan["item_id"], "--author", "Águas do Vale",
                     "--date", "2024-03-12", "--box", root]) == 0  # fmt: skip
    assert "Filed as Documents/PDF/2024/Águas do Vale/" in capsys.readouterr().out
    assert (
        box.root / "Documents/PDF/2024/Águas do Vale/Águas do Vale.html"
    ).is_file()  # drawn at once
    assert cli.main(["documents", "review", "--box", root, "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)["documents"]
    assert "scan_00482.pdf" not in {d["original_filename"] for d in listed}
