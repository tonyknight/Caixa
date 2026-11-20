---
id: 20261120-04-the-mbox-writer
title: "The mbox writer"
type: feature
priority: high
status: todo
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ""
parent:
depends_on:
- 20261120-02-mail-index-and-parallel-reading
subtasks: []
---

## Description

Write a Cleaned or Reduced mbox: the kept mails' byte ranges copied in order, byte for byte, to a
`.part` file, every mail checked against the index (in the workers), then renamed into place. Used by
Clean (ticket 5) and Reduce (ticket 13).

## Acceptance criteria

- [ ] Names and placement as in *The mbox family*: `(YYYY-MM-DD) <name> [Cleaned|Reduced].mbox` in the source's folder (beside a `.zip`); an old date and tag replaced; ` (2)` on a clash
- [ ] Stops before any work when the folder cannot be written or free space is short, saying how much is needed
- [ ] The source is only ever opened read-only; a test checks its bytes and time are unchanged
- [ ] The written file holds exactly the requested mails, byte-identical and in order (checked mail by mail before the rename); a failure leaves no file under the final name
- [ ] The new file is recorded in the index as a child of its source, with its account

## Context

Phase 1.5 - Mbox Tasks Breakdown item 4. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Components* (Mbox writer), *The mbox family*; M6.

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
