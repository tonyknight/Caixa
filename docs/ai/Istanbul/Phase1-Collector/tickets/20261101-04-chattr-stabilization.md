---
id: 20261101-04-chattr-stabilization
title: Chattr stabilization
type: feature
priority: high
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 4.
parent: null
depends_on:
- 20261101-03-chattr-import-and-licensing
subtasks: []
---

## Description

Make Chattr's v2 scaffolding actually work and remove its contradictions.

## Acceptance criteria

- [ ] The name is 'Chattr' everywhere (`~/.chattr.json`, `~/Documents/Chattr`, `chattr.sqlite`, `chattr` command)
- [ ] Preflight and configuration are wired: pointer → root → global `config.json` merged with `Services/<Service>.json`
- [ ] iMessage configuration keys resolve (Quick/List/Diagnostics no longer fail)
- [ ] Preflight repair keeps existing preferences and state; `--root` works without prompting
- [ ] HTML generation no longer crashes and the template uses the database field names
- [ ] Unused dependencies removed; stale docs consolidated

## Context

Phase1-Collector Tasks Breakdown item 4. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Chattr — What works / Scaffolding / Contradictions; F11.

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
