---
id: 20261101-18-caixa-master-schema-v0-and-messages-adapter
title: Caixa master schema v0 and messages adapter
type: feature
priority: high
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 18.
parent: null
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
- 20261101-14-people-roles-contacts-and-aliases
subtasks: []
---

## Description

Create Caixa's master database and load Chattr's output into it.

## Acceptance criteria

- [ ] Migrations; items, people, aliases, item → person links with roles, imports, change log
- [ ] Adapter ATTACHes `chattr.sqlite` and upserts by stable ID; appends change-log rows
- [ ] `aliases.json` exported from the master
- [ ] Re-syncing unchanged data writes zero change-log rows

## Context

Phase1-Collector Tasks Breakdown item 18. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Data model — handoff contract; F13; F14.

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
