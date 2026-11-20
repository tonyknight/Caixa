---
id: 20261120-08-how-mail-bodies-look
title: "How mail bodies look"
type: spike
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

Spike: decide how mail bodies are drawn on the conversation page. `caixa mail sample <mbox>`
draws a few conversations of a small real mbox three ways (plain text; tidied HTML; the mail's own
HTML with its styling kept and scripts, event handlers and remote content removed) for the
maintainer to compare on their own computer.

## Acceptance criteria

- [ ] `caixa mail sample` writes the three versions of each sampled conversation to a folder the maintainer chooses (outside the repository)
- [ ] Every version holds no script, event handler or remote reference (tested on the fixtures)
- [ ] The maintainer's choice is recorded in the Requirements (*What the box holds*) and in this ticket's notes
- [ ] No real mail is committed

## Context

Phase 1.5 - Mbox Tasks Breakdown item 8. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *What the box holds* (conversation page), N3, Open questions. Blocks ticket 10.

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
