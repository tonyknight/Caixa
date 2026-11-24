"""Processing documents again: OCR that failed, was partial, or could not run when they came in.

The archived file is what is read, so the original need not still exist. When OCR failed, the box
holds an unchanged copy of the original, so nothing is lost. Each document is inspected, OCR'd
(with other languages if given) and validated, as at import (`caixa.documents.pdf.process`):

- a better file (it passed validation) replaces the archived one, through a checked `.part`
  file; its hash, pages, OCR and validation statuses and review follow;
- otherwise the document stays as it was, and the new failure is recorded.

Each attempt is a `reprocess` run. The document keeps its record and identity (its original's
SHA-256), so nothing is duplicated. `keep` (undo's `keep_file`) is told about each file before it
is replaced, so undoing the job puts the earlier version back.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from caixa import __version__, settings
from caixa.box import Box
from caixa.collectors.base import Progress
from caixa.documents import records
from caixa.documents.archive import copy_into

#: The review reasons a successful reprocess takes away.
CLEARED = ("ocr_failed",)


def _candidates(box: Box, item_ids: Optional[Sequence[str]], failed_only: bool) -> list[str]:
    with box.master(read_only=True) as master:
        if item_ids:
            known = {
                r[0]
                for r in master.connection.execute(
                    f"SELECT item_id FROM documents WHERE item_id IN "
                    f"({', '.join('?' for _ in item_ids)})",
                    list(item_ids),
                )
            }
            return [item for item in item_ids if item in known]
        if not failed_only:
            return []
        return [
            r[0]
            for r in master.connection.execute(
                "SELECT item_id FROM documents WHERE ocr_status IN ('failed', 'partial', "
                "'needs_ocr') OR validation_status = 'unchanged_copy' ORDER BY created_at"
            )
        ]


def reprocess(
    box: Box,
    item_ids: Optional[Sequence[str]] = None,
    failed_only: bool = False,
    languages: Optional[str] = None,
    progress: Callable[[Progress], None] = lambda step: None,
    keep: Optional[Callable[[str], None]] = None,
) -> dict[str, Any]:
    """Reprocess the documents named, or (`failed_only`) every one OCR could still improve."""
    from caixa.collectors.pdfImport import examine

    chosen = _candidates(box, item_ids, failed_only)
    saved = settings.load(box)
    language = languages or str(saved.get("documents.ocr_languages") or "eng")
    options = {
        "enabled": True,  # asked for by name: done even when OCR is off for imports
        "languages": language,
        "workdir": str(box.work_dir("documents") / "ocr"),
    }
    result: dict[str, Any] = {"reprocessed": 0, "improved": 0, "failed": 0, "languages": language}
    for number, item_id in enumerate(chosen, start=1):
        with box.master() as master:
            record = records.load_record(master, item_id)
        archived = box.root / record.file_path
        progress(Progress("reprocessing", number, len(chosen), Path(record.file_path).name))
        seen = examine(archived, ocr=options)
        done = seen.ocr or {}
        output = Path(done["output"]) if done.get("output") else None
        status = str(done.get("status") or "failed")
        improved = status in ("done", "partial", "not_needed") and not (
            done.get("validation") and not done["validation"]["passed"]
        )
        with box.master() as master:
            if improved:
                if output is not None:
                    if keep is not None:
                        keep(record.file_path)
                    copy_into(box, output, record.file_path + ".new", str(done["sha256"]))
                    (box.root / (record.file_path + ".new")).replace(archived)
                    output.unlink(missing_ok=True)
                texts = {int(n): t for n, t in (done.get("texts") or {}).items()}
                review = [reason for reason in record.review if reason not in CLEARED]
                changed = replace(
                    record,
                    archived_sha256=(
                        str(done["sha256"]) if output is not None else record.archived_sha256
                    ),
                    ocr_status=status,
                    validation_status="passed",
                    review=review,
                    processing_status="needs_review" if review else "archived",
                    text_hash=seen.text_hash or record.text_hash,
                )
                records.save_document(master, changed, None)
                records.set_pages(
                    master,
                    item_id,
                    [
                        records.PageText(
                            page["number"],
                            texts.get(page["number"], page["text"]),
                            "ocr" if page["number"] in texts else "pdf",
                            page["page_class"],
                            page["quality"],
                        )
                        for page in seen.inspection
                    ],
                )
                failed_folder = box.work_dir("documents") / "failed" / seen.sha256
                if failed_folder.is_dir():  # the earlier failure is past
                    import shutil

                    shutil.rmtree(failed_folder, ignore_errors=True)
                result["improved"] += 1
            else:
                result["failed"] += 1
            records.add_run(
                master, item_id, "reprocess", status if improved else "failed",
                tool=done.get("tool") or "caixa",
                version=(done.get("versions") or {}).get("ocrmypdf") or __version__,
                settings={**(done.get("settings") or {}), "versions": done.get("versions")},
                report={"error": done.get("error"), "validation": done.get("validation")},
            )  # fmt: skip
        result["reprocessed"] += 1
    return result


__all__ = ["reprocess"]
