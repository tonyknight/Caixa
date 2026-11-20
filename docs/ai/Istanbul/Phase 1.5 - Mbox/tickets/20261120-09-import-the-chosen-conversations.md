---
id: 20261120-09-import-the-chosen-conversations
title: "Import the chosen conversations"
type: feature
priority: high
status: todo
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ""
parent:
depends_on:
- 20261120-06-senders-known-and-what-a-choice-brings
subtasks: []
---

## Description

Import the chosen conversations: copy their mails into a working mbox, import it through
Chattr's mail conversion with the account, and upsert the master's new mail tables by Message-ID.

## Acceptance criteria

- [ ] Only the conversations a choice brings are imported (fixture test with two chosen senders)
- [ ] Master migration 4: `accounts`, `mail`, `mail_accounts`, `mail_threads`; date, sender address and name, account, subject and plain text stored
- [ ] Mail keyed by Message-ID (hash of headers without one): importing again, or from a second account, adds nothing; the second account is recorded
- [ ] Conversations that share mails across exports are merged, not split
- [ ] A job with preview (senders, conversations, mails, files, size), progress, cancel and undo; decoding and attachments in the workers
- [ ] `caixa mail import`; `chattr-cli convert mail` unchanged when used alone

## Context

Phase 1.5 - Mbox Tasks Breakdown item 9. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Components* (Import), *Data model*, *Key flows*; M9. Phase 1 review notes on ticket 20261101-10 (key mail by Message-ID).

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
