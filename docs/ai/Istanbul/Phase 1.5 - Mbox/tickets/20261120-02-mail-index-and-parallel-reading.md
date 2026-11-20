---
id: 20261120-02-mail-index-and-parallel-reading
title: Mail index and parallel reading
type: feature
priority: high
status: in-progress
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ''
parent:
depends_on:
- 20261120-01-synthetic-mail-fixtures
subtasks: []
plan_status: in-progress
current_task: T03
---
## Description

Read an `.mbox` (or each `.mbox` in a `.zip`) into `.caixa/mail/index.sqlite` without importing
anything: byte ranges, a SHA-256 of each mail's bytes, headers and thread keys, never bodies in
memory. Split at mail boundaries across up to 12 worker processes; a zip is one stream feeding the
workers. Sources remember their lineage and account.

## Acceptance criteria

- [ ] `index.sqlite` with `sources`, `mails` and `senders` as in *Data model*; readable only by the owner
- [ ] Plain and zipped mboxes, folders holding them, and Takeout zips with several `.mbox` are read with progress and cancel
- [ ] Reading again a file already read (same size, time and first-megabyte hash) is instant
- [ ] The **account** is a required name at read time; a Cleaned or Reduced file gets its parent's
- [ ] A box setting **Workers** (processor count, at most 12); 1 and 12 workers give the same index
- [ ] Memory stays under 500 MB on the generated multi-gigabyte mbox; 12 workers are faster than 1 (slow test)
- [ ] Service method(s) `mail.read`/`mail.status` and `caixa mail read <path> --account NAME`

## Context

Phase 1.5 - Mbox Tasks Breakdown item 2. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Components* (Mail index), *The mbox family*, *Data model*, *Workers*; M1–M3. Phase 1's `chattr/parsers/mbox_parser.py` has the header decoding and thread-key logic to reuse; it reads the whole file into memory, which this must not.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T03

**Design:** a new package `caixa/mail/` (the mail workflow lives in Caixa, beside the
collectors). `caixa/mail/index.py` holds `MailIndex`, a SQLite file at
`<box>/.caixa/mail/index.sqlite` (folder 0700, file 0600; rebuildable, so a schema change simply
starts it again). A mail is the bytes from its `From ` line to the next one (Python's `mailbox`
rule), so the byte ranges of a file, end to end, are the file. Reading a plain mbox: the main
process cuts the file into ranges (8–64 MB) at mail boundaries; each range is read in blocks and
its mails' headers parsed (`email.parser.BytesHeaderParser`, default policy; Chattr's
`normalize_message_id` and `MboxParser._time` reused) by a pool of worker processes
(`concurrent.futures.ProcessPoolExecutor`; one worker means no pool, in-process), results returned
in file order and inserted by the main process. A zip member is one stream: the main process cuts it
into mails and sends batches (~16 MB, at most two per worker waiting) to the pool; offsets are
offsets in the unzipped member, so they hold for an unzipped copy too. Per mail: position, offset,
length, SHA-256 of its bytes, Message-ID, In-Reply-To, References root, Gmail thread id, thread key,
date (UTC, offset, assumed), sender, recipients, subject, labels, number of attachment parts, and the
list and bulk headers ticket 03 classifies on. Thread keys as Chattr's parser (Gmail id, else the
References root, else a parent found by In-Reply-To). Senders are summed per source (names, mails,
size, first and last date). A source is recognised by path and member; the same size, time and
first-megabyte hash means it is not read again. A `[Cleaned]`/`[Reduced]` name gives the kind;
the account is required unless the index already knows the file's. Cancelling is the progress
callback raising, as for imports; the pool is shut down and the source left unread.

### T01: The index and reading a plain mbox

- `caixa/mail/__init__.py`, `caixa/mail/index.py`: schema (`sources`, `mails`, `senders`),
  `MailIndex(path)`, `MailIndex.for_box(box)`, `read(source, account, workers, progress)` for
  `.mbox` files, `ReadResult`, `MailError`; account names checked (usable as a folder name).
- Tests (`tests/test_mail_index.py`, on the noisy fixture): counts and fields (normalized ids,
  decoded subject and names, labels, offset kept, attachments counted); the ranges end to end are
  the file and each SHA-256 matches; thread keys (Gmail thread; References across years); the mail
  without a Message-ID; senders summed; 1 and 4 workers give identical rows; reading again reuses
  the source; a changed file is read again; a file that is not an mbox is refused; no account, a bad
  account; cancelling leaves no half-read source.
- Verify: `python -m pytest -q tests/test_mail_index.py`
- [x] done

### T02: Zips and folders

- `read` takes a `.zip` (every `.mbox` member, streamed) and a folder (every `.mbox` and every
  zip holding one).
- Tests: the plain zip gives the same mails and offsets as the mbox; the Takeout zip gives two
  sources with one account; a folder; a zip without an mbox is refused; workers 1 and 4 agree on a
  zip.
- Verify: `python -m pytest -q tests/test_mail_index.py`
- [x] done

### T03: The Workers setting, `mail.read` as a job, and `caixa mail read`

- `caixa/settings.py`: `workers` (integer, the processor count up to 12, between 1 and 12).
- `caixa/service.py`: `mail.read` (write; queues a `mail-read` job with progress, cancel and
  the result), `mail.sources`; `caixa/worker.py` method list in its description.
- `caixa/cli.py`: `caixa mail read PATH --account NAME [--workers N] [--json]`.
- Tests (`tests/test_mail_service.py`): the job reads and reports; the account comes back for a
  known file; the setting's default and limits; the command line prints the counts.
- Verify: `python -m pytest -q tests/test_mail_service.py tests/test_mail_index.py && python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

### T04: The scale test

- `tests/test_mail_scale.py` (marked `slow`): a 2 GB generated mbox read with 1 and with the most
  workers the computer allows (up to 12); peak memory of the main process and of the workers under
  500 MB; more workers faster than one when the computer has more than one processor; times
  printed.
- Verify: `python -m pytest -q -m slow tests/test_mail_scale.py -s`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: caixa/mail/index.py. Workers are spawned processes (spawn, not fork: Caixa runs jobs in a thread and fork in a threaded process can deadlock); one worker means no pool. A source's mails are stored in one transaction, so a cancelled read leaves nothing. Attachments are counted as Content-Disposition attachment/inline lines (inline signature images included). The list and bulk headers (List-Id, List-Unsubscribe, List-Post, Precedence, Auto-Submitted, Feedback-ID and a few mass-mail services' own) are kept per mail in 'signals' for ticket 03.

### 2026-11-20
T02: zips are read as one stream per .mbox member, batches (16 MB) parsed by the workers with at most two per worker waiting; a zip member is identified by the zip's time and the member's size and CRC. Folders give every .mbox and zip with one, and Apple Mail's '<name>.mbox/mbox' (added: Apple Mail exports each mailbox as such a folder).
