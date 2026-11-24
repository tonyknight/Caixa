"""Validation in the import, what happens when OCR's file fails it, and reprocessing
(ticket 20261124-07)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterator

import pymupdf
import pytest

from caixa import cli, settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import records
from caixa.documents.pdf import ocr
from caixa.documents.reprocess import reprocess
from caixa.service import Service
from pdf_family import PdfFamily

TOOLS = ocr.tools()
pytestmark = pytest.mark.skipif(not TOOLS.ready, reason=f"OCR tools missing: {TOOLS.missing}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def scans(pdf_family: PdfFamily, tmp_path: Path) -> Path:
    """Two scans and a statement: enough to see OCR, validation and reprocessing."""
    folder = tmp_path / "scans"
    folder.mkdir()
    for name in (
        "scan_00482.pdf",
        "download.pdf",
        "2024-11 Banco Atlântico Checking Statement.pdf",
    ):
        shutil.copyfile(pdf_family.root / name, folder / name)
    return folder


def _bad_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """OCRmyPDF "works" but its file has a page drawn over: validation must refuse it."""
    import ocrmypdf

    def spoiled(source: Any, output: Any, **options: Any) -> int:
        doc = pymupdf.open(source)
        for page in doc:
            page.draw_rect(page.rect, color=(1, 1, 1), fill=(1, 1, 1))
        doc.save(output)
        doc.close()
        return 0

    monkeypatch.setattr(ocrmypdf, "ocr", spoiled)


def _documents(box: Box) -> dict[str, dict[str, Any]]:
    with box.master() as master:
        return {
            d["original_filename"]: records.get_document(master, d["item_id"])
            for d in records.list_documents(master)
        }


def _import(box: Box, folder: Path) -> Any:
    return PdfCollector().run(box, folder, {"workers": 1}, lambda step: None)


def test_an_import_validates_what_ocr_wrote(scans: Path, tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    _import(box, scans)
    scan = _documents(box)["scan_00482.pdf"]
    assert scan["ocr_status"] == "done" and scan["validation_status"] == "passed"
    run = next(r for r in scan["runs"] if r["stage"] == "validate")
    assert run["result"] == "passed" and run["report"]["passed"] is True
    statement = _documents(box)["2024-11 Banco Atlântico Checking Statement.pdf"]
    assert not [r for r in statement["runs"] if r["stage"] == "validate"]  # nothing was processed


@pytest.fixture
def failed(scans: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Box]:
    box = Box.create(tmp_path / "Box", name="Our box")
    before = {p.name: (_sha(p), p.stat().st_mtime_ns) for p in scans.iterdir()}
    with monkeypatch.context() as patch:
        _bad_ocr(patch)
        _import(box, scans)
    assert {p.name: (_sha(p), p.stat().st_mtime_ns) for p in scans.iterdir()} == before
    yield box


def test_a_file_that_fails_validation_is_never_used(failed: Box, scans: Path) -> None:
    scan = _documents(failed)["scan_00482.pdf"]
    assert scan["ocr_status"] == "failed" and scan["validation_status"] == "unchanged_copy"
    assert scan["archived_sha256"] == scan["source_sha256"] == _sha(scans / "scan_00482.pdf")
    assert _sha(failed.root / scan["file_path"]) == scan["source_sha256"]
    assert scan["processing_status"] == "needs_review" and "ocr_failed" in scan["review"]
    kept = failed.caixa_dir / "work" / "documents" / "failed" / scan["source_sha256"]
    report = json.loads((kept / "report.json").read_text(encoding="utf-8"))
    assert (kept / "output.pdf").is_file() and report["validation"]["passed"] is False
    assert "appearance" in {c["name"] for c in report["validation"]["checks"] if not c["passed"]}
    run = next(r for r in scan["runs"] if r["stage"] == "validate")
    assert run["result"] == "failed"


def test_reprocessing_once_ocr_works(failed: Box) -> None:
    before = _documents(failed)["scan_00482.pdf"]
    done = reprocess(failed, failed_only=True, progress=lambda step: None)
    assert done["reprocessed"] == 2 and done["improved"] == 2 and done["failed"] == 0
    after = _documents(failed)["scan_00482.pdf"]
    assert after["item_id"] == before["item_id"] and len(_documents(failed)) == 3
    assert after["ocr_status"] == "done" and after["validation_status"] == "passed"
    assert after["review"] == [] and after["processing_status"] == "archived"
    assert after["archived_sha256"] != after["source_sha256"]
    assert _sha(failed.root / after["file_path"]) == after["archived_sha256"]
    with failed.master() as master:
        text = master.connection.execute(
            "SELECT text, source FROM document_pages WHERE item_id = ?", (after["item_id"],)
        ).fetchone()
    assert "77812" in text["text"] and text["source"] == "ocr"
    assert any(r["stage"] == "reprocess" and r["result"] == "done" for r in after["runs"])


def test_reprocessing_names_its_documents(failed: Box) -> None:
    scan = _documents(failed)["scan_00482.pdf"]
    done = reprocess(failed, item_ids=[scan["item_id"]], progress=lambda step: None)
    assert done["reprocessed"] == 1 and done["improved"] == 1


def test_reprocessing_that_fails_again_changes_nothing(
    failed: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _documents(failed)["scan_00482.pdf"]
    _bad_ocr(monkeypatch)
    done = reprocess(failed, failed_only=True, progress=lambda step: None)
    assert done["improved"] == 0 and done["failed"] == 2
    after = _documents(failed)["scan_00482.pdf"]
    assert after["archived_sha256"] == before["archived_sha256"]
    assert after["ocr_status"] == "failed" and "ocr_failed" in after["review"]
    assert [r["result"] for r in after["runs"] if r["stage"] == "reprocess"] == ["failed"]


@pytest.fixture
def service(failed: Box) -> Iterator[Service]:
    made = Service(roots=[failed.root.parent])
    made.box_open(str(failed.root))
    yield made
    made.close()


def test_a_reprocess_job_can_be_undone(service: Service, failed: Box) -> None:
    before = _documents(failed)["scan_00482.pdf"]
    job = service.call("documents.reprocess", {"failed": True})
    done = service.wait(job["id"], 300)
    assert done["status"] == "done", done["error"]
    assert done["result"]["improved"] == 2
    assert _documents(failed)["scan_00482.pdf"]["ocr_status"] == "done"
    undone = service.wait(service.import_undo()["id"], 300)
    assert undone["status"] == "done", undone["error"]
    again = _documents(failed)["scan_00482.pdf"]
    assert again["ocr_status"] == "failed" and again["archived_sha256"] == before["archived_sha256"]
    assert _sha(failed.root / again["file_path"]) == before["archived_sha256"]


def test_the_command_line_reprocesses(failed: Box, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["documents", "reprocess", "--failed", "--box", str(failed.root)]) == 0
    out = capsys.readouterr().out
    assert "2 reprocessed" in out and "2 improved" in out


def test_asking_for_nothing_is_refused(service: Service) -> None:
    from caixa.service import ServiceError

    with pytest.raises(ServiceError) as refused:
        service.call("documents.reprocess", {})
    assert refused.value.kind == "invalid_params"


def test_other_languages_can_be_given(failed: Box) -> None:
    settings.save(failed, {"documents.ocr_languages": "eng"})
    done = reprocess(failed, failed_only=True, languages="eng", progress=lambda step: None)
    assert done["languages"] == "eng"
