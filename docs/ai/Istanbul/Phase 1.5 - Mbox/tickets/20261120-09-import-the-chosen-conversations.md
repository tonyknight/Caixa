---
id: 20261120-09-import-the-chosen-conversations
title: Import the chosen conversations
type: feature
priority: high
status: in-progress
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ''
parent:
depends_on:
- 20261120-06-senders-known-and-what-a-choice-brings
subtasks: []
plan_status: in-progress
current_task: T03
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

Status: in-progress
Current task: T03

**Design:** importing reuses Phase 1's mail pipeline (Chattr's mail conversion, people, filing,
pages, the master's adapter, undo) on a small working mbox that holds only the chosen
conversations; this ticket changes what that pipeline keys mail by and records about it, and leaves
the box's files and pages to ticket 10.

- **Chattr** (mail only): a mail's id comes from its Message-ID alone (a hash of its headers when it
  has none), not from its conversation, so a mail never comes in twice; met again under another
  thread (a later export threads it differently), it moves to that thread, so conversations merge
  instead of splitting. `MboxParser` takes the `account` (kept in each mail's `service_specific`)
  and `workers`: the mails' records (decoding, attachments stored by hash) are built by worker
  processes from their bytes, in batches, in file order.
- **The master**, migration 4: `accounts` (id, name); `mail` (item id, account, Message-ID, thread
  key, date and offset, sender address and name, recipients, subject; the plain text stays the
  item's `text`); `mail_accounts` (item, account: a mail seen in a second account is recorded, its
  `mail` row stays with the first); `mail_threads` (thread key, account, subject, first and last
  date, mails, files; home person, page, summary and its model and date are filled by tickets 10
  and 12). `caixa/mail/records.py` `record_mail(master, chattr_db)` fills them from Chattr's
  messages after each mail import.
- **The service:** `mail.import.preview` (senders, conversations, mails, files, size of what the
  chosen bring) and `mail.import`, a `mail-import` job: the chosen threads' mails copied (byte for
  byte, in order) into `<box>/.caixa/work/mail/import-<job>.mbox`; the Mail collector run on it with
  the account and the Workers setting, inside an undo snapshot like any import; `record_mail`; the
  working mbox removed. Senders with mail in the master are **Imported** in Sort mail. The Jobs page
  and toasts name the job. `caixa mail import PATH [--account]`.

### T01: Chattr keys mail by Message-ID, takes the account and uses workers

- `tools/chattr/src/chattr/records.py` (`assign_ids`), `database_manager.py` (a moved mail),
  `parsers/mbox_parser.py` (`account`, `workers`), `commands.py` and `caixa/collectors/chattr.py`
  (passing them).
- Tests (`tools/chattr/tests/test_mbox_accounts.py`): the same mail under two threads is one
  message, in the later thread; the account in `service_specific`; 1 and 3 workers give the same
  records and stored files.
- Verify: `python -m pytest -q tools/chattr/tests/test_mbox_accounts.py tools/chattr/tests/test_mbox_parser.py tools/chattr/tests/test_mbox_threads.py tools/chattr/tests/test_mbox_import.py`
- [x] done

### T02: The master records mail

- `caixa/schema.py` (migration 4), `caixa/mail/records.py`.
- Tests (`tests/test_mail_records.py`): after importing the fixture's mbox through the Mail
  collector with an account, every mail has its `mail` row (facts, account) and plain text; threads
  with their counts; importing the Work account's mbox records the shared mail in `mail_accounts`
  and keeps it with Gmail; importing again adds nothing.
- Verify: `python -m pytest -q tests/test_mail_records.py tests/test_master.py`
- [x] done

### T03: `mail.import` as a job, and `caixa mail import`

- `caixa/mail/write.py` (`extract`), `caixa/service.py` (`mail.import.preview`, `mail.import`,
  `_mail_imported`), `caixa/cli.py`, the protocol list; `web/src/client` (job label, result and
  failure toast for `mail-import`), window rebuilt.
- Tests (`tests/test_mail_service.py`): two chosen senders bring exactly their conversations
  (and the owner's unanswered mail to a chosen person; from a list thread only the box's and the
  owner's mail); the preview's counts; importing again adds nothing; the chosen are then Imported;
  undo takes the import back; the command.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: Chattr: a mail's id is 'mail:<hash of its Message-ID>' (other services unchanged); a mail met again under another thread moves to it and a thread left empty is deleted (with its participants). MboxParser(account, workers): account in service_specific; with workers > 1 the mails' bytes are read in the parent and their records built in spawned processes in 16 MB batches, in file order. commands.convert(parser_options=...) passes them for batch services; the Mail collector forwards options 'account' and 'workers'. Mail ids change for boxes that imported mail with Phase 1 (none on real data yet): re-importing such a box would add the mail again under new ids.

### 2026-11-20
T02: master migration 4 (accounts, mail, mail_accounts, mail_threads); caixa/mail/records.py record_mail(master, chattr_db, account, seen). Found and fixed: Phase 1's group rule (a group the owner never wrote in is removed) dropped a chosen mail thread where the owner was only a recipient; DatabaseManager.tidy_groups(keep=('Mail',)) spares mail conversations (mail now only comes in as the owner chose it). A mail met again in another account is unchanged in Chattr, so its second account comes from the import job (seen = the working mbox's Message-IDs). Master.delete_items also deletes an item's mail rows.
