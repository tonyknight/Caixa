---
id: 20261101-21-caixa-service-layer-and-caixa-worker
title: Caixa service layer and caixa worker
type: feature
priority: high
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 21.
parent: null
depends_on:
- 20261101-20-collector-contract-and-registry
subtasks: []
---

## Description

The Python service layer behind the browser and the CLI.

## Acceptance criteria

- [ ] stdio JSON-RPC methods for box, collectors, import, jobs, people, browse, settings
- [ ] SQLite jobs table with progress notifications; inbox folder watching
- [ ] `--read-only` rejects every write method
- [ ] CLI uses the same layer; worker-protocol pytest suite

## Context

Phase1-Collector Tasks Breakdown item 21. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Caixa worker; F17; F21.

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
