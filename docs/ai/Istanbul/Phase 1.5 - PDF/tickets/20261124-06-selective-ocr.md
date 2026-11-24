---
id: 20261124-06-selective-ocr
title: Selective OCR
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: selective OCR with OCRmyPDF, broken pages read only, settings, doctor.'
parent:
depends_on:
- 20261124-05-inspection-page-by-page
subtasks: []
plan_status: done
---
## Description

OCR with OCRmyPDF on only the pages that need it; broken-text pages' OCR text stored without rewriting the page; the `documents.ocr` and `documents.ocr_languages` (`eng`) settings; history; `caixa doctor` checks; the no-OCR path.

## Acceptance criteria

- [x] Scanned and mixed fixtures get a text layer on exactly their scanned pages; digital pages are not rasterized; a good OCR layer is kept
- [x] A broken-text page looks the same and its OCR text is stored as `ocr`
- [x] Without OCRmyPDF or Tesseract the import succeeds and those pages are `needs_ocr`; `caixa doctor` names what to install
- [x] Engine, version and settings recorded in `document_runs`

## Context

Phase 1.5 - PDF Tasks Breakdown item 6. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (OCR), *Pipeline*; D5, D17, D27.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/documents/pdf/ocr.py`.

- `tools()`: whether OCR can run. OCRmyPDF must be importable and Tesseract on the path; it also
  reports their versions, Tesseract's languages and what is missing (with `brew install
  ocrmypdf`).
- `ocr_document(source, output, inspection, languages)`:
  - The pages that need it are OCR'd with OCRmyPDF: `pages=` the `needs_ocr` and poor-layer pages,
    `skip_text` (or `redo_ocr` when a poor layer is among them), `output_type="pdf"`,
    `optimize=0`, one job, OCRmyPDF's logging quiet. The output goes to the job's working folder.
  - `broken_text` pages are not rewritten. A render of each is read by Tesseract through PyMuPDF
    (`get_textpage_ocr`, 300 dpi), and only its text is kept.
  - It returns `OcrOutcome`: status (`not_needed`, `done`, `partial` when an OCR'd page still has
    no text, `needs_ocr` when the tools are missing or OCR is off, `failed`), the output path, the
    text of each page OCR touched, the mode, the tool versions and settings, and an error.
- New box settings in a Documents group of Settings: `documents.ocr` (on) and
  `documents.ocr_languages` (`eng`, decided 2026-11-24).
- The collector's worker (`examine`, given the OCR options and the working folder) runs OCR after
  inspection. The import:
  - copies the OCR output when there is one (archived SHA-256 = the output's), else the source;
  - stores OCR'd pages' text as `ocr`;
  - sets `ocr_status`;
  - records an `ocr` run (tool, versions, settings, result);
  - marks a failed OCR `ocr_failed` for review, archiving the unchanged copy;
  - removes the working outputs.
- `caixa doctor` lists OCRmyPDF, Tesseract (with its languages) and Ghostscript (optional), with
  the Homebrew line.

### T01: OCR of the pages that need it

- `caixa/documents/pdf/ocr.py` (`OcrTools`, `tools`, `OcrOutcome`, `ocr_document`).
- Tests (`tests/test_pdf_ocr.py`; skipped with a reason when OCRmyPDF or Tesseract is missing):
  - the scan and the cheque get a text layer that holds their words;
  - the mixed file is OCR'd on page 2 only, and page 1 keeps its text and gains no picture;
  - the poor layer is redone ("Rental Agreement");
  - the broken page's text is read and the file is not rewritten;
  - a digital PDF needs nothing;
  - missing tools give `needs_ocr` with what to install;
  - a failure gives `failed` and no output.
- Verify: `python -m pytest -q tests/test_pdf_ocr.py`
- [x] done

### T02: OCR in the import, the settings and the doctor

- `caixa/settings.py`: the two settings.
- `caixa/collectors/pdfImport.py`: OCR in the workers.
- `caixa/documents/importing.py`: output, pages, status, run, cleanup.
- `caixa/diagnostics.py`: the OCR programs.
- `web/src/client/pages/SettingsPage.tsx` and `locales.ts`: the Documents group (window rebuilt).
- Tests:
  - an import of the family archives OCR'd copies of the scans (archived hash ≠ source hash,
    words found in their `ocr` pages) and digital PDFs byte for byte;
  - `documents.ocr` off leaves `needs_ocr`;
  - missing tools leave `needs_ocr` and the import succeeds;
  - an OCR run is recorded with OCRmyPDF's version;
  - no working output is left;
  - the doctor lists the OCR programs.
- Verify: `python -m pytest -q tests/test_pdf_ocr.py tests/test_pdf_collector.py tests/test_pdf_inspect.py tests/test_diagnostics.py tests/test_service_box.py && python -m mypy --python-version 3.12 caixa && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** `caixa/documents/pdf/ocr.py` OCRs only the pages inspection says need it, with
  OCRmyPDF: `pages=`, `skip_text`, or `redo_ocr` for a poor layer, a plain PDF output, no
  recompression. On the mixed file the digital page keeps its text and gains no picture.
  Broken-text pages are read by Tesseract through PyMuPDF and their file is not rewritten.
  Without the tools, or with OCR off, pages stay `needs_ocr` and the import goes on.
  - The collector's workers run OCR after inspection.
  - The import files the OCR'd copy (with its own SHA-256) or a byte-for-byte copy, stores OCR
    text as `ocr` pages, sets `ocr_status`, records an `ocr` run with versions and settings, and
    removes working outputs.
  - New settings `documents.ocr` (on) and `documents.ocr_languages` (`eng`) appear in a Documents
    group in Settings.
  - `caixa doctor` lists OCRmyPDF, Tesseract with its languages, and Ghostscript.
- **Files:**
  - new: `caixa/documents/pdf/ocr.py`, `tests/test_pdf_ocr.py`;
  - changed: `caixa/collectors/pdfImport.py`, `caixa/documents/importing.py`,
    `caixa/settings.py`, `caixa/diagnostics.py`, `web/src/client/pages/SettingsPage.tsx`,
    `web/src/client/locales.ts`, the built window;
  - adjusted for OCR being on by default: `tests/test_pdf_collector.py`,
    `tests/test_pdf_inspect.py`.
- **Errors:** none in the code. Five earlier tests assumed no OCR ran; the inspection tests now
  import with OCR off, and the collector's byte-for-byte check applies where OCR changed nothing.
- **Verify:**
  - `python -m pytest -q`: 1684 passed, 1 skipped.
  - vitest: 277 passed; tsc clean; window rebuilt.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: 0fb4185..f25c760 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** whether Ghostscript is needed for plain PDF output with OCRmyPDF 17 is not settled
  here, since it was installed. The doctor calls it optional; check on the Mac without it.
- **Minor:** OCRmyPDF reads the original and writes only into the job's working folder; no
  separate working copy of the original is made, since nothing writes to it.
- **Minor:** OCR runs in the same worker processes as inspection, one OCRmyPDF job each, so a
  large scanned PDF holds one worker for its whole OCR.
- **Spec:** D5, D17 and D27 (doctor) met; every acceptance criterion met.
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.pdf.ocr`; the import tests failing before
  the wiring) before each GREEN.
- **Commits:** `20261124-06 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
