"""Ask the documents (ticket 20261124-21): a question answered by the local model from passages
Caixa retrieved, citing each as `[n]`; every citation is checked before the answer is shown. Only
stand-in models on this computer are asked (`stand_in_documents`, `stand_in_apple.py`)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa import settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import ask
from caixa.documents.search import search
from stub_server import StubServer

QUESTION = "How much was the electricity bill for December 2023?"
BILL = "2022 Car Insurance.pdf"  # the electricity bill, misleadingly named


@pytest.fixture
def model(pdf_family: Any) -> Iterator[Any]:
    from stand_in_documents import DocumentModel

    server = StubServer()
    server.model = DocumentModel(pdf_family)  # type: ignore[attr-defined]
    server.respond = server.model.respond  # type: ignore[attr-defined]
    yield server
    server.close()


@pytest.fixture
def box(pdf_family: Any, tmp_path: Path, model: Any) -> Box:
    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    made = Box.create(tmp_path / "Box", name="Our box")
    settings.save(made, {"documents.ocr": False, "documents.enrich": False})
    PdfCollector().run(made, source, {"workers": 1}, lambda step: None)
    settings.save(made, {"summaries.provider": "endpoint", "summaries.endpoint": model.endpoint,
                         "summaries.model": "stand-in-documents"})  # fmt: skip
    return made


def test_a_question_is_answered_citing_its_document_and_page(box: Box) -> None:
    answered = ask.ask_documents(box, QUESTION)
    assert answered["found"] is True and not answered.get("refused")
    assert answered["written_by"] == {"provider": "endpoint", "model": "stand-in-documents"}
    cited = answered["citations"]
    assert cited and cited[0]["page"] == 1
    assert cited[0]["file_path"].endswith(".pdf")
    assert any(c["original_filename"] == BILL for c in cited)
    for citation in cited:
        assert f"[{citation['n']}]" in answered["answer"]
        assert citation["passage"]


def test_any_word_finds_what_every_word_misses(box: Box) -> None:
    with box.master(read_only=True) as master:
        assert search(master, QUESTION) == []
        found = search(master, QUESTION, match="any")
    assert found and found[0]["original_filename"] == BILL


def test_how_many_passages_each_provider_reads() -> None:
    assert ask.COUNT == {"apple": 4, "endpoint": 8}


def test_the_passages_are_numbered_and_fit_the_budget(box: Box) -> None:
    with box.master(read_only=True) as master:
        passages = ask.retrieve(master, "statement Banco Atlântico", count=4)
    assert [p.n for p in passages] == list(range(1, len(passages) + 1)) and len(passages) <= 4
    written = ask.prompt(QUESTION, passages, budget=2000)
    assert written.startswith("Question: " + QUESTION)
    assert "[1] " in written and len(written) <= 2000


def test_a_citation_it_was_not_given_is_refused(box: Box, model: Any) -> None:
    model.model.misbehave["ask"] = "wrong_citation"
    answered = ask.ask_documents(box, QUESTION)
    assert answered["refused"] is True and answered["answer"] == ""
    assert answered["citations"] == [] and "passage" in answered["message"]


def test_an_answer_the_passages_do_not_hold(box: Box, model: Any) -> None:
    model.model.misbehave["ask"] = "not_found"
    answered = ask.ask_documents(box, QUESTION)
    assert answered["found"] is False and answered["citations"] == []
    assert not answered.get("refused")


def test_nothing_found_asks_no_model(box: Box, model: Any) -> None:
    answered = ask.ask_documents(box, "zzyzx qwerty")
    assert answered["found"] is False and answered["citations"] == []
    assert "No page" in answered["message"]


def test_a_remote_endpoint_is_refused(box: Box) -> None:
    settings.save(box, {"summaries.endpoint": "https://api.example.com/v1"})
    answered = ask.ask_documents(box, QUESTION)
    assert answered["reason"] == "remote"


def test_reading_turned_off_still_lets_the_owner_ask(box: Box) -> None:
    settings.save(box, {"documents.enrich": False})
    assert ask.ask_documents(box, QUESTION)["found"] is True


def test_nothing_is_logged(box: Box, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        ask.ask_documents(box, QUESTION)
    for words in ("electricity", "88.15", "maria"):
        assert words not in caplog.text.casefold()
