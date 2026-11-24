---
id: 20261124-05-inspection-page-by-page
title: "Inspection page by page"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-04-the-pdf-collector
subtasks: []
---

## Description

Inspect every page with PyMuPDF and classify it (`text`, `needs_ocr`, `ocr_layer`, `broken_text`, `blank`) from its text quality and image coverage; recognise encrypted and damaged files. Stored on the pages and shown in preview.

## Acceptance criteria

- [ ] Every fixture page gets the class its known answers name
- [ ] Encrypted (password) and damaged files are recognised; an owner-password-only PDF is readable
- [ ] Quality measures and the class are stored per page; preview reports pages likely to need OCR

## Context

Phase 1.5 - PDF Tasks Breakdown item 5. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Inspection); D4.

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
