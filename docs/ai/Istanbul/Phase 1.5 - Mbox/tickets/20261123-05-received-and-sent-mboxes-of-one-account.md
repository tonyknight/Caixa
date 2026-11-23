---
id: 20261123-05-received-and-sent-mboxes-of-one-account
title: Received and sent mboxes of one account
type: chore
priority: medium
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Sort mail asks which to sort; received + sent join (tested both orders)
parent:
depends_on: []
subtasks: []
---
## Description

The maintainer has an account exported as a folder of two mboxes (received and sent) and asked how
the second is reached after the first is imported, and how sent mail joins one account. Both are
read at once and listed under "Mboxes already read"; choices hold box-wide; mail joins
conversations by Message-ID and References. Asked: prove it with a test, and fix the question
"Which one do you want to clean?" that Sort mail showed too.

## Acceptance criteria

- [x] Sort mail asks "Which one do you want to sort?"; Clean mail still asks to clean.
- [x] A received and a sent mbox of one account, imported in either order, give one conversation
      per thread with every mail once, on the person's page; each mail keeps its mbox (Inbox, Sent).

## Context

- `web/src/client/mail/Sources.tsx` (`which`), `CleanMail.tsx`, `SortMail.tsx`, `locales.ts`
- `tests/test_mail_sent_and_received.py`

## Subtasks

- [x] T01 The question per window; the received-and-sent test.

## Implementation plan

Status: done
Current task: T01

### T01

- `Sources` takes the question (`which`) from its window; `mail.read.whichSort` added (English,
  Chinese). Web tests for both windows.
- `tests/test_mail_sent_and_received.py`: a folder with Inbox.mbox and Sent.mbox (no Gmail thread
  ids), read with account Work, the owner confirmed and two senders chosen once, imported in both
  orders: one 3-mail Dinner conversation on Ana's page with every mail on its page; the Mail list
  shows it under Inbox and Sent; the unanswered lunch under Sent.
- Verify: web and Caixa suites.

## Completion report

- **Outcome:** The question fits the window; received and sent mboxes of one account join as
  expected, proved in both orders.
- **Files:** `web/src/client/mail/Sources.tsx`, `CleanMail.tsx`, `SortMail.tsx`,
  `web/src/client/locales.ts`, the built `caixa/data/web/`; `web/tests/sort-mail.test.tsx`,
  `clean-mail.test.tsx`; `tests/test_mail_sent_and_received.py` (new).
- **Errors:** None in the product. Noted: mail the owner sent to someone who never wrote back and
  whom nobody named is filed under their address (Unrecognized) though the To line names them.
- **Verify:** Web 275 passed; Caixa 1508 passed, 1 skipped.

### Review

Clean.

## Notes

Append-only running log. Each entry dated.
