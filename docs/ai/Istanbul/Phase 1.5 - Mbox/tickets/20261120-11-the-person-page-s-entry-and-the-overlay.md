---
id: 20261120-11-the-person-page-s-entry-and-the-overlay
title: "The person page's entry and the overlay"
type: feature
priority: high
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

One entry per conversation on every involved person's page, and the overlay that shows the
conversation page over it.

## Acceptance criteria

- [ ] The entry at the first mail's date: `@<Account>` pill, who began it, subject, summary (or the opening words), counts, Read the conversation
- [ ] Every box person in a conversation gets the entry, linking to the one page; unanswered owner mail appears as sent by the owner
- [ ] `conversation.js`: a dialog with the page in a frame, closing with Escape, the cross or a click beside it, and an open-in-its-own-window button
- [ ] Its hash joins the box pages' Content-Security-Policy; pages drawn with an older script get the current one (`caixa/web.py` PAGE_SCRIPTS)
- [ ] Works from `/box/` and from `file://` with no policy error (end-to-end test)
- [ ] The index page's Mail view and dashboard list mail by account

## Context

Phase 1.5 - Mbox Tasks Breakdown item 11. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *What the box holds* (entry), *Components*; M11.

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
