---
id: 20261120-01-synthetic-mail-fixtures
title: "Synthetic mail fixtures"
type: chore
priority: high
status: todo
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ""
parent:
depends_on: []
subtasks: []
---

## Description

The synthetic mail every test of this project uses: a noisy mbox (plain and zipped) and a
generator for a multi-gigabyte mbox for the scale test. Built by the fixture family's builders, in
the style of `tools/chattr/tests/fixtures/builders/mbox.py`; deterministic (fixed boundaries and
`From ` lines).

## Acceptance criteria

- [ ] The noisy mbox holds: family and friends who are people in the fixture box; the owner's sent mail, including mail never answered; strangers; newsletters, notifications, mailing lists and no-reply senders; mail with unsubscribe links (English, Portuguese, Spanish); receipts and orders in the same languages, some from no-reply senders with unsubscribe links
- [ ] Gmail labels including Sent, Spam, Trash and the Promotions, Updates, Social and Forums categories; Gmail thread ids on some threads and References-only threads on others; a thread across years; a mailing-list thread in which a box person posted
- [ ] Edge cases: mail without a Message-ID, the same mail in two accounts, odd charsets and RFC 2047 headers, HTML-only mail, `From ` lines escaped in bodies, signature images repeated with slightly different bytes, one-pixel tracking images, `image001.png` from different mails on the same day
- [ ] A zipped copy, and a Takeout-shaped zip holding more than one `.mbox`
- [ ] A generator writes an mbox of a requested size into a temporary folder (never committed) for the slow scale test
- [ ] The same input always gives byte-identical files; a test checks it
- [ ] Each case is documented in the builder so later tickets can find what they need

## Context

Phase 1.5 - Mbox Tasks Breakdown item 1. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Testing requirements* (Fixtures, Scale). Tasks Breakdown item 1.

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
