---
id: 20261124-07-validation-and-failure-handling
title: Validation and failure handling
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: validation of OCR output, unchanged-copy fallback, failed artifacts,
  undoable reprocess.'
parent:
depends_on:
- 20261124-06-selective-ocr
subtasks: []
plan_status: done
---
## Description

Validate every processed PDF (structure with PyMuPDF and pikepdf, content, appearance) before it is accepted; on failure archive the unchanged copy, keep the failed output, mark for review; `caixa documents reprocess`.

## Acceptance criteria

- [x] Every OCR'd fixture passes; page count, order, sizes, rotation and appearance match within tolerance
- [x] A forced failure archives the unchanged copy (archived hash = source hash), keeps output and report in `.caixa/work/documents/failed/<id>/`, and puts the document in To review
- [x] `caixa documents reprocess` (and `documents.reprocess`) succeeds once the cause is gone, without a duplicate record

## Context

Phase 1.5 - PDF Tasks Breakdown item 7. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Validation), *Pipeline* step 5; D6, D7.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/documents/pdf/validate.py`, `validate(source, output, ocr_pages)` returns
`Validation(passed, checks)`, each check with a name, whether it passed and a detail:

- **Structure:**
  - the output exists and is not empty;
  - it opens in PyMuPDF without being repaired;
  - it needs no password;
  - pikepdf (an independent parser, installed with OCRmyPDF) opens it and `check()` reports no
    problems. Without pikepdf the check is marked skipped, not failed.
- **Content:**
  - the same page count;
  - each page's size and rotation the same (half a point of tolerance);
  - pages that had text keep that text on the same page (their order);
  - OCR'd pages have text;
  - no page has fewer pictures.
- **Appearance:** each page is rendered at 40 dpi in grey from both files. The mean difference
  must stay within `MEAN_TOLERANCE` (2.0 of 255) and every 16-pixel block within
  `BLOCK_TOLERANCE` (24), so a blank or changed page fails.

The worker validates OCR output right after OCR.

- **Failed:** the output and a `report.json` go to `.caixa/work/documents/failed/<sha256>/`, OCR's
  status becomes `failed`, and the unchanged copy is archived (`validation_status`
  `unchanged_copy`, review `ocr_failed`).
- **Passed:** `validation_status` is `passed`. A `validate` run records the checks either way.

`caixa/documents/reprocess.py` reprocesses documents whose OCR failed, is partial or still
needed. Its input is the archived copy (the unchanged one when OCR failed), so the original need
not still exist. The steps are inspect, OCR (other languages may be given), validate, then:

- on success, replace the archived file through a checked `.part` file and update hashes, pages,
  statuses and review, with a `reprocess` run;
- otherwise leave the document as it was, with the new failure recorded.

It runs as a job (`documents.reprocess`, `caixa documents reprocess [ids…] [--failed]
[--languages]`), undoable like an import.

### T01: Validating a processed PDF

- `caixa/documents/pdf/validate.py` (`Check`, `Validation`, `validate`).
- Tests (`tests/test_pdf_validate.py`):
  - every OCR'd fixture passes;
  - a file that is empty, not a PDF, missing a page, with a page resized or rotated, with a page
    blanked or drawn over, with text dropped from a digital page, or with no text where OCR ran
    fails the right check;
  - a page reordering fails;
  - pikepdf's problems are reported.
- Verify: `python -m pytest -q tests/test_pdf_validate.py`
- [x] done

### T02: Validation in the import, failure handling and reprocessing

- `caixa/collectors/pdfImport.py`: validate after OCR, and keep failed artifacts.
- `caixa/documents/importing.py`: statuses, `validate` run.
- `caixa/documents/reprocess.py`.
- `caixa/service.py`: `documents.reprocess`, job kind `documents-reprocess` with undo.
- `caixa/cli.py`: `caixa documents reprocess`.
- `tests/test_worker_protocol.py`: the method is listed.
- Tests:
  - an import validates every OCR'd document (`passed`, a `validate` run);
  - a forced bad OCR output (a page dropped) archives the unchanged copy, keeps the output and
    report under `failed/`, marks the document for review, and leaves the original untouched;
  - reprocessing it once OCR works gives `done`/`passed`, replaces the file, adds a `reprocess`
    run, creates no new record and clears `ocr_failed`;
  - `--failed` picks such documents;
  - undo puts the reprocessed file back;
  - the command line reprocesses and reports.
- Verify: `python -m pytest -q tests/test_pdf_validate.py tests/test_pdf_ocr.py tests/test_pdf_collector.py tests/test_worker_protocol.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:** `caixa/documents/pdf/validate.py` checks every OCR'd file against its
  original before it is accepted:
  - structure: exists, opens unrepaired, unlocked, and pikepdf's `check_pdf_syntax` (errors fail,
    warnings are noted);
  - content: page count, sizes and rotation, the text of untouched pages on the same page, text
    where OCR ran, no lost pictures;
  - appearance: 40 dpi grey renders, by mean and by 16-pixel blocks.

  `caixa/documents/pdf/process.py` runs OCR then validation in the workers. A failing output goes
  with its `report.json` to `.caixa/work/documents/failed/<sha256>/`, the unchanged copy is
  archived (`unchanged_copy`, `ocr_failed` for review), and a `validate` run records the checks.
  `caixa/documents/reprocess.py` (job `documents.reprocess`, `caixa documents reprocess [ids]
  [--failed] [--languages]`) works from the archived copy and replaces it only with a validated
  file. The record and identity are kept, the review is cleared, and a `reprocess` run is added.
  The job is undoable: `undo.keep_file` saves a file before it is replaced.
- **Files:**
  - new: `caixa/documents/pdf/validate.py`, `caixa/documents/pdf/process.py`,
    `caixa/documents/reprocess.py`, `tests/test_pdf_validate.py`, `tests/test_pdf_reprocess.py`;
  - changed: `caixa/collectors/pdfImport.py`, `caixa/documents/importing.py`,
    `caixa/documents/records.py` (`load_record`), `caixa/undo.py` (`keep_file`),
    `caixa/service.py`, `caixa/cli.py`, `tests/test_worker_protocol.py`.
- **Errors:**
  - pikepdf 10 names its check `check_pdf_syntax` (not `check`), which is used when present.
  - Undo did not restore a file replaced in place, so `keep_file` was added.
  - The protocol's lists of methods and write methods gained `documents.reprocess`.
- **Verify:**
  - `python -m pytest -q`: 1711 passed, 1 skipped.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: 5c43a58..85e833f (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** the appearance tolerances (mean 2.0, block 24 of 255 at 40 dpi) were set on
  synthetic scans; real colour scans may need them revisited.
- **Minor:** the text check skips OCR'd pages (their old invisible text may be replaced), so a
  poor layer redone is judged by `ocr_text` and appearance only.
- **Minor:** reprocessing writes `<name>.new` beside the archived file for a moment before
  replacing it.
- **Spec:** D6 and D7 met; every acceptance criterion met (including undo of a reprocess).
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.pdf.validate`, then
  `caixa.documents.reprocess`) before each GREEN.
- **Commits:** `20261124-07 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
