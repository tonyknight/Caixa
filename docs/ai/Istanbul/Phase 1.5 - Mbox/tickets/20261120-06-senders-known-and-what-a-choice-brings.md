---
id: 20261120-06-senders-known-and-what-a-choice-brings
title: "Senders, Known and what a choice brings"
type: feature
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

The sorting logic behind Sort mail: the owner's addresses per account, Known matching, the
threads a chosen sender brings, and the owner's decisions.

## Acceptance criteria

- [ ] The owner's addresses proposed from mail labelled Sent (and the most frequent From otherwise) and confirmed with the account
- [ ] Known by address (chosen to begin with) and by name only (shown as such, not chosen until confirmed)
- [ ] To sort ordered with the owner's correspondents first, then the busiest
- [ ] A chosen sender brings every thread they wrote in, whole, and every thread in which the owner wrote to them, even unanswered; in a mailing-list thread only the mails of box people and the owner
- [ ] Choices and ignores remembered in `owner.json` and restored when a Cleaned or Reduced mbox is read, and after a reset
- [ ] `caixa mail senders | choose | ignore`

## Context

Phase 1.5 - Mbox Tasks Breakdown item 6. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Sorting rules*, *Data model* (owner.json); M2, M8.

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
