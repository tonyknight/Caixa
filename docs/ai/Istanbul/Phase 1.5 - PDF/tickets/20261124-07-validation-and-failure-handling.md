---
id: 20261124-07-validation-and-failure-handling
title: Validation and failure handling
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-06-selective-ocr
subtasks: []
plan_status: done
---
## Description

Validate every processed PDF (structure with PyMuPDF and pikepdf, content, appearance) before it is accepted; on failure archive the unchanged copy, keep the failed output, mark for review; `caixa documents reprocess`.

## Acceptance criteria

- [ ] Every OCR'd fixture passes; page count, order, sizes, rotation and appearance match within tolerance
- [ ] A forced failure archives the unchanged copy (archived hash = source hash), keeps output and report in `.caixa/work/documents/failed/<id>/`, and puts the document in To review
- [ ] `caixa documents reprocess` (and `documents.reprocess`) succeeds once the cause is gone, without a duplicate record

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

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
