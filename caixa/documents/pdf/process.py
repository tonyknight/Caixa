"""OCR and validation of one PDF, as one step: what an import and a reprocess both run.

`ocr_and_validate` OCRs the pages inspection says need it (`caixa.documents.pdf.ocr`) and, when
that wrote a new file, validates it against the original (`caixa.documents.pdf.validate`). A file
that fails validation is never used. It goes, with a `report.json` saying why, to
`<working folder>/failed/<sha256>/`, OCR's status becomes `failed`, and the text OCR read into it is
dropped. The text of pages read without rewriting the file (broken text) is kept, since it never
touched the file.

The result is plain values (it crosses from worker processes).
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from caixa.documents.pdf.ocr import ocr_document
from caixa.documents.pdf.validate import validate

FAILED = "failed"


def _hash(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ocr_and_validate(
    path: Path,
    sha256: str,
    inspection: Sequence[Mapping[str, Any]],
    options: Mapping[str, Any],
) -> dict[str, Any]:
    """OCR then validate `path` (see the module text). `options`: `enabled`, `languages`,
    `workdir` (the job's OCR folder; failed files go beside it, in `failed/`)."""
    workdir = Path(str(options["workdir"]))
    began = time.monotonic()
    outcome = ocr_document(
        path,
        workdir / f"{sha256}.pdf",
        [dict(page) for page in inspection],
        str(options.get("languages") or "eng"),
        bool(options.get("enabled", True)),
    )
    took = round(time.monotonic() - began, 2)
    done: dict[str, Any] = {
        "status": outcome.status,
        "output": None,
        "sha256": None,
        "texts": dict(outcome.texts),
        "mode": outcome.mode,
        "tool": outcome.tool,
        "versions": outcome.versions,
        "settings": outcome.settings,
        "error": outcome.error,
        "validation": None,
        "seconds": took,  # OCR's
    }
    if outcome.output is None:
        return done
    began = time.monotonic()
    checked = validate(path, outcome.output, outcome.settings.get("pages") or [])
    done["validation"] = checked.report()
    done["validate_seconds"] = round(time.monotonic() - began, 2)
    if checked.passed:
        done["output"] = str(outcome.output)
        done["sha256"] = _hash(outcome.output)
        return done
    failed = workdir.parent / FAILED / sha256
    failed.mkdir(parents=True, exist_ok=True)
    shutil.move(str(outcome.output), failed / "output.pdf")
    reasons = [c["name"] for c in done["validation"]["checks"] if not c["passed"]]
    report = {"source": str(path), "sha256": sha256, **done, "output": str(failed / "output.pdf")}
    (failed / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    for number in outcome.settings.get("pages") or []:
        done["texts"].pop(number, None)  # read into a file that is not used
    done["status"] = "failed"
    done["error"] = f"the OCR'd file failed validation ({', '.join(reasons)}); kept in {failed}"
    done["failed"] = str(failed)
    return done


def kept_failure(workdir: Path, sha256: str) -> Optional[Path]:
    """Where a failed OCR output of the file with this hash was kept, if it was."""
    folder = workdir.parent / FAILED / sha256
    return folder if folder.is_dir() else None


__all__ = ["FAILED", "kept_failure", "ocr_and_validate"]
