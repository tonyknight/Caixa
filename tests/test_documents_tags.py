"""Summaries and tags (ticket 20261124-13): written by the model, made right by Caixa, and the
owner's to change."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa.documents.tags import normalize_tags

STARTERS = ["banking", "statement", "bill", "utilities", "receipt", "invoice", "cheque", "tax",
            "insurance", "medical", "legal", "property", "correspondence", "pension", "car", "home"]  # fmt: skip


@pytest.mark.parametrize(
    ("given", "kept"),
    [
        (["Statements", "Banking"], ["statement", "banking"]),
        (["Médical", "CHEQUES"], ["medical", "cheque"]),
        (["  family   papers ", "Family Papers"], ["family papers"]),
        (["bill", "bills", "Bill"], ["bill"]),
        (["a", "b", "c", "d", "e"], ["a", "b", "c", "d"]),
        (["", "  "], []),
    ],
)
def test_tags_are_made_tidy(given: list[str], kept: list[str]) -> None:
    assert normalize_tags(given, STARTERS) == kept


@pytest.fixture
def stand_in(pdf_family: Any) -> Iterator[Any]:
    from stand_in_documents import DocumentModel
    from stub_server import StubServer

    server = StubServer()
    server.model = DocumentModel(pdf_family)  # type: ignore[attr-defined]
    server.respond = server.model.respond  # type: ignore[attr-defined]
    yield server
    server.close()


@pytest.fixture
def imported(pdf_family: Any, tmp_path: Path, stand_in: Any) -> Any:
    from caixa import settings
    from caixa.box import Box
    from caixa.collectors.pdfImport import PdfCollector

    stand_in.model.summaries["receipt_rotated.pdf"] = (
        "Café Central gave this receipt for two coffees and a cake. " * 6
    ).strip()
    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(
        box,
        {
            "documents.ocr": False,
            "summaries.provider": "endpoint",
            "summaries.endpoint": stand_in.endpoint,
            "summaries.model": "stand-in-documents",
        },
    )
    PdfCollector().run(box, source, {"workers": 1}, lambda step: None)
    return box


def _documents(box: Any) -> dict[str, dict[str, Any]]:
    from caixa.documents import records

    with box.master() as master:
        return {
            d["original_filename"]: records.get_document(master, d["item_id"])
            for d in records.list_documents(master)
        }


def test_the_prompt_names_the_starter_tags(imported: Any, stand_in: Any) -> None:
    prompt = stand_in.model.prompts["2022 Car Insurance.pdf"]
    assert "Tags to use when they fit:" in prompt and "utilities" in prompt


def test_documents_get_a_summary_by_a_model(imported: Any) -> None:
    bill = _documents(imported)["2022 Car Insurance.pdf"]
    assert 30 <= len(bill["summary"].split()) <= 50
    assert bill["summary_model"] == "stand-in-documents"


def test_a_long_summary_is_cut_at_a_sentence(imported: Any) -> None:
    receipt = _documents(imported)["receipt_rotated.pdf"]
    words = receipt["summary"].split()
    assert len(words) <= 50 and receipt["summary"].endswith(".")


def test_documents_get_their_tags(imported: Any) -> None:
    statement = _documents(imported)["2024-11 Banco Atlântico Checking Statement.pdf"]
    assert {t["tag"] for t in statement["tags"]} == {"statement", "family papers"}
    assert {t["source"] for t in statement["tags"]} == {"ai_inference"}


def test_a_document_in_review_still_gets_them(imported: Any) -> None:
    misleading = _documents(imported)["2022 Car Insurance.pdf"]
    assert misleading["processing_status"] == "needs_review"
    assert misleading["summary"] and {t["tag"] for t in misleading["tags"]} == {
        "bill",
        "family papers",
    }


# --- The owner's tags and the starter set (T02) --------------------------------------------------


def test_the_owner_adds_and_removes_tags(imported: Any) -> None:
    from caixa.documents.enrich import enrich_documents
    from caixa.documents.tags import change_tags

    statement = _documents(imported)["2024-11 Banco Atlântico Checking Statement.pdf"]
    with imported.master() as master:
        change_tags(master, statement["item_id"], add=["Checking"], remove=["family papers"])
    after = {
        t["tag"]: t["source"] for t in _documents(imported)[statement["original_filename"]]["tags"]
    }
    assert after == {"statement": "ai_inference", "checking": "user_verified"}
    enrich_documents(imported, item_ids=[statement["item_id"]])
    again = {t["tag"] for t in _documents(imported)[statement["original_filename"]]["tags"]}
    assert again == {"statement", "checking"}  # what the owner took out stays out


def test_the_starter_set_can_grow_and_shrink(imported: Any) -> None:
    from caixa.documents.tags import change_starter, starter_tags

    with imported.master() as master:
        change_starter(master, add=["Pets"], remove=["car"])
        found = starter_tags(master)
    assert "pets" in found and "car" not in found and "home" in found


def test_the_service_and_the_command(imported: Any, capsys: pytest.CaptureFixture[str]) -> None:
    from caixa import cli
    from caixa.service import Service

    bill = _documents(imported)["2022 Car Insurance.pdf"]
    service = Service(roots=[imported.root.parent])
    service.box_open(str(imported.root))
    try:
        changed = service.call(
            "documents.tags",
            {"item_id": bill["item_id"], "add": ["electricity"], "remove": ["bill"]},
        )
        assert {t["tag"] for t in changed["tags"]} == {"electricity", "family papers"}
        starters = service.call("documents.tags.starter", {"add": ["school"]})
        assert "school" in starters["starter"]
    finally:
        service.close()
    box = str(imported.root)
    assert cli.main(["documents", "tags", bill["item_id"], "--add", "energy", "--box", box]) == 0
    assert "energy" in capsys.readouterr().out
    assert cli.main(["documents", "tags", "--starter", "--remove", "school", "--box", box]) == 0
    assert "school" not in capsys.readouterr().out
