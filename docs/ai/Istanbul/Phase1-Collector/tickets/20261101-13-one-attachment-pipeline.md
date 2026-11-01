---
id: 20261101-13-one-attachment-pipeline
title: One attachment pipeline
type: feature
priority: medium
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 13.
parent: null
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
---

## Description

Generalize AttachmentManager for all services.

## Acceptance criteria

- [ ] Archival `(YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>` names with no collisions
- [ ] Originals kept; date written into standard metadata where supported
- [ ] Per-person `Attachments/` folders

## Context

Phase1-Collector Tasks Breakdown item 13. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Organizing principles; F8.

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
