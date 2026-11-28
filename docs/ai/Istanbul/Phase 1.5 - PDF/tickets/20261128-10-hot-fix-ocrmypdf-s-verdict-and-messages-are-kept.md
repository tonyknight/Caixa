---
id: 20261128-10-hot-fix-ocrmypdf-s-verdict-and-messages-are-kept
title: 'Hot fix: OCRmyPDF''s verdict and messages are kept with their file'
type: bug
priority: medium
status: done
created: 2026-11-28
updated: 2026-11-28
closed: 2026-11-28
notes: OCRmyPDF's verdict and messages kept with their file, not printed
parent:
depends_on: []
subtasks: []
plan_status: done
current_task: T01
---
## Description

During the maintainer's import, the terminal showed a bare
`ERROR: stream 414 0 R (/JPXDecode) could not be decoded: tile cannot extend outside image`.

- **Where it comes from:** OCRmyPDF checks every stream of its output after OCR (Pillow could not
  decode one JPEG 2000 image). It then *returns* `ExitCode.invalid_output_pdf` instead of raising,
  and Caixa ignores the returned code; Caixa's own validation then decides on the copy.
- **Why it was bare:** Caixa sets OCRmyPDF's logger to errors only, with no handler, so Python's
  last-resort handler prints them to the terminal, with no file or job named.

## Acceptance criteria

- [x] OCRmyPDF's returned code is read. One other than `ok` is noted on the OCR outcome, its run
      record and the session log ("OCRmyPDF judged its output …"); Caixa's validation still
      decides on the copy.
- [x] OCRmyPDF's warnings and errors during a file's OCR are kept with that file, on its run
      record and in the session log, and are not printed to the terminal.

## Context

Requirements: D16 (*Pipeline, statuses and failure*), D26 (the session log: errors are always
allowed in it; no page text).

## Subtasks

## Implementation plan

Status: done
Current task: T01

**Design** (`caixa/documents/pdf/ocr.py`, `process.py`, `importing.py`):

- `OcrOutcome.notes`, a list of strings.
- Around `ocrmypdf.ocr`, a handler on the `ocrmypdf` logger collects the warnings and errors into
  the notes, with `propagate` off, so nothing reaches the terminal. Both are restored afterwards.
- A returned code other than `ok` adds "OCRmyPDF judged its output <name>; Caixa's validation
  decides" to the notes.
- `process` carries `notes` into the examined file's OCR record. `import_examined` puts them in
  the OCR run's report, and `log_examination` in the session log's `ocr` event.

### T01: The verdict and the messages, with their file

- `caixa/documents/pdf/ocr.py`, `caixa/documents/pdf/process.py`,
  `caixa/documents/importing.py`, `tests/test_pdf_ocr.py`.
- Tests, with OCRmyPDF stood in for (it logs an error and returns `invalid_output_pdf`):
  - the outcome's notes hold the message and the verdict, and nothing reaches standard error;
  - an import keeps them on the OCR run's report and in the session log, by the file's name.
- Verify: `python -m pytest -q tests/test_pdf_ocr.py tests/test_pdf_collector.py tests/test_session_log_import.py`
- [x] done

## Completion report

- **Outcome:**
  - **Messages:** OCRmyPDF's warnings and errors during a file's OCR are collected by a handler
    on its logger (`propagate` off), so nothing reaches the terminal. The logger is put back as
    it was afterwards.
  - **Verdict:** its returned code is read. One other than `ok` adds "OCRmyPDF judged its output
    <name>; Caixa's validation decides" to `OcrOutcome.notes`. Caixa's validation still decides
    whether the OCR'd copy is used.
  - **Where they go:** the notes travel in the examined file's OCR record to the OCR run's report
    and to the session log's `ocr` event, by the file's name. A failed OCR keeps its notes too.
- **Files:** `caixa/documents/pdf/ocr.py`, `caixa/documents/pdf/process.py`,
  `caixa/documents/importing.py`, `tests/test_pdf_ocr.py`.
- **Errors:** none.
- **Verify:**
  - `python -m pytest -q tests/test_pdf_ocr.py tests/test_pdf_collector.py tests/test_session_log_import.py`:
    53 passed.
  - mypy: the 8 baseline errors.
  - The full suite is not run, per the maintainer's instruction.

## Review

### 2026-11-28: reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** OCRmyPDF's messages are about the file's structure (streams, fonts, images), not its
  text. They are kept as written, so a future OCRmyPDF that quoted page text would put it in the
  session log.
- **Minor:** OCR runs in worker processes, so the handler is installed in each worker, around
  each file.
- **Spec:** D16 and D26 met; every acceptance criterion met.
- **TDD:** RED (no `notes`; the message printed to standard error) before GREEN.

## Notes

Append-only running log. Each entry dated.
