"""Reconciling what the filename, the properties, the text, the model and the owner say, and
deciding whether a document can be named and filed (ticket 20261124-12)."""

from __future__ import annotations

import shutil
from itertools import count
from pathlib import Path
from typing import Any, Iterator, Optional

import pytest

from caixa.documents.reconcile import decide

_ids = count(1)


def F(field: str, value: str, source: str, evidence: Optional[str] = None,
      page: Optional[int] = None, verified: Optional[int] = None) -> dict[str, Any]:  # fmt: skip
    return {"id": next(_ids), "field": field, "value": value, "source": source,
            "evidence": evidence, "page": page, "verified": verified, "state": "proposed"}  # fmt: skip


PAGES = {
    1: "Banco Atlântico\nChecking Statement\nStatement period: November 1, 2024 to November 30, 2024"
}


def _model(**values: Any) -> list[dict[str, Any]]:
    base = {
        "type": F("type", "statement", "ai_inference"),
        "category": F("category", "financial", "ai_inference"),
        "title": F("title", "Checking Statement", "ai_inference"),
        "author": F("author", "Banco Atlântico", "ai_inference", "Banco Atlântico", 1, 1),
        "date": F("date", "2024-11-30", "ai_inference", "November 30, 2024", 1, 1),
        "date_kind": F("date_kind", "statement_end", "ai_inference"),
    }
    for key, value in values.items():
        if value is None:
            base.pop(key, None)
        else:
            base[key] = value
    return list(base.values())


def test_everything_agreeing_is_confident() -> None:
    fields = _model() + [
        F("date", "2024-11", "original_filename", "2024-11"),
        F("type", "statement", "original_filename"),
        F("author", "Banco Atlântico", "pdf_metadata", "Banco Atlântico"),
    ]
    decision = decide(fields, PAGES, {}, ai_ok=True)
    assert decision.confident and decision.reasons == []
    assert (decision.date, decision.precision, decision.date_kind) == (
        "2024-11-30",
        "day",
        "statement_end",
    )
    assert (decision.title, decision.author, decision.type, decision.category) == (
        "Checking Statement", "Banco Atlântico", "statement", "financial",
    )  # fmt: skip
    applied = {f["field"] for f in fields if f["id"] in decision.applied}
    assert {"date", "author", "title", "type", "category"} <= applied
    assert decision.date_sources == ["ai_inference", "original_filename"]


def test_a_more_precise_filename_date_is_kept() -> None:
    fields = _model(date=F("date", "2024-11", "ai_inference", "November", 1, 1)) + [
        F("date", "2024-11-30", "original_filename", "2024-11-30")
    ]
    decision = decide(fields, PAGES, {}, ai_ok=True)
    assert decision.date == "2024-11-30" and decision.precision == "day"


def test_a_filename_date_that_names_another_date_is_explained() -> None:
    pages = {1: "Property Tax Statement\nTax year 2022\nIssued: April 20, 2023"}
    fields = _model(
        type=F("type", "tax", "ai_inference"),
        title=F("title", "Property Tax Bill", "ai_inference"),
        author=F("author", "Câmara Municipal de Vila Nova", "ai_inference", "Câmara", 1, 1),
        date=F("date", "2022", "ai_inference", "Tax year 2022", 1, 1),
        date_kind=F("date_kind", "tax_year", "ai_inference"),
    ) + [
        F("date", "2023", "original_filename", "2023"),
        F("date_in_text", "2023-04-20", "pdf_content", "April 20, 2023", 1),
        F("type", "tax", "original_filename"),
        F("type", "bill", "original_filename"),
    ]
    decision = decide(fields, pages, {}, ai_ok=True)
    assert decision.confident and decision.date == "2022" and decision.precision == "year"
    assert decision.explained == [("2023", "issue")] or decision.explained == [("2023", "other")]


def test_a_filename_date_nothing_explains_is_a_conflict() -> None:
    pages = {
        1: "Energia do Norte\nElectricity Bill\nIssued: January 10, 2024\nBilling period: December 2023"
    }
    filename_date = F("date", "2022", "original_filename", "2022")
    fields = _model(
        type=F("type", "bill", "ai_inference"),
        title=F("title", "Electricity Bill", "ai_inference"),
        author=F("author", "Energia do Norte", "ai_inference", "Energia do Norte", 1, 1),
        date=F("date", "2024-01-10", "ai_inference", "January 10, 2024", 1, 1),
        date_kind=F("date_kind", "issue", "ai_inference"),
    ) + [
        filename_date,
        F("type", "insurance", "original_filename"),
        F("date_in_text", "2024-01-10", "pdf_content", "January 10, 2024", 1),
    ]
    decision = decide(fields, pages, {}, ai_ok=True)
    assert not decision.confident
    assert {"conflict:date", "conflict:type"} <= set(decision.reasons)
    assert filename_date["id"] in decision.conflicts


