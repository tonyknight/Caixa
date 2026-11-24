"""Passages, embeddings and hybrid search (ticket 20261124-20). Only a stand-in embedding model on
this computer is asked (`stand_in_embeddings`)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pytest

from caixa import settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import embeddings
from caixa.documents.embeddings import EmbeddingsUnavailable, embed_documents
from caixa.documents.passages import split
from stub_server import StubServer


@pytest.fixture
def endpoint() -> Iterator[StubServer]:
    import stand_in_embeddings

    server = StubServer()
    server.respond = stand_in_embeddings.respond
    yield server
    server.close()


def _values(server: StubServer, **more: Any) -> dict[str, Any]:
    return {"summaries.provider": "endpoint", "summaries.endpoint": server.endpoint,
            "summaries.model": "reader", "documents.embedding_model": "stand-in-embeddings", **more}  # fmt: skip


@pytest.fixture
def box(pdf_family: Any, tmp_path: Path, endpoint: StubServer) -> Box:
    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    made = Box.create(tmp_path / "Box", name="Our box")
    settings.save(made, {"documents.ocr": False, "documents.enrich": False})
    PdfCollector().run(made, source, {"workers": 1}, lambda step: None)
    settings.save(made, _values(endpoint, **{"documents.enrich": False}))
    return made


# --- Passages --------------------------------------------------------------------------------------


def test_passages_overlap_and_cover_the_text() -> None:
    text = " ".join(f"word{n}" for n in range(600))  # about 4,800 characters
    found = split(text, size=1000, overlap=150)
    assert len(found) >= 5
    assert found[0][0] == 0 and found[-1][1] == len(text)
    for (_, end, piece), (start, _, _) in zip(found, found[1:]):
        assert start < end  # they overlap
        assert len(piece) <= 1000
    for start, end, piece in found:
        assert text[start:end].strip() == piece
        assert start == 0 or text[start - 1] == " "  # cut where a word begins
        assert end == len(text) or text[end] == " "  # and where one ends


def test_a_short_page_is_one_passage_and_an_empty_one_none() -> None:
    assert split("Banco Atlântico\nConta 4821") == [(0, 26, "Banco Atlântico\nConta 4821")]
    assert split("   ") == []


# --- Vectors -------------------------------------------------------------------------------------


def test_every_readable_document_gets_vectors(box: Box) -> None:
    done = embed_documents(box)
    assert done["embedded"] > 0 and done["model"] == "stand-in-embeddings"
    with box.master() as master:
        rows = master.connection.execute(
            "SELECT item_id, page, text, embedding, embedding_model FROM chunks"
        ).fetchall()
    assert rows and all(r["embedding_model"] == "stand-in-embeddings" for r in rows)
    vector = np.frombuffer(rows[0]["embedding"], dtype=np.float32)
    assert vector.shape == (64,) and abs(float(np.linalg.norm(vector)) - 1.0) < 1e-5
    assert {r["item_id"] for r in rows} >= {d for d in done["documents"]}


def test_a_second_run_embeds_nothing(box: Box, endpoint: StubServer) -> None:
    embed_documents(box)
    asked = len(endpoint.requests)
    assert embed_documents(box)["embedded"] == 0 and len(endpoint.requests) == asked


def test_a_stopped_run_carries_on(box: Box, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    real = embeddings._ask

    def flaky(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 3:
            raise embeddings.EmbeddingError("the model stopped")
        return real(*args, **kwargs)

    monkeypatch.setattr(embeddings, "_ask", flaky)
    first = embed_documents(box)
    assert first["failed"] >= 1 and first["embedded"] >= 1
    monkeypatch.setattr(embeddings, "_ask", real)
    second = embed_documents(box)
    assert second["embedded"] >= 1 and second["failed"] == 0
    assert embed_documents(box)["embedded"] == 0


def test_without_a_model_there_is_nothing_to_do(box: Box, endpoint: StubServer) -> None:
    settings.save(box, _values(endpoint, **{"documents.embedding_model": ""}))
    done = embed_documents(box)
    assert done["embedded"] == 0 and done["reason"] == "no_model"


def test_an_endpoint_on_the_internet_is_refused() -> None:
    with pytest.raises(EmbeddingsUnavailable) as refused:
        embeddings.embedder({"summaries.endpoint": "https://api.example.com/v1",
                             "documents.embedding_model": "big", "summaries.allow_remote": True})  # fmt: skip
    assert refused.value.reason == "remote"


# --- Hybrid search, the job and the command (T02) ------------------------------------------------


def _search(box: Box, query: str, semantic: bool = True) -> list[dict[str, Any]]:
    from caixa.documents.search import search

    embed, model = embeddings.embedder(settings.load(box)) if semantic else (None, None)
    with box.master(read_only=True) as master:
        return search(master, query, embed=embed, model=model)


def test_a_paraphrase_finds_what_words_miss(box: Box) -> None:
    embed_documents(box)
    assert _search(box, "power invoice", semantic=False) == []
    found = _search(box, "power invoice")
    assert found and found[0]["original_filename"] == "2022 Car Insurance.pdf"
    assert found[0]["semantic"] is True and "Electricity" in found[0]["snippet"]


def test_words_still_come_first(box: Box) -> None:
    embed_documents(box)
    words = _search(box, "Supermercado", semantic=False)
    both = _search(box, "Supermercado")
    assert both[0]["item_id"] == words[0]["item_id"] and both[0]["page"] == words[0]["page"]
    assert "[Supermercado]" in both[0]["snippet"]


def test_without_vectors_it_is_search_by_words(box: Box) -> None:
    assert _search(box, "Maria") == _search(box, "Maria", semantic=False)


@pytest.fixture
def service(box: Box) -> Iterator[Any]:
    from caixa.service import Service

    made = Service(roots=[box.root.parent])
    made.box_open(str(box.root))
    yield made
    made.close()


def test_the_job_embeds_and_the_service_searches_by_meaning(service: Any) -> None:
    job = service.call("documents.embed", {})
    done = service.wait(job["id"], 300)
    assert done["status"] == "done", done["error"]
    assert done["result"]["embedded"] > 0
    found = service.call("documents.search", {"query": "power invoice"})["hits"]
    assert found and found[0]["original_filename"] == "2022 Car Insurance.pdf"


def test_the_command_embeds(box: Box, capsys: pytest.CaptureFixture[str]) -> None:
    from caixa import cli

    assert cli.main(["documents", "embed", "--box", str(box.root)]) == 0
    assert "documents embedded" in capsys.readouterr().out


def test_an_import_embeds_when_a_model_is_set(
    pdf_family: Any, tmp_path: Path, endpoint: StubServer
) -> None:
    source = tmp_path / "more"
    source.mkdir()
    shutil.copyfile(pdf_family.root / "2022 Car Insurance.pdf", source / "2022 Car Insurance.pdf")
    made = Box.create(tmp_path / "Other", name="Other box")
    settings.save(made, {**_values(endpoint), "documents.ocr": False, "documents.enrich": False})
    PdfCollector().run(made, source, {"workers": 1}, lambda step: None)
    with made.master() as master:
        (count,) = master.connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL"
        ).fetchone()
    assert count >= 1
