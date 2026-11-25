"""The import session log (20261125-02 T01): one file per document job in `.caixa/logs/sessions/`,
with a JSON-lines twin, saying what each stage decided. Synthetic family only."""

from __future__ import annotations

import json
import re
import stat
import sys
from pathlib import Path
from typing import Any, Iterator

import pytest

import caixa
from caixa import session_log, settings
from caixa.box import Box
from caixa.session_log import Document, Quote, Reply, SessionLog

CAR = Document(1, 3, "2022 Car Insurance.pdf")


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box.create(tmp_path / "Box", name="Our box")


def _events(log: SessionLog) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log.events_path.read_text().splitlines()]


def test_a_session_is_named_for_its_time_kind_and_job_and_is_owner_only(box: Box) -> None:
    log = SessionLog(box, 7, "PDF import")
    log.close("done")
    assert log.path.parent == box.logs_dir / "sessions"
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d-\d\d-\d\d PDF import \(job 7\)\.log", log.path.name)
    assert log.events_path == log.path.with_suffix(".jsonl")
    assert stat.S_IMODE(log.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(log.events_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(log.path.parent.stat().st_mode) == 0o700


def test_the_header_names_the_version_the_python_the_packages_and_the_settings(box: Box) -> None:
    import numpy

    settings.save(box, {"workers": 3, "documents.ocr_languages": "eng+por"})
    log = SessionLog(box, 7, "PDF import")
    log.close("done")
    text = log.path.read_text()
    assert f"Caixa {caixa.__version__}" in text
    assert sys.executable in text
    assert f"numpy {numpy.__version__}" in text and "pymupdf " in text
    assert "workers: 3" in text and "eng+por" in text
    assert "embedding model: none" in text  # an empty setting says so
    first = _events(log)[0]
    assert first["event"] == "session" and first["job"] == 7 and first["kind"] == "PDF import"
    assert first["python"] == sys.executable
    assert first["packages"]["numpy"] == numpy.__version__
    assert first["settings"]["workers"] == 3


def test_lines_are_written_as_they_happen_in_both_files(box: Box) -> None:
    log = SessionLog(box, 7, "PDF import")
    log.event(
        "import", "file", CAR, "→ Documents/PDF/Unrecognized/2022 Car Insurance.pdf",
        author=None, date="2022", reasons=["no_author"],
    )  # fmt: skip
    text = log.path.read_text()  # before close
    line = next(line for line in text.splitlines() if "[1/3]" in line)
    assert re.match(r"\d\d:\d\d:\d\d file +\[1/3\] 2022 Car Insurance\.pdf → Documents/", line)
    assert "author: none" in line and "date: 2022" in line and "reasons: no_author" in line
    event = _events(log)[-1]
    assert event["event"] == "file" and event["stage"] == "import"
    assert event["document"] == {"number": 1, "total": 3, "name": "2022 Car Insurance.pdf"}
    assert event["author"] is None and event["reasons"] == ["no_author"]
    log.close("done")


@pytest.mark.parametrize("field", ["text", "page_text", "passage", "passages", "summary"])
def test_page_text_passages_and_summaries_are_refused(box: Box, field: str) -> None:
    log = SessionLog(box, 7, "PDF import")
    with pytest.raises(ValueError, match="never"):
        log.event("read", "propose", CAR, **{field: "Seguros Atlântico, apólice 123"})
    log.close("done")
    assert "apólice" not in log.path.read_text() + log.events_path.read_text()


@pytest.mark.parametrize("kept", [False, True])
def test_quotes_and_replies_are_kept_only_when_the_owner_asks(box: Box, kept: bool) -> None:
    settings.save(box, {"documents.log_quotes": kept})
    log = SessionLog(box, 7, "PDF import")
    log.event(
        "read", "propose", CAR, author="Seguros Atlântico",
        author_quote=Quote("Seguros Atlântico, S.A."), reply=Reply('{"type": "insurance"}'),
    )  # fmt: skip
    log.close("done")
    text, events = log.path.read_text(), _events(log)
    assert "author: Seguros Atlântico" in text
    assert ("Seguros Atlântico, S.A." in text) is kept
    assert ("insurance" in text) is kept
    proposal = next(event for event in events if event["event"] == "propose")
    assert ("author_quote" in proposal and "reply" in proposal) is kept
    assert events[0]["settings"]["documents.log_quotes"] is kept


def test_outside_a_session_the_log_is_quiet(box: Box) -> None:
    quiet = session_log.current()
    quiet.event("import", "file", CAR, author="Seguros Atlântico")
    quiet.error("import", RuntimeError("something unexpected"), CAR)
    quiet.outcome(CAR, "Unrecognized", ["no_author"])
    with quiet.stage("examine"):
        pass
    quiet.close("done")
    assert not (box.logs_dir / "sessions").exists()


def test_the_summary_counts_outcomes_tallies_reasons_and_times_stages(box: Box) -> None:
    log = SessionLog(box, 7, "PDF import")
    with log.stage("examine"):
        pass
    log.outcome(CAR, "Unrecognized", ["no_author"])
    log.outcome(Document(2, 3, "EDP fatura.pdf"), "Unrecognized", ["no_author", "no_date"])
    log.outcome(Document(3, 3, "IRS 2023.pdf"), "filed")
    log.outcome(CAR, "filed")  # read later: where a document ended up is what counts
    log.error("read", TypeError("an unexpected error"), CAR)
    log.close("done")
    text = log.path.read_text()
    summary = text[text.index("summary") :]
    assert "done" in summary
    assert "filed 2" in summary
    assert "Unrecognized 1 (no_author 1, no_date 1)" in summary
    assert re.search(r"examine \d+\.\d s", summary)
    assert "[1/3] 2022 Car Insurance.pdf" in summary and "TypeError: an unexpected error" in summary
    last = _events(log)[-1]
    assert last["event"] == "summary" and last["status"] == "done"
    assert last["outcomes"] == {"filed": 2, "Unrecognized": 1}
    assert last["reasons"] == {"Unrecognized": {"no_author": 1, "no_date": 1}}
    assert set(last["stages"]) == {"examine"}
    assert last["errors"][0]["type"] == "TypeError"


def test_an_error_is_written_with_its_traceback(box: Box) -> None:
    log = SessionLog(box, 7, "PDF import")
    try:
        raise TypeError("normalize() argument 2 must be str, not list")
    except TypeError as error:
        log.error("read", error, CAR)
    text = log.path.read_text()
    assert "TypeError: normalize() argument 2 must be str, not list" in text
    assert "Traceback" in text and "test_an_error_is_written_with_its_traceback" in text
    error_event = _events(log)[-1]
    assert error_event["event"] == "error" and error_event["stage"] == "read"
    assert "Traceback" in error_event["traceback"]
    log.close("failed")


def test_an_open_session_is_current_and_closes_with_the_error(box: Box) -> None:
    with pytest.raises(RuntimeError):
        with session_log.opened(box, 3, "PDF import") as log:
            assert session_log.current() is log
            raise RuntimeError("something unexpected")
    assert session_log.current() is not log
    assert isinstance(log, SessionLog)
    text = log.path.read_text()
    assert "RuntimeError: something unexpected" in text and "Traceback" in text
    assert _events(log)[-1]["status"] == "failed"


def test_a_cancelled_session_says_so(box: Box) -> None:
    from caixa.service import JobCancelled

    with pytest.raises(JobCancelled):
        with session_log.opened(box, 3, "PDF import") as log:
            raise JobCancelled()
    assert isinstance(log, SessionLog)
    assert _events(log)[-1]["status"] == "cancelled"
    assert not any(event["event"] == "error" for event in _events(log))


def test_a_session_that_cannot_be_written_does_not_stop_the_work(
    box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(SessionLog, "__init__", refuse)
    with session_log.opened(box, 3, "PDF import") as log:
        log.event("import", "file", CAR)
    assert type(log) is session_log.QuietLog


# --- Jobs -----------------------------------------------------------------------------------------


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Any]:
    from caixa.service import Service

    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Our box", owner="Maria Costa")
    yield made
    made.close()


def test_only_document_jobs_have_a_session() -> None:
    from caixa.service import session_kind

    assert session_kind({"kind": "import", "collector": "pdf"}) == "PDF import"
    assert session_kind({"kind": "documents-enrich", "collector": "pdf"}) == "documents enrich"
    assert session_kind({"kind": "documents-embed", "collector": "pdf"}) == "documents embed"
    assert session_kind({"kind": "documents-reprocess", "collector": "pdf"}) == (
        "documents reprocess"
    )
    assert session_kind({"kind": "import", "collector": "contacts"}) is None
    assert session_kind({"kind": "mail-import", "collector": "mail"}) is None
    assert session_kind({"kind": "refresh", "collector": None}) is None


def test_a_document_job_that_fails_leaves_a_closed_session_with_the_error(
    service: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caixa.documents import embeddings

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("something unexpected")

    monkeypatch.setattr(embeddings, "embed_documents", broken)
    job = service.documents_embed()
    done = service.wait(job["id"], 60)
    assert done["status"] == "failed"
    (path,) = (tmp_path / "Box" / ".caixa" / "logs" / "sessions").glob("*.log")
    assert path.name.endswith(f"documents embed (job {job['id']}).log")
    text = path.read_text()
    assert "RuntimeError: something unexpected" in text and "Traceback" in text
    last = json.loads(path.with_suffix(".jsonl").read_text().splitlines()[-1])
    assert last["event"] == "summary" and last["status"] == "failed"
