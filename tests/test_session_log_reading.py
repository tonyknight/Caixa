"""Reading, reconciliation, embedding and drawing in the session log (20261125-02 T03), with the
stand-in model. Synthetic family only."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa import session_log, settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import enrich, records
from caixa.session_log import SessionLog
from pdf_family import PdfFamily
from stand_in_documents import DocumentModel
from stub_server import StubServer

STATEMENT = "2024-11 Banco Atlântico Checking Statement.pdf"
MISLEADING = "2022 Car Insurance.pdf"
RECEIPT = "receipt_rotated.pdf"


@pytest.fixture
def server(pdf_family: PdfFamily) -> Iterator[StubServer]:
    made = StubServer()
    model = DocumentModel(pdf_family)
    made.respond = model.respond
    made.model = model  # type: ignore[attr-defined]
    yield made
    made.close()


@pytest.fixture
def family(pdf_family: PdfFamily, tmp_path: Path) -> Path:
    copy = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, copy)
    (copy / "answers.json").unlink()
    return copy


def _box(tmp_path: Path, server: StubServer, **more: Any) -> Box:
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(
        box,
        {
            "documents.ocr": False,
            "summaries.provider": "endpoint",
            "summaries.endpoint": server.endpoint,
            "summaries.model": "stand-in-documents",
            **more,
        },
    )
    return box


def _import(box: Box, family: Path) -> list[dict[str, Any]]:
    with session_log.opened(box, 1, "PDF import") as log:
        PdfCollector().run(box, family, {"workers": 1}, lambda step: None)
    assert isinstance(log, SessionLog)
    return [json.loads(line) for line in log.events_path.read_text().splitlines()]


def _by(events: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    return {e["document"]["name"]: e for e in events if e["event"] == name and "document" in e}


def test_the_model_and_why_it_reads_are_logged(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    events = _import(_box(tmp_path, server), family)
    chosen = next(e for e in events if e["event"] == "provider")
    assert chosen["provider"] == "endpoint" and chosen["model"] == "stand-in-documents"
    assert chosen["budget"] == enrich.BUDGET and "Settings" in chosen["why"]


def test_each_reading_logs_what_was_sent_the_attempts_and_the_proposal(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    events = _import(_box(tmp_path, server), family)
    read = _by(events, "read")[STATEMENT]
    assert 0 < read["sent"] <= read["budget"] and read["pages"] == [1, 2]
    assert [a["problem"] for a in read["attempts"]] == [None] and read["seconds"] >= 0
    proposed = _by(events, "propose")[STATEMENT]
    assert proposed["type"] == "statement" and proposed["author"] == "Banco Atlântico"
    assert proposed["author_verified"] is True and proposed["date"].startswith("2024-11")
    assert "summary" not in proposed and "author_quote" not in proposed  # D26


def test_a_confident_document_logs_its_move(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    decided = _by(_import(_box(tmp_path, server), family), "decide")[RECEIPT]
    assert decided["confident"] is True and not decided.get("reasons")
    assert decided["moved_from"].startswith("Documents/PDF/Unrecognized/")
    assert decided["moved_to"].startswith("Documents/PDF/2024/Café Central/")
    assert any(step.startswith("date:") for step in decided["trail"])


def test_a_misleading_filename_logs_its_conflicts_with_both_values(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    decided = _by(_import(_box(tmp_path, server), family), "decide")[MISLEADING]
    assert decided["confident"] is False
    assert {"conflict:date", "conflict:type"} <= set(decided["reasons"])
    trail = " | ".join(decided["trail"])
    assert "2022" in trail and "2024-01-10" in trail
    assert decided["stays"] == "Documents/PDF/Unrecognized/2022 Car Insurance.pdf"


def test_an_answer_that_is_not_json_logs_two_attempts_and_goes_to_review(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    server.model.misbehave[MISLEADING] = "not_json"  # type: ignore[attr-defined]
    events = _import(_box(tmp_path, server), family)
    read = _by(events, "read")[MISLEADING]
    assert len(read["attempts"]) == 2 and all(a["problem"] for a in read["attempts"])
    assert "ai_unusable" in _by(events, "decide")[MISLEADING]["reasons"]


def test_raw_replies_and_quotes_are_logged_only_when_asked(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    events = _import(_box(tmp_path, server, **{"documents.log_quotes": True}), family)
    read = _by(events, "read")[STATEMENT]
    reply = json.loads(read["attempts"][0]["reply"])
    assert reply["type"] and "summary" not in reply  # D26: never a summary, even opted in
    assert _by(events, "propose")[STATEMENT]["author_quote"]


def test_a_failing_provider_logs_each_failure_and_the_stop(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    server.status = 500
    events = _import(_box(tmp_path, server), family)
    failed = [e for e in events if e["event"] == "read" and e.get("error")]
    assert len(failed) == 2
    stopped = next(e for e in events if e["event"] == "stopped")
    assert stopped["waiting"] > 0 and "in a row" in stopped["message"]


def test_without_a_model_the_log_says_why_nothing_was_read(family: Path, tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.ocr": False, "summaries.provider": "endpoint"})
    events = _import(box, family)
    nothing = next(e for e in events if e["event"] == "provider")
    assert nothing["reason"] == "no_model" and nothing["waiting"] > 0


def test_an_unexpected_error_reading_one_document_is_logged_with_its_traceback(
    server: StubServer, family: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = enrich.classify

    def classify(client: Any, document: Any, budget: int) -> Any:
        if document.filename == MISLEADING:
            raise TypeError("an unexpected error")
        return real(client, document, budget)

    monkeypatch.setattr(enrich, "classify", classify)
    events = _import(_box(tmp_path, server), family)
    error = next(e for e in events if e["event"] == "error")
    assert error["stage"] == "read" and MISLEADING in error["document"]
    assert error["type"] == "TypeError" and "Traceback" in error["traceback"]


def test_the_summary_tallies_the_review_reasons_the_master_holds(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    box = _box(tmp_path, server)
    summary = _import(box, family)[-1]
    with box.master() as master:
        documents = records.list_documents(master)
    unrecognized = [d for d in documents if "/Unrecognized/" in d["file_path"]]
    assert summary["outcomes"].get("Unrecognized", 0) == len(unrecognized)
    expected: dict[str, int] = {}
    for document in unrecognized:
        with box.master() as master:
            found = records.get_document(master, document["item_id"])
        if found["ai_status"] == "pending":  # never read (locked): its filing gaps are tallied
            continue
        for reason in found["review"]:
            expected[reason] = expected.get(reason, 0) + 1
    tallied = dict(summary["reasons"].get("Unrecognized", {}))
    for reason in ("no_date", "no_author"):  # the locked statement's, from filing
        tallied[reason] -= 1
    tallied.pop("locked")
    assert {k: v for k, v in tallied.items() if v} == expected
    assert {"read", "draw"} <= set(summary["stages"])


def test_drawing_says_how_many_pages_it_wrote(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    drawn = next(e for e in _import(_box(tmp_path, server), family) if e["event"] == "drawn")
    assert drawn["pages"] > 0


def test_embedding_logs_its_model_and_each_document(
    server: StubServer, family: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caixa.documents import embeddings

    def embedder(values: Any, timeout: float = 0) -> Any:
        return (lambda texts: [[1.0, 0.0] for _ in texts]), "stand-in-embeddings"

    monkeypatch.setattr(embeddings, "embedder", embedder)
    box = _box(tmp_path, server, **{"documents.embedding_model": "stand-in-embeddings"})
    events = _import(box, family)
    assert next(e for e in events if e["event"] == "embedder")["model"] == "stand-in-embeddings"
    embedded = _by(events, "embed")
    assert embedded[STATEMENT]["passage_count"] > 0
