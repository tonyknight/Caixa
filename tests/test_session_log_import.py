"""Examining, OCR, validation and filing in the session log (20261125-02 T02). Synthetic family
only; reading by a model is off here (it is logged in T03)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from caixa import session_log, settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents.pdf import ocr
from caixa.session_log import SessionLog
from pdf_family import PdfFamily

READABLE = 15  # as in test_pdf_collector
UNREADABLE = {"damaged_scan.pdf", "not_really.pdf"}
FILED_BY_NAME = {
    "2024-11 Banco Atlântico Checking Statement.pdf",
    "2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf",
}
OCR = ocr.tools().ready


@pytest.fixture
def family(pdf_family: PdfFamily, tmp_path: Path) -> Path:
    copy = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, copy)
    (copy / "answers.json").unlink()
    return copy


@pytest.fixture
def box(tmp_path: Path) -> Box:
    made = Box.create(tmp_path / "Box", name="Our box")
    settings.save(made, {"documents.enrich": False})
    return made


def _import(box: Box, folder: Path) -> list[dict[str, Any]]:
    with session_log.opened(box, 1, "PDF import") as log:
        PdfCollector().run(box, folder, {"workers": 1}, lambda step: None)
    assert isinstance(log, SessionLog)
    return [json.loads(line) for line in log.events_path.read_text().splitlines()]


def _by(events: list[dict[str, Any]], name: str) -> dict[str, dict[str, Any]]:
    return {e["document"]["name"]: e for e in events if e["event"] == name}


def test_every_new_file_is_filed_with_what_its_name_and_properties_said(
    family: Path, box: Box
) -> None:
    filed = _by(_import(box, family), "file")
    assert len(filed) == READABLE
    for name, event in filed.items():
        assert event["stage"] == "import" and event["message"].startswith("→ Documents/PDF/")
        assert "filename" in event and "properties" in event
    for name in FILED_BY_NAME:
        assert "/Unrecognized/" not in filed[name]["message"]
        assert set(filed[name]["filed_by"]) == {"date", "title", "author"}
        assert not filed[name].get("why")


def test_each_file_left_in_unrecognized_says_what_was_missing(family: Path, box: Box) -> None:
    filed = _by(_import(box, family), "file")
    unrecognized = {n: e for n, e in filed.items() if "/Unrecognized/" in e["message"]}
    assert len(unrecognized) == READABLE - len(FILED_BY_NAME)
    for name, event in unrecognized.items():
        assert event["why"], name
        assert set(event["why"]) <= {"no_date", "dates_disagree", "no_author", "no_title"}
    assert "no_date" in unrecognized["scan_00482.pdf"]["why"]  # a scanner's name says nothing


def test_unreadable_known_and_locked_files_are_named_as_such(family: Path, box: Box) -> None:
    events = _import(box, family)
    unreadable = _by(events, "unreadable")
    assert set(unreadable) == UNREADABLE
    assert all(e["reason"] for e in unreadable.values())
    known = [e for e in events if e["event"] == "known"]
    assert len(known) == 1  # the exact copy in Arquivo/2024/
    assert _by(events, "file")["extrato_protegido.pdf"]["review"] == ["locked"]


def test_examination_counts_pages_by_class(family: Path, box: Box, pdf_family: PdfFamily) -> None:
    examined = _by(_import(box, family), "examine")
    assert len(examined) == READABLE
    assert examined["extrato_protegido.pdf"]["locked"] is True
    for fixture in pdf_family.documents:
        name = Path(fixture.path).name
        if name not in examined or examined[name].get("locked"):
            continue
        event = examined[name]
        assert sum(event["classes"].values()) == event["pages"] == len(fixture.pages), name
        assert event["seconds"] >= 0


@pytest.mark.skipif(not OCR, reason="OCR tools missing here")
def test_scanned_files_log_ocr_and_validation(family: Path, box: Box) -> None:
    events = _import(box, family)
    done = _by(events, "ocr")["scan_00482.pdf"]
    assert done["status"] == "done" and done["pages"] and done["seconds"] >= 0
    checked = _by(events, "validate")["scan_00482.pdf"]
    assert checked["passed"] is True and checked["failed"] == []
    assert "2024-11 Banco Atlântico Checking Statement.pdf" not in _by(events, "ocr")


def test_the_summary_counts_where_files_went_and_times_the_stages(family: Path, box: Box) -> None:
    summary = _import(box, family)[-1]
    assert summary["event"] == "summary" and summary["status"] == "done"
    assert summary["outcomes"] == {
        "Unrecognized": READABLE - len(FILED_BY_NAME),
        "filed": len(FILED_BY_NAME),
        "unreadable": len(UNREADABLE),
        "already in the box": 1,
    }
    assert sum(summary["reasons"]["Unrecognized"].values()) >= READABLE - len(FILED_BY_NAME)
    assert {"examine", "file", "draw"} <= set(summary["stages"])


def test_the_files_found_and_the_examining_settings_open_the_import(family: Path, box: Box) -> None:
    events = _import(box, family)
    found = next(e for e in events if e["event"] == "found")
    assert found["files"] == READABLE + len(UNREADABLE) + 1
    assert found["workers"] == 1 and "ocr" in found


@pytest.mark.skipif(not OCR, reason="OCR tools missing here")
def test_a_reprocess_logs_what_ocr_and_validation_did(
    pdf_family: PdfFamily, tmp_path: Path
) -> None:
    from caixa.documents.reprocess import reprocess

    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.enrich": False, "documents.ocr": False})
    folder = tmp_path / "scans"
    folder.mkdir()
    shutil.copyfile(pdf_family.root / "scan_00482.pdf", folder / "scan_00482.pdf")
    PdfCollector().run(box, folder, {"workers": 1}, lambda step: None)
    with session_log.opened(box, 2, "documents reprocess") as log:
        reprocess(box, failed_only=True, progress=lambda step: None)
    assert isinstance(log, SessionLog)
    events = [json.loads(line) for line in log.events_path.read_text().splitlines()]
    assert _by(events, "ocr")["scan_00482.pdf"]["status"] == "done"
    assert _by(events, "validate")["scan_00482.pdf"]["passed"] is True
    assert _by(events, "reprocess")["scan_00482.pdf"]["improved"] is True
    assert events[-1]["outcomes"] == {"improved": 1}
