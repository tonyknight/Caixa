"""No page text in the logs (ticket 20261124-23, D26): the whole path of a document through
Caixa's service (import with OCR where the tools are here, reading by a stand-in model,
embedding, Ask and search) prints nothing of what the pages say into a job's log, the terminal or
the jobs' stored messages."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import pytest

from caixa import settings
from caixa.box import Box
from caixa.documents.pdf import ocr
from stub_server import StubServer


def _page_words(pdf_family: Any) -> set[str]:
    """Words only the pages hold: each fixture's own, less any that is also a file's name, a
    title or an author (those may rightly be said)."""
    said = set()
    for fixture in pdf_family.documents:
        for value in (fixture.path, fixture.title, fixture.author):
            if value:
                said.add(str(value).casefold())
    words = set()
    for fixture in pdf_family.documents:
        for word in fixture.words:
            if not any(word.casefold() in name for name in said):
                words.add(word)
    return words


def test_the_fixtures_have_page_words_to_look_for(pdf_family: Any) -> None:
    words = _page_words(pdf_family)
    assert {"Supermercado Sol", "HZ-55120", "1,987.20"} <= words


def test_no_page_text_in_the_logs(
    pdf_family: Any, tmp_path: Path, capfd: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:  # fmt: skip
    import stand_in_embeddings
    from stand_in_documents import DocumentModel

    from caixa.service import Service

    reader, vectors = StubServer(), StubServer()
    reader.respond = DocumentModel(pdf_family).respond
    vectors.respond = stand_in_embeddings.respond
    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {
        "documents.ocr": ocr.tools().ready, "summaries.provider": "endpoint",
        "summaries.endpoint": reader.endpoint, "summaries.model": "stand-in-documents",
    })  # fmt: skip
    service = Service(roots=[tmp_path])
    try:
        caplog.set_level(logging.DEBUG)
        service.box_open(str(box.root))
        job = service.call("import.start", {"collector": "pdf", "source": str(source),
                                            "options": {"workers": 1}})  # fmt: skip
        done = service.wait(job["id"], 600)
        assert done["status"] == "done", done["error"]
        settings.save(box, {"documents.embedding_model": "stand-in-embeddings",
                            "summaries.endpoint": vectors.endpoint})  # fmt: skip
        embedded = service.wait(service.call("documents.embed", {})["id"], 300)
        assert embedded["status"] == "done" and embedded["result"]["embedded"] > 0
        settings.save(box, {"summaries.endpoint": reader.endpoint})
        read = service.wait(service.call("documents.enrich", {"all": True})["id"], 600)
        assert read["status"] == "done", read["error"]
        answered = service.call("documents.ask", {"question": "How much was the electricity bill?"})
        assert answered["found"] is True  # (the question reached the model)
        assert service.call("documents.search", {"query": "Supermercado"})["hits"]
        messages = [str(j.get("message") or "") + str(j.get("error") or "")
                    for j in service.call("jobs.list", {})]  # fmt: skip
        before = set((box.logs_dir / "sessions").iterdir())
        sessions = _read(before)
        settings.save(box, {"documents.log_quotes": True})
        quoted = service.wait(service.call("documents.enrich", {"all": True})["id"], 600)
        assert quoted["status"] == "done", quoted["error"]
        with_quotes = _read(set((box.logs_dir / "sessions").iterdir()) - before)
    finally:
        service.close()
        reader.close()
        vectors.close()
    logs = [p.read_text(encoding="utf-8", errors="replace") for p in box.logs_dir.glob("*.log")]
    assert logs  # every job kept its log
    out = capfd.readouterr()
    everything = "\n".join([*logs, *messages, out.out, out.err, caplog.text])
    leaked = sorted(word for word in _page_words(pdf_family) if word in everything)
    assert leaked == []
    # The session logs (D26 as amended): values, never page text, passages or summaries; the
    # model's quotes and replies only once the owner asks for them.
    assert sessions.count("--- summary: done") == 3  # the import, the embedding, the reading
    assert sorted(word for word in _page_words(pdf_family) if word in sessions) == []
    with box.master() as master:
        written = [s for (s,) in master.connection.execute("SELECT summary FROM documents")]
        passages = [t for (t,) in master.connection.execute("SELECT text FROM chunks")]
    assert [s for s in written if s] and passages
    assert not [s for s in written if s and s in sessions]
    assert not [p for p in passages if len(p) > 40 and p in sessions]
    assert "author_quote" not in sessions and '"reply":' not in sessions
    assert "author_quote" in with_quotes and '"reply":' in with_quotes
    assert not [s for s in written if s and s[:40] in with_quotes]


def _read(paths: set[Path]) -> str:
    """These session logs' text and JSON lines."""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(paths))


@pytest.mark.skipif(not hasattr(__import__("os"), "geteuid"), reason="POSIX permissions")
def test_the_working_copies_are_the_owners_alone(tmp_path: Path) -> None:
    import stat

    box = Box.create(tmp_path / "Box", name="Our box")
    folder = box.work_dir("documents")
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    folder.chmod(0o755)  # (as an older Caixa left it)
    assert stat.S_IMODE(box.work_dir("documents").stat().st_mode) == 0o700
