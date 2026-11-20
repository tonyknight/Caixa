---
id: 20261120-15-retire-the-blind-mail-import-documentation
title: "Retire the blind mail import; documentation"
type: chore
priority: medium
status: todo
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ""
parent:
depends_on:
- 20261120-05-the-clean-mail-window
- 20261120-07-the-sort-mail-window
- 20261120-13-reduce
subtasks: []
---

## Description

Retire Phase 1's blind mail import and document the new mail workflow.

## Acceptance criteria

- [ ] The import wizard's Mail card opens Clean mail / Sort mail; no collector imports a whole mbox
- [ ] `caixa import mail` replaced by `caixa mail read | clean | keep | senders | choose | ignore | import | reduce`; the worker protocol description lists the `mail.*` methods
- [ ] `docs/Documentation/Collector.md` (Mail) and `README.md` (box layout, collectors, status) describe the workflow
- [ ] A checklist for the maintainer's first real mbox (clean, sort, import, reduce, what to report)

## Context

Phase 1.5 - Mbox Tasks Breakdown item 15. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: M14; Tasks Breakdown item 15.

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
