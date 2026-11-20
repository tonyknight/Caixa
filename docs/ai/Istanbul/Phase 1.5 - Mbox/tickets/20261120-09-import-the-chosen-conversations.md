---
id: 20261120-09-import-the-chosen-conversations
title: Import the chosen conversations
type: feature
priority: high
status: done
created: 2026-11-20
updated: 2026-11-20
closed: 2026-11-20
notes: 'Done: import of chosen conversations (job, undo), master mail tables, Message-ID
  ids, workers, Import button.'
parent:
depends_on:
- 20261120-06-senders-known-and-what-a-choice-brings
subtasks: []
plan_status: done
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

Status: done
Current task: 

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
- [x] done

## Completion report

- **Outcome:** importing the chosen conversations: `mail.import.preview` and `mail.import` (a
  `mail-import` job, undoable) copy the chosen threads' mails into a working mbox and run Phase 1's
  Mail collector on it with the account and the Workers setting; the master's new tables
  (migration 4: `accounts`, `mail`, `mail_accounts`, `mail_threads`) record every mail's facts and
  account and each conversation's counts. Chattr keys mail by Message-ID alone (a mail is never
  imported twice; a mail re-threaded by a later export moves, so conversations merge), keeps the
  account with each mail and builds records in worker processes. Mail conversations are spared
  Phase 1's group rule. Sort mail has its Import button; senders whose mail is all in the box are
  Imported. `caixa mail import`.
- **Files:** new `caixa/mail/records.py`, `tests/test_mail_records.py`,
  `tools/chattr/tests/test_mbox_accounts.py`; changed `caixa/{schema,master,service,cli}.py`,
  `caixa/mail/write.py` (`extract`), `caixa/collectors/chattr.py`,
  `tools/chattr/src/chattr/{records,database_manager,commands}.py`,
  `tools/chattr/src/chattr/parsers/mbox_parser.py`, `web/src/client/{mail/SortMail.tsx,
  mail/types.ts,Toasts.tsx,locales.ts}`, `caixa/data/web/*`, tests (`test_mail_service`,
  `test_worker_protocol`, `sort-mail`, `jobs-page`).
- **Errors:** Phase 1's group rule removed a chosen mail thread the owner had not written in;
  mail conversations are now spared it. A mail met again in a second account is unchanged in Chattr,
  so the import job tells the master which mails the mbox held.
- **Verify:** `python -m pytest -q` → 1392 passed, 1 skipped, 1 deselected; black, mypy, tsc clean;
  `vitest run` → 247 passed.

## Review

### 2026-11-20: 9f37697..HEAD (T01–T03), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** mail ids changed form (`mail:<hash>`); a box that imported mail with Phase 1's blind
  import would get that mail again under the new ids. No box holds real mail yet (the completion
  report of Phase 1 says mail was never tried on real data).
- **Minor:** pages and files are still Phase 1's (`Mail/<year>/…`) until ticket 10, which waits for
  the maintainer's choice of body style (ticket 08).
- **Minor:** the working mbox is read by Chattr's parser through `mailbox`, which builds its own
  table of contents; it holds only the chosen mails, so this is small.
- **Minor:** `chattr-cli convert mail` on its own is unchanged in use; it now also spares mail
  conversations from no rule (Chattr standalone never ran `tidy_groups`).
- **Spec:** M9 met; every acceptance criterion met.
- **TDD:** RED then GREEN for each task.
- **Commits:** `{ticket-id} {task-id}: {title}`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: Chattr: a mail's id is 'mail:<hash of its Message-ID>' (other services unchanged); a mail met again under another thread moves to it and a thread left empty is deleted (with its participants). MboxParser(account, workers): account in service_specific; with workers > 1 the mails' bytes are read in the parent and their records built in spawned processes in 16 MB batches, in file order. commands.convert(parser_options=...) passes them for batch services; the Mail collector forwards options 'account' and 'workers'. Mail ids change for boxes that imported mail with Phase 1 (none on real data yet): re-importing such a box would add the mail again under new ids.

### 2026-11-20
T02: master migration 4 (accounts, mail, mail_accounts, mail_threads); caixa/mail/records.py record_mail(master, chattr_db, account, seen). Found and fixed: Phase 1's group rule (a group the owner never wrote in is removed) dropped a chosen mail thread where the owner was only a recipient; DatabaseManager.tidy_groups(keep=('Mail',)) spares mail conversations (mail now only comes in as the owner chose it). A mail met again in another account is unchanged in Chattr, so its second account comes from the import job (seen = the working mbox's Message-IDs). Master.delete_items also deletes an item's mail rows.

### 2026-11-20
T03: mail.import.preview, mail.import (a mail-import job: the chosen threads copied into .caixa/work/mail/import-<job>.mbox, the Mail collector run with the account and workers inside an undo snapshot, record_mail with the mails seen, the working mbox removed), caixa mail import. Imported in Sort mail = senders (and the owner's correspondents) all of whose mail in this mbox is in the box, so a newer export with new mail from someone keeps them to import. Sort mail gained its Import button (asks with the preview's counts, follows the job, shows Imported, asks for the senders again); Jobs label and failure toast for mail-import; window rebuilt. mypy: import chattr.commands as a module, as the collector does.
