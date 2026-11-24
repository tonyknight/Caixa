---
id: 20261124-07-validation-and-failure-handling
title: "Validation and failure handling"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-06-selective-ocr
subtasks: []
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

Status: draft
Current task:

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
