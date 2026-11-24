---
id: 20261124-02-the-archival-naming-convention
title: "The archival naming convention"
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

Caixa's archival naming convention, as a document (`docs/Archival names.md`) and as code (`caixa/naming.py`) future file collectors can reuse: dates at their precision, which date names each type, title and author cleaning, characters, a cut after 110 characters, clashes with ` (2)`.

## Acceptance criteria

- [ ] `docs/Archival names.md` documents the convention with examples and edge cases, linked from the README
- [ ] `caixa/naming.py` builds `(DATE) Title - Author.ext` with `(YYYY-MM-DD)`, `(YYYY-MM)`, `(YYYY)`; no author omits ` - Author`; no date is not named (Unrecognized keeps the original name)
- [ ] Unsafe characters, control characters, leading/trailing dots and spaces, runs of spaces, capitals and NFC are handled; names are cut after 110 characters at a word
- [ ] A different file of the same name in a folder gets ` (2)`, ` (3)`; the same file is recognised
- [ ] Every example in the document is a test

## Context

Phase 1.5 - PDF Tasks Breakdown item 2. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Naming convention*; D9.

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
