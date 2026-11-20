---
id: 20261120-14-attachments-folders-for-every-source
title: "Attachments folders for every source"
type: feature
priority: medium
status: todo
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ""
parent:
depends_on:
- 20261120-10-conversation-pages-and-attachments
subtasks: []
---

## Description

Every source files attachments in an `Attachments/` folder: `People/<Person>/<Source>/Attachments/`
(and the same under `Groups/`). Boxes already built are moved once.

## Acceptance criteria

- [ ] iMessage, WhatsApp, Messenger, Instagram, Google Voice and voicemail file new attachments in `<Source>/Attachments/`
- [ ] Opening a box built before this moves its files once; the move can be stopped and restarted without loss
- [ ] Paths in `chattr.sqlite` and `caixa.sqlite` updated; pages redrawn; a test checks every link on every page resolves
- [ ] Undo snapshots and re-imports keep working after the move
- [ ] `docs/Documentation/Collector.md` (Attachments in detail) updated

## Context

Phase 1.5 - Mbox Tasks Breakdown item 14. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *What the box holds* (Attachments folders); M15. Filing code: `tools/chattr/src/chattr/filing.py`.

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