def test_type_words_agree_when_one_of_them_is_the_models() -> None:
    fields = _model() + [
        F("type", "bill", "original_filename"),
        F("type", "statement", "original_filename"),
    ]
    assert "conflict:type" not in decide(fields, PAGES, {}, ai_ok=True).reasons


def test_a_bill_and_an_invoice_are_close_enough() -> None:
    fields = _model(type=F("type", "invoice", "ai_inference")) + [
        F("type", "bill", "original_filename")
    ]
    assert "conflict:type" not in decide(fields, PAGES, {}, ai_ok=True).reasons


def test_an_author_is_matched_to_a_known_one() -> None:
    known = {"banco atlantico": "Banco Atlântico"}
    fields = _model(
        author=F("author", "BANCO ATLANTICO, S.A.", "ai_inference", "Banco Atlântico", 1, 1)
    )
    decision = decide(fields, PAGES, known, ai_ok=True)
    assert decision.author == "Banco Atlântico" and decision.alias == "BANCO ATLANTICO, S.A."


def test_a_different_author_in_the_filename_is_a_conflict() -> None:
    fields = _model() + [
        F("author", "Seguradora Horizonte", "original_filename", "Seguradora Horizonte")
    ]
    decision = decide(fields, PAGES, {}, ai_ok=True)
    assert "conflict:author" in decision.reasons and not decision.confident


def test_a_different_author_in_the_properties_is_not() -> None:
    fields = _model() + [F("author", "J. Smith", "pdf_metadata", "J. Smith")]
    assert decide(fields, PAGES, {}, ai_ok=True).confident


def test_the_owners_values_win() -> None:
    fields = _model() + [
        F("author", "Banco do Atlântico", "user_verified"),
        F("date", "2024-12", "user_verified"),
        F("title", "Statement of Account", "user_verified"),
    ]
    decision = decide(fields, PAGES, {}, ai_ok=True)
    assert decision.author == "Banco do Atlântico" and decision.date == "2024-12"
    assert decision.precision == "month" and decision.title == "Statement of Account"
    assert decision.confident  # the owner's word needs no evidence


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"date": None}, "no_date"),
        ({"author": None}, "no_author"),
        ({"date": F("date", "2024-11-30", "ai_inference", "30 Nov", 1, 0)}, "unverified_date"),
        (
            {"author": F("author", "Banco Central", "ai_inference", "Banco Central", 1, 0)},
            "unverified_author",
        ),
        ({"title": None}, "no_title"),
        ({"type": None}, "no_type"),
    ],
)
def test_each_reason_for_review(changes: dict[str, Any], reason: str) -> None:
    decision = decide(_model(**changes), PAGES, {}, ai_ok=True)
    assert reason in decision.reasons and not decision.confident


def test_an_unusable_reading_is_not_confident() -> None:
    decision = decide(_model(), PAGES, {}, ai_ok=False)
    assert "ai_unusable" in decision.reasons and not decision.confident


def test_an_author_named_in_the_text_needs_no_quote() -> None:
    fields = _model(author=F("author", "Banco Atlântico", "ai_inference", None, None, None))
    assert decide(fields, PAGES, {}, ai_ok=True).confident


def test_a_date_written_in_the_text_needs_no_quote() -> None:
    fields = _model(date=F("date", "2024-11-30", "ai_inference", None, None, None)) + [
        F("date_in_text", "2024-11-30", "pdf_content", "November 30, 2024", 1)
    ]
    assert decide(fields, PAGES, {}, ai_ok=True).confident


# --- Applying, in an import (T02) ----------------------------------------------------------------

from caixa.documents.pdf import ocr as _ocr  # noqa: E402

needs_ocr = pytest.mark.skipif(not _ocr.tools().ready, reason="OCR tools missing here")


@pytest.fixture
def stand_in(pdf_family: Any) -> Iterator[Any]:
    from stand_in_documents import DocumentModel
    from stub_server import StubServer

    server = StubServer()
    server.model = DocumentModel(pdf_family)  # type: ignore[attr-defined]
    server.respond = server.model.respond  # type: ignore[attr-defined]
    yield server
    server.close()


def _settings(server: Any) -> dict[str, Any]:
    return {
        "summaries.provider": "endpoint",
        "summaries.endpoint": server.endpoint,
        "summaries.model": "stand-in-documents",
    }


@pytest.fixture
def imported(pdf_family: Any, tmp_path: Path, stand_in: Any) -> Any:
    from caixa import settings
    from caixa.box import Box
    from caixa.collectors.pdfImport import PdfCollector

    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, _settings(stand_in))
    result = PdfCollector().run(box, source, {"workers": 2}, lambda step: None)
    return box, result


def _documents(box: Any) -> dict[str, dict[str, Any]]:
    from caixa.documents import records

    with box.master() as master:
        return {
            d["original_filename"]: records.get_document(master, d["item_id"])
            for d in records.list_documents(master)
        }


