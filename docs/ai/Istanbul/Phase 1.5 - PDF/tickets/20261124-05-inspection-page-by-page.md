---
id: 20261124-05-inspection-page-by-page
title: Inspection page by page
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: page classes and quality, stored with page text; probable duplicates.'
parent:
depends_on:
- 20261124-04-the-pdf-collector
subtasks: []
plan_status: done
---
## Description

Inspect every page with PyMuPDF and classify it (`text`, `needs_ocr`, `ocr_layer`, `broken_text`, `blank`) from its text quality and image coverage; recognise encrypted and damaged files. Stored on the pages and shown in preview.

## Acceptance criteria

- [x] Every fixture page gets the class its known answers name
- [x] Encrypted (password) and damaged files are recognised; an owner-password-only PDF is readable
- [x] Quality measures and the class are stored per page with the page's own text; preview reports pages likely to need OCR
- [x] A different file with the same text as a document in the box is flagged `probable_duplicate` for review, never merged

## Context

Phase 1.5 - PDF Tasks Breakdown item 5. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Inspection); D4.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

## Completion report

- **Outcome:** `caixa/documents/pdf/inspect.py` measures every page and classifies it as text,
  needs_ocr, ocr_layer (poor or not), broken_text or blank. The measures are characters, bad
  characters, word-like tokens, invisible text (text trace type 3), image coverage and drawings.
  Every fixture page gets its known class. The collector's workers inspect each readable PDF. The
  import stores each page's text, class and quality, sets `ocr_status` and a fingerprint of the
  text, and marks a different file with the same text `probable_duplicate` (both kept). The
  preview says how many pages may need OCR.
- **Files:**
  - new: `caixa/documents/pdf/__init__.py`, `caixa/documents/pdf/inspect.py`,
    `tests/test_pdf_inspect.py`;
  - changed: `caixa/collectors/pdfImport.py`, `caixa/documents/importing.py`,
    `caixa/documents/records.py` (`find_by_text`).
- **Errors:** one mypy `no-any-return` from PyMuPDF's rectangle area, fixed.
- **Verify:**
  - `python -m pytest -q`: 1671 passed, 1 skipped.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: f6eb4ae..e1ae2f6 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** the word-like test knows Latin vowels only. Text in other scripts (Greek, Cyrillic,
  CJK) would be judged broken. Revisit if such PDFs turn up.
- **Minor:** image coverage for several pictures is estimated on a 40×40 grid, which is
  enough to tell a scan from a logo.
- **Minor:** page text crosses the process boundary in `Examined`; a very large PDF carries all
  its text through the pool once.
- **Spec:** D4 met; every acceptance criterion met (including the probable-duplicate rule from
  *Pipeline*).
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.pdf`; the import tests failing before the
  wiring) before each GREEN.
- **Commits:** `20261124-05 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
