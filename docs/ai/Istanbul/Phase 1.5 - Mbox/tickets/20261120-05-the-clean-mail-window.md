---
id: 20261120-05-the-clean-mail-window
title: "The Clean mail window"
type: feature
priority: high
status: todo
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ""
parent:
depends_on:
- 20261120-03-junk-classifier-and-the-receipts-guard
- 20261120-04-the-mbox-writer
subtasks: []
---

## Description

The Clean mail window: React in `web/src`, opened in its own window from the Mail card in
Import, showing the categorized list of what cleaning would delete, with Keep, preview and writing
the Cleaned mbox. Its service methods and commands.

## Acceptance criteria

- [ ] Categories on the left with senders, mails and size each; rows with sender name, address, number of mails and size
- [ ] Select, Shift-select, drag onto Keep, Keep from the hover tools; the status bar adds up the selection
- [ ] A preview shows a sender's mails (read from the mbox by byte range, drawn safely)
- [ ] Writing asks for confirmation (how many mails and how much space are left out) and runs as a job with progress
- [ ] Keeps are remembered in `owner.json` (`mail` section)
- [ ] `mail.*` methods for cleaning and `caixa mail clean | keep`
- [ ] Vitest with the fake API, and an end-to-end test in Chromium against the real `caixa serve`; the built window rebuilt and committed
- [ ] After this ticket the maintainer can clean a real mbox

## Context

Phase 1.5 - Mbox Tasks Breakdown item 5. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Components* (windows), *Cleaning rules*, *The list, in both windows*; M5, M8. Design language: the box index page (`tools/chattr/src/chattr/templates/index.html`, `index.js`).

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
