---
id: 20261101-07-imessage-parser
title: iMessage parser
type: feature
priority: medium
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 7.
parent: null
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
---

## Description

Move the working iMessage reader behind `BaseParser` and into the database, with the review fixes.

## Acceptance criteria

- [ ] attributedBody is decoded with a real typedstream decoder; long messages are not truncated
- [ ] Both seconds and nanoseconds epochs handled; UTC + offset stored
- [ ] Spam filter runs on the parallel path and tags rather than drops
- [ ] Tapbacks on attachments (`p:1/`, `bp:`) attach to their targets
- [ ] All tools open `chat.db` read-only

## Context

Phase1-Collector Tasks Breakdown item 7. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Chattr — Carry forward / Fix; F1–F3.

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
