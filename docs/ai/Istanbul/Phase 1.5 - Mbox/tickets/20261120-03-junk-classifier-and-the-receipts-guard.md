---
id: 20261120-03-junk-classifier-and-the-receipts-guard
title: "Junk classifier and the receipts guard"
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

Give every mail its junk flags and keep-protections, roll them up by sender, and put each sender
in a cleaning group with its number of mails and total size. Body checks (unsubscribe links,
receipts) run in the workers.

## Acceptance criteria

- [ ] Flags and protections exactly as in *Cleaning rules*
- [ ] Receipts and orders are kept even from no-reply senders with unsubscribe links (English, Portuguese, Spanish)
- [ ] Mail from the owner, from box people (by address or known name), threads the owner wrote in, and senders the owner ever wrote to are never flagged for removal
- [ ] Senders grouped under Lists and newsletters, Notices and no-reply, Unsubscribe links, Spam and Trash (strongest reason), and Receipts and orders (kept)
- [ ] Each sender and each group carries its number of senders, mails and total size
- [ ] On the noisy fixture every junk mail is flagged and every protected mail kept (a test lists both)

## Context

Phase 1.5 - Mbox Tasks Breakdown item 3. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Cleaning rules*, *The list, in both windows*; M4.

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
