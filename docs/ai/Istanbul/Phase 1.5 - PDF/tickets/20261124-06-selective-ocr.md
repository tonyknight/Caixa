---
id: 20261124-06-selective-ocr
title: "Selective OCR"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-05-inspection-page-by-page
subtasks: []
---

## Description

OCR with OCRmyPDF on only the pages that need it; broken-text pages' OCR text stored without rewriting the page; the `documents.ocr` and `documents.ocr_languages` (`eng`) settings; history; `caixa doctor` checks; the no-OCR path.

## Acceptance criteria

- [ ] Scanned and mixed fixtures get a text layer on exactly their scanned pages; digital pages are not rasterized; a good OCR layer is kept
- [ ] A broken-text page looks the same and its OCR text is stored as `ocr`
- [ ] Without OCRmyPDF or Tesseract the import succeeds and those pages are `needs_ocr`; `caixa doctor` names what to install
- [ ] Engine, version and settings recorded in `document_runs`

## Context

Phase 1.5 - PDF Tasks Breakdown item 6. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (OCR), *Pipeline*; D5, D17, D27.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: draft
Current task:

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
