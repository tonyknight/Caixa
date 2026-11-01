---
id: 20261101-20-collector-contract-and-registry
title: Collector contract and registry
type: feature
priority: high
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 20.
parent: null
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
- 20261101-18-caixa-master-schema-v0-and-messages-adapter
subtasks: []
---

## Description

Let export sources register themselves so the UI needs no per-source code.

## Acceptance criteria

- [ ] `caixa.collectors` entry-point discovery
- [ ] Each collector declares inputs, 'how to export' instructions, an options JSON Schema, `preview` and `run`
- [ ] Chattr's six sources registered

## Context

Phase1-Collector Tasks Breakdown item 20. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Collector contract; F16.

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
