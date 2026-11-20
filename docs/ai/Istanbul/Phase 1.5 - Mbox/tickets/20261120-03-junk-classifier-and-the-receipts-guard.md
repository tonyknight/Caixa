---
id: 20261120-03-junk-classifier-and-the-receipts-guard
title: Junk classifier and the receipts guard
type: feature
priority: high
status: in-progress
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ''
parent:
depends_on:
- 20261120-02-mail-index-and-parallel-reading
subtasks: []
plan_status: done
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

Status: done
Current task: 

**Design:** cleaning needs two things from a mail's body: whether it has an unsubscribe link and
whether it reads like a receipt or an order. Both are found **in the read itself** (ticket 02's
workers already hold every mail's bytes), so an mbox is read once: the worker parses the mail
(first megabyte, so a large attachment costs nothing) and keeps two booleans, `unsubscribe` and
`receipt` (the subject counts for receipts). The index schema goes to version 2 (an index of
version 1 is simply read again). `caixa/mail/clean.py` then classifies from the index alone:

- **flags** per mail, each tied to a group: `spam`/`trash` labels → `spam_trash`; list headers
  (`List-Id`, `List-Post`, `List-Unsubscribe`), `Precedence: bulk|list|junk`, a mass-mail
  service's markers (`Feedback-ID` and others), Gmail's Promotions and Forums → `lists`;
  `Auto-Submitted` (not `no`), a no-reply-like sender, Gmail's Updates and Social → `notices`; an
  unsubscribe link in the body → `unsubscribe`. A mail's group is its strongest flag's, in that
  order (Spam and Trash, then lists, then notices, then unsubscribe links).
- **protections** per mail: `owner` (sent by one of the owner's addresses), `box_person` (sender's
  address is a box person's, or their name is one the box knows), `owner_wrote` (the owner wrote to
  this sender, in any source), `owner_thread` (the owner wrote in this thread), `receipt`, `kept`
  (the sender was kept by the owner).
- A mail is **removed by cleaning** when it has a flag and no protection. Each sender's removable
  mails are summed into the group of their strongest flag; flagged mails kept only as receipts are
  listed under **Receipts and orders (kept)**. Groups and rows carry senders, mails and size.

`classify(index, source_id, owner_addresses, known_addresses, known_names, kept)` takes plain sets,
so it needs no box; the owner's addresses here are the ones the owner's mail labelled `Sent` came
from, plus any given (ticket 06 adds confirming them). Its result is written to `mails.flags`,
`mails.protections`, `mails.by_owner`, `senders.grp` and `senders.owner_wrote`.

### T01: Unsubscribe links and receipts found in the read

- `caixa/mail/index.py`: schema version 2 with `unsubscribe` and `receipt` columns; `parse`
  reads the body (plain, else the HTML as text) of the first megabyte.
- `caixa/mail/clean.py`: the wording (English, Portuguese, Spanish) as `UNSUBSCRIBE` and
  `RECEIPT`, used by `parse`.
- Tests (`tests/test_mail_clean.py`): every mail of the noisy fixture with an unsubscribe link or
  receipt wording is marked, and no other; an index of version 1 is read again.
- Verify: `python -m pytest -q tests/test_mail_clean.py tests/test_mail_index.py`
- [x] done

### T02: Flags, protections, groups and the counts

- `caixa/mail/clean.py`: `flags_of`, `classify`, `owner_addresses_from_sent`, `groups`
  (`Group` and `SenderRow`: key, label, senders, mails, size; name, address, mails, size).
- The fixture's catalogue: the owner's plain reply to the school (`school-2`) carries no flag, so
  its outcome is `clean`, not `kept:protected`.
- Tests: on both accounts of the noisy fixture every mail's outcome equals the catalogue's (the
  test lists any that differ); group order and labels; counts and sizes add up to the mails;
  `kept` senders lose their junk; a sender in a junk group and under receipts.
- Verify: `python -m pytest -q tests/test_mail_clean.py && python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && python -m pytest -q -m slow tests/test_mail_scale.py -s`
- [x] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: the read parses each mail's first megabyte fully (headers and text from one parse) and keeps 'unsubscribe' and 'receipt'; both the plain part and the HTML part (as text) are searched, since a newsletter's plain part sometimes leaves the link out. Index schema 2.

### 2026-11-20
T02: classify/groups/outcome in clean.py; every mail of both fixture accounts gets the catalogue's outcome. Fixture corrected: school-2 (the owner's plain reply) is 'clean'. owner_wrote counts the owner's mail in every source of the index; owner_thread is per source. Performance: parsing bodies in the read made 2 GB of 40 KB mails 5x slower (191.7 s with 1 worker, 48.8 s with 4); a quick keyword check before the wording searches brought it to 140.2 s and 35.4 s (header parsing by the email package's default policy is now the largest cost). Memory unchanged (86 MB).
