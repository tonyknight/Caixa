---
id: 20261124-03-migration-6-and-document-records
title: "Migration 6 and document records"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-01-synthetic-pdf-fixtures
subtasks: []
---

## Description

Migration 6 of the master database: every table of *Data model* (documents, sources, pages, the FTS5 index, fields, tags, authors and aliases, runs, chunks), a records module to write and read them, and `documents.list` / `documents.get`.

## Acceptance criteria

- [ ] Migration 6 applies to a new master and to one at version 5; `schema.CURRENT_VERSION` is 6
- [ ] Documents are `items` of type `document`, collector `pdf`, id `pdf:<source sha256>`, with `time_precision` from the naming date
- [ ] A records module upserts a document, its sources, pages (keeping the FTS index in step), fields, tags and runs, and reads them back
- [ ] `documents.list` and `documents.get` service methods and `caixa documents list|show` commands
- [ ] Reset and undo snapshots cover the new tables

## Context

Phase 1.5 - PDF Tasks Breakdown item 3. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Data model*; D3, D7.

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
