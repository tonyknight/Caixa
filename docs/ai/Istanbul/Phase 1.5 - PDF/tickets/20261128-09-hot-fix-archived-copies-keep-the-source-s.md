---
id: 20261128-09-hot-fix-archived-copies-keep-the-source-s
title: 'Hot fix: archived copies keep the source''s metadata and dates'
type: bug
priority: high
status: done
created: 2026-11-28
updated: 2026-11-28
closed: 2026-11-28
notes: OCR'd copies keep the source's metadata; every copy keeps its source's date
parent:
depends_on: []
subtasks: []
plan_status: done
current_task: T01
---
## Description

An OCR'd archived copy is OCRmyPDF's output, and OCRmyPDF rewrites its metadata. Reproduced on a
synthetic scan:

- Creator becomes `OCRmyPDF 17.14.2 / OCRmyPDF fpdf2 + Tesseract OCR …`;
- Producer becomes `pikepdf …`;
- ModDate becomes the import's;
- an XMP stream is added (CreatorTool OCRmyPDF, ModifyDate and MetadataDate the import's).

macOS shows such a Creator as the file's "Authors". Every archived copy, OCR'd or not, also has
the import's time as its file date, because the copy does not carry the source's dates. The
sources themselves are only read. The maintainer judged this unwise: a copy for the archive should
say what the original said.

## Acceptance criteria

- [x] An OCR'd copy has the source's document information and XMP exactly as the source has them
      (no XMP where the source has none); only its text layer differs.
- [x] This is done before the copy is validated and hashed, so the archived hash is the restored
      copy's.
- [x] Every archived copy has the source's modification time.

## Context

Requirements: D3 and D4 (the originals unchanged, a validated searchable copy). The copies already
in a box are a separate step, its command named by the maintainer.

## Subtasks

## Implementation plan

Status: done
Current task: T01

**Design:**

- `ocr.restore_metadata(source, output)` (pikepdf): the output's trailer `/Info` becomes a copy
  of the source's, or none when the source has none, and its `/Root /Metadata` a copy of the
  source's XMP, or none. It is saved in place without pikepdf's own metadata handling, so nothing
  is added. `ocr_document` calls it on its output, before `process` validates and hashes it.
- `archive.copy_into(…, modified=…)` sets the archived file's modification time
  (`os.utime`). `import_examined` gives it the source's.

### T01: The OCR'd copy's metadata, and the copies' dates

- `caixa/documents/pdf/ocr.py`, `caixa/documents/archive.py`, `caixa/documents/importing.py`,
  `tests/test_pdf_ocr.py`.
- Tests:
  - a scan with Author, Title, Creator, Producer and dates, and one with XMP, keep them all
    through OCR, with no XMP added to the first;
  - an import's archived copy, OCR'd or not, has the source's metadata and modification time.
- Verify: `python -m pytest -q tests/test_pdf_ocr.py tests/test_pdf_collector.py tests/test_pdf_validate.py`
- [x] done

## Completion report

- **Outcome:**
  - **Metadata:** `ocr.restore_metadata` gives an OCR'd copy the source's document information
    and XMP exactly as the source has them, and removes the XMP OCRmyPDF added where the source
    had none. It saves in place, without pikepdf's metadata handling. `ocr_document` calls it
    before `process` validates and hashes the copy, so the archived hash is the restored copy's.
    If it cannot be done, OCR counts as failed and the source is archived unchanged. Only the
    text layer differs from the source. Reprocessing goes through the same step.
  - **Dates:** `archive.copy_into(…, modified=…)` gives every archived copy, OCR'd or not, the
    source's modification time; `import_examined` passes it.
- **Files:** `caixa/documents/pdf/ocr.py`, `caixa/documents/archive.py`,
  `caixa/documents/importing.py`, `tests/test_pdf_ocr.py`, `tests/test_pdf_collector.py` (a
  stand-in's signature).
- **Errors:**
  - A key whose value is null (`/Keywords null`) is not carried over: the PDF format treats it
    as absent, and the test compares what the metadata says.
  - macOS's creation date cannot be set from Python, so it stays the import's.
- **Verify:**
  - `python -m pytest -q tests/test_pdf_ocr.py tests/test_pdf_collector.py tests/test_pdf_validate.py`:
    61 passed.
  - mypy: the 8 baseline errors.
  - The full suite is not run, per the maintainer's instruction.

## Review

### 2026-11-28: reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** copies already in a box keep OCRmyPDF's metadata until restored. That needs a
  command whose name is the maintainer's to give.
- **Minor:** the document ID in the trailer (`/ID`) is OCRmyPDF's; it identifies the file's
  version, not its content's source, and is left as is.
- **Spec:** D3 and D4 met; every acceptance criterion met.
- **TDD:** RED (Creator, Producer, ModDate and XMP rewritten; the copies' dates the import's)
  before GREEN.

## Notes

Append-only running log. Each entry dated.
