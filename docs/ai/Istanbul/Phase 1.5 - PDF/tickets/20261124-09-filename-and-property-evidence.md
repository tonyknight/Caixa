---
id: 20261124-09-filename-and-property-evidence
title: "Filename and property evidence"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-03-migration-6-and-document-records
subtasks: []
---

## Description

Deterministic evidence from the original filename (dates and partial dates, amounts, numbers, known authors, type words, uninformative patterns) and from the PDF's properties, plus dates in the text; used by the import for the provisional date and author.

## Acceptance criteria

- [ ] Descriptive, uninformative and misleading fixture filenames give the facts their known answers name
- [ ] Properties are read, with producer noise ignored as an author
- [ ] Facts are stored as `document_fields` with source `original_filename` or `pdf_metadata`
- [ ] The import files a document by these when date and author are both known

## Context

Phase 1.5 - PDF Tasks Breakdown item 9. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Filename and property evidence); D11.

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
