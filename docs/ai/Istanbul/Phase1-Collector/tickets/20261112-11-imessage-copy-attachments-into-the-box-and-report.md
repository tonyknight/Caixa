---
id: 20261112-11-imessage-copy-attachments-into-the-box-and-report
title: 'iMessage: copy attachments into the box, and report the ones missing from
  this Mac'
type: feature
priority: medium
status: todo
created: 2026-11-12
updated: 2026-11-12
closed:
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

What is this ticket and why does it exist?

## Acceptance criteria

- [ ] Concrete, checkable condition
- [ ] Another concrete condition

## Context

Links to relevant code, prior tickets, decisions in the project's
Requirements file, or anything else a model working on this would need
to know.

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

### 2026-11-12
Ported from imessage-exporter 5.0.1 (GPL-3.0; update tools/chattr/NOTICE from '2.x series' to 5.x). Planned with the maintainer on 2026-11-12; all six are wanted before the first real iMessage import. No implementation plan yet.

### 2026-11-12
Maintainer's database: 12,629 attachments, 5,274 missing (409 with no path, 4,865 not on disk). Add a report of missing attachments by conversation so they can be downloaded in Messages before importing.
