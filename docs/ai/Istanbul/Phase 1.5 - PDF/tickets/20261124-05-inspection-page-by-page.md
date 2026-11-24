---
id: 20261124-05-inspection-page-by-page
title: Inspection page by page
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-04-the-pdf-collector
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

Inspect every page with PyMuPDF and classify it (`text`, `needs_ocr`, `ocr_layer`, `broken_text`, `blank`) from its text quality and image coverage; recognise encrypted and damaged files. Stored on the pages and shown in preview.

## Acceptance criteria

- [ ] Every fixture page gets the class its known answers name
- [ ] Encrypted (password) and damaged files are recognised; an owner-password-only PDF is readable
- [ ] Quality measures and the class are stored per page with the page's own text; preview reports pages likely to need OCR
- [ ] A different file with the same text as a document in the box is flagged `probable_duplicate` for review, never merged

## Context

Phase 1.5 - PDF Tasks Breakdown item 5. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Inspection); D4.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** `caixa/documents/pdf/inspect.py` measures each page with PyMuPDF:

- characters (no spaces);
- the share of bad characters: Private Use Area, U+FFFD, controls;
- the share of word-like tokens among tokens with letters (letters only, at least one vowel or a
  single letter);
- the share of invisible characters (`get_texttrace` type 3);
- image coverage (the union of image boxes over the page);
- drawings.

From these, `classify` decides:

- no text: `blank` (nothing drawn) or `needs_ocr` (pictures or drawings);
- mostly bad characters: `broken_text` (or a poor `ocr_layer` when the text is invisible);
- mostly invisible: `ocr_layer`, `poor` when its words are mostly not words;
- few words among the text: `broken_text`;
- a page covered by a picture with a little text on it: `needs_ocr`;
- else `text`.

The thresholds are constants, set on the fixtures. `inspect_pdf(doc)` returns a `PageInspection`
for every page, with its text.

`examine` (the collector's worker) inspects every readable, unlocked PDF. `Examined` carries the
inspections as plain values and the hash of its normalized text. The import stores each page
(`set_pages`: text, `pdf`, class, quality), sets `ocr_status` (`needs_ocr` when a page is
`needs_ocr`, `broken_text` or a poor `ocr_layer`, else `not_needed`) and `text_hash`. A new file
with the same text as a document already in the box gets `probable_duplicate` in its review
(`needs_review`), and both stay. The preview counts pages that may need OCR.

### T01: Measuring and classifying pages

- `caixa/documents/pdf/__init__.py`, `caixa/documents/pdf/inspect.py` (`PageInspection`,
  `measure`, `classify`, `inspect_pdf`, `text_hash`).
- Tests (`tests/test_pdf_inspect.py`):
  - every page of every readable fixture gets the class its known answers name;
  - the poor OCR layer is marked poor and the good one not;
  - a blank page;
  - the rotated page reads as text;
  - `text_hash` ignores spacing and case, and is None without text.
- Verify: `python -m pytest -q tests/test_pdf_inspect.py`
- [x] done

### T02: Inspection in the import and the preview

- `caixa/collectors/pdfImport.py`: `examine` inspects; the preview counts OCR pages.
- `caixa/documents/importing.py`: pages, `ocr_status`, `text_hash`, `probable_duplicate`.
- Tests (`tests/test_pdf_inspect.py`, `tests/test_pdf_collector.py`):
  - imported documents have their pages with text, class and quality;
  - `ocr_status` is `needs_ocr` for the scans, the mixed file, the broken text and the poor
    layer, and `not_needed` for the rest;
  - the statement saved again is `probable_duplicate`;
  - the preview says how many pages may need OCR.
- Verify: `python -m pytest -q tests/test_pdf_inspect.py tests/test_pdf_collector.py && python -m mypy --python-version 3.12 caixa`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
