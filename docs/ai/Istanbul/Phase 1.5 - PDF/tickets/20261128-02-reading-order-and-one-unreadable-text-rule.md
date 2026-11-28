---
id: 20261128-02-reading-order-and-one-unreadable-text-rule
title: Reading order and one unreadable-text rule
type: feature
priority: high
status: in-progress
created: 2026-11-28
updated: 2026-11-28
closed:
notes: ''
parent:
depends_on: []
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

The first part of folding `prepare` into the import (D31). Two changes to inspection: page text
is extracted in reading order wherever it is stored, and one rule decides unreadable text.

- **Reading order.** Inspection stores `page.get_text()` in the PDF's stream order, so a page
  drawn bottom-first keeps its closing before its letterhead. `prepare` reads `sort=True`.
- **Unreadable text.** A layer of digits and punctuation is called `text` today: with fewer than
  20 letters, the word-share test is skipped. `prepare` OCRs any page with fewer than 20 letters,
  so a short page of real words is OCR'd too. One rule replaces both.

## Acceptance criteria

- [ ] Page text is stored in reading order: the PDF's text, the OCR layer's text, and the OCR of
      a broken page.
- [ ] A text layer of mostly digits and punctuation is `broken_text`: read by OCR from a render,
      with the page unchanged.
- [ ] A short page of real words stays `text` and is not OCR'd.
- [ ] `prepare` uses the same rule.

## Context

Requirements: D31 (*Preprocessing, stored for every use*); Tasks Breakdown 27.

## Subtasks

## Implementation plan

Status: in-progress
Current task: T02

**Design:**

- `caixa/documents/pdf/inspect.py`:
  - `inspect_pdf` stores `page.get_text(sort=True)`; `measure` counts the same text (order does
    not change its counts).
  - New measure `letter_share` (letters among visible characters), with constants `NOT_WORDS_MIN
    = 15` visible characters and `LETTER_SHARE = 0.25`. In `classify`, a page that is not
    measurable (fewer than `MEASURABLE` letters), has at least `NOT_WORDS_MIN` visible characters,
    and whose letters are under `LETTER_SHARE` of them is `broken_text`. It is checked after the
    bad-character and invisible-layer rules, so an OCR layer stays `ocr_layer`.
  - A short page of words (`Receipt Thank you`: letter share 1.0) stays `text`.
- `caixa/documents/pdf/ocr.py`: the OCR of a broken page, and the text of an OCR layer, are read
  with `sort=True`.
- `caixa/documents/prepare.py`: `_not_words` is replaced by inspection's rule (`measure` and
  `classify` say `broken_text`), so the dry run and the import agree. Its `sort=True` reading
  stays. (Ticket 06 moves `prepare` onto the import's steps.)
- **Known effect:** a document's text hash (`probable_duplicate`) is taken from its text, so a
  document imported before this change and the same file imported after may differ in hash
  order. The hash ignores spacing and case, not order; this is noted, not changed.

### T01: Reading order and the rule in inspection

- `caixa/documents/pdf/inspect.py`, `tests/test_pdf_inspect.py`.
- Tests:
  - a page drawn bottom-first is stored top-first;
  - a digits-and-punctuation layer is `broken_text`;
  - a short page of words is `text`;
  - an OCR layer of digits stays `ocr_layer`;
  - every fixture page keeps its known class.
- Verify: `python -m pytest -q tests/test_pdf_inspect.py tests/test_pdf_family.py`
- [x] done

### T02: OCR in reading order, the import end to end, and prepare's rule

- `caixa/documents/pdf/ocr.py`, `caixa/documents/prepare.py`, `tests/test_pdf_ocr.py`,
  `tests/test_documents_prepare.py`.
- Tests:
  - an import stores a bottom-first page top-first;
  - a digits layer is imported with OCR text (`source = ocr`) and the archived page looks the
    same (validation passes);
  - a short page of words is imported as `pdf` text with no OCR;
  - `prepare.read_document` OCRs the digits layer and not the short page.
- Verify: `python -m pytest -q tests/test_pdf_ocr.py tests/test_documents_prepare.py tests/test_pdf_inspect.py tests/test_pdf_collector.py && python -m mypy --python-version 3.12 caixa`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