@needs_ocr
@pytest.mark.parametrize(
    ("name", "path"),
    [
        ("2024-11 Banco Atlântico Checking Statement.pdf",
         "2024/Banco Atlântico/(2024-11-30) Checking Statement - Banco Atlântico.pdf"),
        ("scan_00482.pdf", "2024/Águas do Vale/(2024-03-12) Fatura de Água - Águas do Vale.pdf"),
        ("2023 Property Tax Bill.pdf",
         "2022/Câmara Municipal de Vila Nova/(2022) Property Tax Bill - Câmara Municipal de Vila Nova.pdf"),
        ("2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf",
         "2024/Seguradora Horizonte/(2024-07-01) Home Insurance Renewal - Seguradora Horizonte.pdf"),
        ("receipt_rotated.pdf", "2024/Café Central/(2024-05-03) Receipt 0093 - Café Central.pdf"),
    ],
)  # fmt: skip
def test_confident_documents_are_named_and_filed(imported: Any, name: str, path: str) -> None:
    box, _ = imported
    document = _documents(box)[name]
    assert document["file_path"] == f"Documents/PDF/{path}", document["review"]
    assert (box.root / document["file_path"]).is_file()
    assert document["processing_status"] == "archived" and document["review"] == []


@needs_ocr
def test_the_filenames_other_date_is_kept_as_what_it_is(imported: Any) -> None:
    box, _ = imported
    tax = _documents(box)["2023 Property Tax Bill.pdf"]
    assert tax["date"] == "2022" and tax["date_precision"] == "year" and tax["date_kind"] == "tax_year"
    kept = [f for f in tax["fields"] if f["source"] == "original_filename" and f["value"] == "2023"]
    assert {f["field"] for f in kept} >= {"date"} and any(f["field"].startswith("date_") for f in kept)


def test_a_misleading_name_waits_for_review(imported: Any) -> None:
    box, _ = imported
    misleading = _documents(box)["2022 Car Insurance.pdf"]
    assert misleading["file_path"] == "Documents/PDF/Unrecognized/2022 Car Insurance.pdf"
    assert {"conflict:date", "conflict:type"} <= set(misleading["review"])
    assert misleading["processing_status"] == "needs_review"
    states = {(f["field"], f["source"]): f["state"] for f in misleading["fields"]}
    assert states[("date", "original_filename")] == "conflict"
    assert states[("date", "ai_inference")] == "conflict"


def test_a_document_without_an_author_waits(imported: Any) -> None:
    box, _ = imported
    contract = _documents(box)["old_ocr_contract.pdf"]
    assert "no_author" in contract["review"] and "/Unrecognized/" in contract["file_path"]


@needs_ocr
def test_a_probable_duplicate_is_filed_and_still_waits(imported: Any) -> None:
    box, _ = imported
    again = _documents(box)["Banco Atlântico November 2024 (1).pdf"]
    assert again["file_path"].startswith("Documents/PDF/2024/Banco Atlântico/")
    assert again["file_path"].endswith(" (2).pdf")
    assert again["review"] == ["probable_duplicate"]


def test_applied_fields_are_marked(imported: Any) -> None:
    box, _ = imported
    statement = _documents(box)["2024-11 Banco Atlântico Checking Statement.pdf"]
    applied = {(f["field"], f["source"]) for f in statement["fields"] if f["state"] == "applied"}
    assert {("date", "ai_inference"), ("author", "ai_inference"), ("type", "ai_inference"),
            ("date", "original_filename")} <= applied  # fmt: skip


@needs_ocr
def test_the_moves_can_be_undone(pdf_family: Any, tmp_path: Path, stand_in: Any) -> None:
    from caixa import settings
    from caixa.service import Service

    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    service = Service(roots=[tmp_path])
    try:
        service.box_create(str(tmp_path / "Box"), name="Our box", owner="Maria Costa")
        from caixa.box import Box

        settings.save(Box.open(tmp_path / "Box"), _settings(stand_in))
        done = service.wait(service.import_start("pdf", str(source))["id"], 600)
        assert done["status"] == "done", done["error"]
        assert "moved" not in done["result"]  # kept on the undo snapshot, not shown
        documents = tmp_path / "Box" / "Documents"
        assert (documents / "PDF" / "2024" / "Banco Atlântico").is_dir()
        undone = service.wait(service.import_undo()["id"], 600)
        assert undone["status"] == "done", undone["error"]
        assert not any(documents.rglob("*.pdf"))
    finally:
        service.close()


def test_reading_again_moves_nothing(imported: Any) -> None:
    from caixa.documents.enrich import enrich_documents

    box, _ = imported
    before = {name: d["file_path"] for name, d in _documents(box).items()}
    done = enrich_documents(box, every=True)
    assert done["moved"] == []
    assert {name: d["file_path"] for name, d in _documents(box).items()} == before
