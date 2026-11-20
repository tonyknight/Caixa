---
id: 20261120-10-conversation-pages-and-attachments
title: "Conversation pages and attachments"
type: feature
priority: high
status: todo
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ""
parent:
depends_on:
- 20261120-08-how-mail-bodies-look
- 20261120-09-import-the-chosen-conversations
subtasks: []
---

## Description

File each conversation as a page of cards in `People/<Person>/Mail/<Account>/` and its
attachments in `Attachments/`, and retire Phase 1's mail pages.

## Acceptance criteria

- [ ] One page per conversation, named `(YYYY-MM-DD) <subject>.html` (` (2)` on a clash), in its home person's folder
- [ ] Cards in date order: subject on the top border; date and time with offset; sender and recipients by name and address; the body drawn the way chosen in ticket 8; attachments; a closed All headers fold. Nord light and dark, no script, readable from disk
- [ ] Attachments in `Mail/<Account>/Attachments/` named `(YYYY-MM-DD) <original name>`; same content once; a different file of the same name that day numbered
- [ ] One-pixel images dropped; a small inline image repeated once by a sender (same name and pixel size) kept once and linked
- [ ] The top-level `Mail/` folder and the per-thread pages of Phase 1 gone; their tests updated

## Context

Phase 1.5 - Mbox Tasks Breakdown item 10. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *What the box holds*; M10, N3.

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
