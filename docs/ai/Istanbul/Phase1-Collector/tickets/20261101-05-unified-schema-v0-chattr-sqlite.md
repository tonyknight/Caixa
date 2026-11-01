---
id: 20261101-05-unified-schema-v0-chattr-sqlite
title: Unified schema v0 (chattr.sqlite)
type: feature
priority: high
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 5.
parent: null
depends_on:
- 20261101-04-chattr-stabilization
subtasks: []
---

## Description

Chattr's own next milestone: one unified schema and one `DatabaseManager` for all services.

## Acceptance criteria

- [ ] Tables per the Requirements data model: conversations, handles, participants, messages, attachments, reactions, imports, schema_version
- [ ] Ordered migrations; stable IDs; upserts make re-imports idempotent
- [ ] `imports` and `Services/*.json` `state` updated on every run
- [ ] Native per-service JSON export still available

## Context

Phase1-Collector Tasks Breakdown item 5. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Data model — Chattr unified schema v0; Stable IDs; F2; N3; N5.

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
