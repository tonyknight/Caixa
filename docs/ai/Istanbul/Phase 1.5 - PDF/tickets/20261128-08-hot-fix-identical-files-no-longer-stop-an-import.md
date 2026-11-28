---
id: 20261128-08-hot-fix-identical-files-no-longer-stop-an-import
title: 'Hot fix: identical files no longer stop an import'
type: bug
priority: high
status: done
created: 2026-11-28
updated: 2026-11-28
closed: 2026-11-28
notes: Identical files share no working copy; one filing error no longer ends an import
parent:
depends_on: []
subtasks: []
plan_status: done
current_task: T01
---
## Description

The maintainer's import of 2,116 PDFs stopped at the end with `OSError: The copy of
<sha256>.pdf does not match it; nothing was filed.` It was reproduced with two copies of one
scanned PDF.

- **Cause:** OCR's working copy is named after the source's hash (`process.py`), so two files
  with the same bytes are OCR'd into one working file. OCRmyPDF's output differs on every run (its
  dates and IDs), so the second overwrites the first's with other bytes. When the first is filed,
  the copy no longer holds the hash recorded for it, and `copy_into` refuses it.
- **Why the whole import stopped:** an error while filing one document is not caught. The
  earlier hot fix `20261125-03` covered examining and reading, not filing.

## Acceptance criteria

- [x] Two files with the same bytes import: one document, both sources recorded; the import
      finishes.
- [x] A second copy of the same bytes is not OCR'd again.
- [x] Each file's OCR working copy is its own.
- [x] An error filing one document is a warning naming the file and the error; nothing of it is
      left half-written (no record, no archived file); the import goes on and finishes.

## Context

Requirements: D16/D17 (*Pipeline, statuses and failure*), as with `20261125-03`.

## Subtasks

## Implementation plan

Status: done
Current task: T01

**Design:**

- `process.ocr_and_validate`: the working copy is
  `<workdir>/<sha256>-<first 12 of the SHA-1 of the source's path>.pdf`.
- `pdfImport._examine_all`: before examining, the files that share a size are hashed. A file
  whose bytes an earlier file in the list has is examined without OCR. It is filed as "already in
  the box" (a second source of the first), so it needs none. Each worker is given `(file, ocr)`.
- `importing.import_examined`: each document's filing runs in a `try`. `Cancelled` passes. Any
  other error rolls the master back to the last commit, removes the archived file if this filing
  copied it, adds a warning (`<name>: could not be filed (<Type>: <message>)`), logs it on the
  document, and goes on.

### T01: Identical files, and one filing error

- `caixa/documents/pdf/process.py`, `caixa/collectors/pdfImport.py`,
  `caixa/documents/importing.py`, `tests/test_pdf_collector.py`.
- Tests:
  - two copies of one scan import as one document with two sources, OCR'd once;
  - two different files get two working copies;
  - a filing that fails for one file leaves a warning and no trace, and the others are filed.
- Verify: `python -m pytest -q tests/test_pdf_collector.py tests/test_pdf_ocr.py tests/test_pdf_validate.py`
- [x] done

## Completion report

- **Outcome:**
  - **Working copies:** each file's OCR working copy is its own,
    `<sha256>-<12 of the SHA-1 of its path>.pdf`.
  - **Second copies:** a file whose bytes an earlier file in the folder has is examined without
    OCR, and filed as a second source of the first. Only files of the same size are hashed for
    this.
  - **Filing errors:** an error filing one document no longer ends the import. The master is
    rolled back to the last document, the file this filing wrote (if any) is removed, a warning
    names the file and the error, the session log says "not filed", and the import goes on.
    `Cancelled` still stops it.
  - The maintainer's case, two copies of one scan, now imports: one document, two sources, OCR'd
    once.
- **Files:** `caixa/documents/pdf/process.py`, `caixa/collectors/pdfImport.py` (`_second_copies`,
  `_examine_one`), `caixa/documents/importing.py`, `tests/test_pdf_collector.py`.
- **Errors:**
  - A patch script with a syntax error ran nothing and was rerun.
  - The first cleanup missed a file written by a copy that then failed; the target is now noted
    before the copy.
- **Verify:**
  - `python -m pytest -q tests/test_pdf_collector.py tests/test_pdf_ocr.py tests/test_pdf_validate.py`:
    58 passed.
  - mypy: the 8 baseline errors.
  - The full suite is not run, per the maintainer's instruction.

## Review

### 2026-11-28: reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** a file failed in OCR's validation is kept in `failed/<sha256>/`, so two identical
  files that both fail share that folder; only the first is OCR'd now, so this no longer arises
  in one import.
- **Minor:** files of the same size are hashed twice (once to find second copies, once when
  examined).
- **Spec:** the pipeline's failure rules (one file's problem is that file's) met; every
  acceptance criterion met.
- **TDD:** RED (the reproduction's `OSError`; one shared working copy; the import stopped by one
  file) before GREEN.

## Notes

Append-only running log. Each entry dated.
