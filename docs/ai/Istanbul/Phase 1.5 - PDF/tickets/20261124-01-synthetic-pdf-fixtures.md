---
id: 20261124-01-synthetic-pdf-fixtures
title: "Synthetic PDF fixtures"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on: []
subtasks: []
---

## Description

The synthetic PDF family every later ticket tests against: deterministic builders (PyMuPDF, fixed seeds) that write digital, scanned, mixed, OCR'd (good and poor), broken-text, rotated and odd-sized PDFs for the synthetic family, with descriptive, uninformative and misleading filenames, missing and wrong properties, encrypted, corrupted, duplicate and same-text-different-bytes files, and a file of known answers (type, title, author, date and precision, key fields, words found only on scanned pages).

## Acceptance criteria

- [ ] A builder writes the whole family into a folder from a fixed seed; two builds are byte-identical where the format allows (or differ only in documented ways)
- [ ] Every case in *Testing requirements* (Fixtures) is present, in English and Portuguese, synthetic people and invented institutions only
- [ ] A known-answers file describes each fixture: expected page classes, type, title, author, naming date and precision, key fields, filename conflicts, search words
- [ ] Tests check the fixtures are what they claim (page counts, encryption, scanned pages without text, broken text layer garbled)

## Context

Phase 1.5 - PDF Tasks Breakdown item 1. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: Testing requirements (Fixtures).

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
