---
id: 20261101-10-mbox-email-parser
title: MBOX email parser
type: feature
priority: medium
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 10.
parent: null
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
---

## Description

Parse MBOX email (Gmail Takeout) into the unified schema.

## Acceptance criteria

- [ ] Threads by Message-ID / In-Reply-To / References and Gmail thread ID
- [ ] RFC 2047 headers decoded; HTML and plain bodies kept
- [ ] Attachments stored by hash

## Context

Phase1-Collector Tasks Breakdown item 10. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F1; F4.

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
