---
id: 20261120-02-mail-index-and-parallel-reading
title: Mail index and parallel reading
type: feature
priority: high
status: done
created: 2026-11-20
updated: 2026-11-20
closed: 2026-11-20
notes: 'Done: mail index, zips and folders, workers (2 GB in 9.9 s with 4), mail.read
  job, caixa mail read.'
parent:
depends_on:
- 20261120-01-synthetic-mail-fixtures
subtasks: []
plan_status: done
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

Status: done
Current task: 

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
- [x] done

### T04: The scale test

- `tests/test_mail_scale.py` (marked `slow`): a 2 GB generated mbox read with 1 and with the most
  workers the computer allows (up to 12); peak memory of the main process and of the workers under
  500 MB; more workers faster than one when the computer has more than one processor; times
  printed.
- Verify: `python -m pytest -q -m slow tests/test_mail_scale.py -s`
- [x] done

## Completion report

- **Outcome:** `caixa/mail/index.py` reads an mbox, a zip holding mboxes (one source per member,
  streamed), a folder of them, or an Apple Mail `<name>.mbox/mbox`, into
  `<box>/.caixa/mail/index.sqlite` (owner-only): every mail's byte range and SHA-256, header facts,
  thread key, attachment count and list/bulk headers; senders summed per source. Up to the
  **Workers** setting (processor count, at most 12) spawned processes; the same index whatever the
  number. Reading a known, unchanged file again is instant; a cancelled read leaves nothing.
  `mail.read` (a `mail-read` job) and `mail.sources` in the service, `caixa mail read`, and the Jobs
  page names the job and its result.
- **Files:** new `caixa/mail/__init__.py`, `caixa/mail/index.py`, `tests/test_mail_index.py`,
  `tests/test_mail_service.py`, `tests/test_mail_scale.py`; changed `caixa/settings.py`,
  `caixa/service.py`, `caixa/cli.py`, `tests/conftest.py`, `tests/test_worker_protocol.py`,
  `README.md`, `web/src/client/{api.ts,locales.ts,pages/JobsPage.tsx}`, `web/tests/jobs-page.test.tsx`,
  `caixa/data/web/*` (rebuilt), `tools/chattr/tests/fixtures/builders/noisy_mbox.py` and its test
  (padding for the scale test).
- **Errors:** none in existing code. The first scale run used 600-byte mails (3.5 million in 2 GB;
  one worker took over 10 minutes); the test now uses 40 KB mails, as real mail.
- **Verify:** `python -m pytest -q` → 1327 passed, 1 skipped, 1 deselected (the slow test);
  `python -m pytest -q -m slow tests/test_mail_scale.py` → 2 GB, 53,622 mails: 36.7 s with 1
  worker, 9.9 s with 4, peak 85 MB; black and mypy clean; `vitest run` → 226 passed; `tsc` clean.

## Review

### 2026-11-20: 817e3c8..HEAD (T01–T04), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** a Cleaned or Reduced file "gets its parent's account" only once ticket 04's writer
  records it in the index before it is read; the read already honours an account the index knows.
- **Minor:** cancelling is tested on a plain mbox with one worker; the zip and pool paths share the
  same mechanism (the progress callback raising inside the generator, the pool shut down) but are
  not separately tested. Running workers finish their range before they exit.
- **Minor:** `parse` reuses Chattr's `MboxParser._time`, a private method; if Chattr's parser
  changes it, the index's dates follow.
- **Minor (performance):** header parsing is about 5,000 mails a second per worker; a mailbox of
  millions of very small mails takes minutes per million with one worker.
- **Spec:** M1–M3 met; acceptance criteria met except the parent-account point above (ticket 04).
- **TDD:** RED then GREEN for each task (collection errors; failing zip and folder tests; failing
  service, setting, protocol and Jobs-page tests).
- **Commits:** `{ticket-id} {task-id}: {title}`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T01: caixa/mail/index.py. Workers are spawned processes (spawn, not fork: Caixa runs jobs in a thread and fork in a threaded process can deadlock); one worker means no pool. A source's mails are stored in one transaction, so a cancelled read leaves nothing. Attachments are counted as Content-Disposition attachment/inline lines (inline signature images included). The list and bulk headers (List-Id, List-Unsubscribe, List-Post, Precedence, Auto-Submitted, Feedback-ID and a few mass-mail services' own) are kept per mail in 'signals' for ticket 03.

### 2026-11-20
T02: zips are read as one stream per .mbox member, batches (16 MB) parsed by the workers with at most two per worker waiting; a zip member is identified by the zip's time and the member's size and CRC. Folders give every .mbox and zip with one, and Apple Mail's '<name>.mbox/mbox' (added: Apple Mail exports each mailbox as such a folder).

### 2026-11-20
T03: 'workers' box setting; mail.read (write: queues a 'mail-read' job; account checked at once, and needed unless the index knows the file) and mail.sources (opens the index read-only, never creating it); 'caixa mail read'. The documented method list is the one in tests/test_worker_protocol.py and README.md (worker.py's docstring lists no methods). Added to the window, beyond the plan: the Jobs page names a mail-read job 'Mail read' and shows '60 mails read' as its result instead of import counts (it would have shown 'undefined new'); window rebuilt (with Node 22; esbuild's output does not depend on Node's version).

### 2026-11-20
T04: scale test (slow). First run used the catalogue's tiny mails (about 600 bytes): 2 GB was 3.5 million mails and one worker took over 10 minutes (header parsing is about 5,000 mails a second per worker), so the generator gained 'average' padding (filler lines after a mail's own end) and the test uses 40 KB mails, as real mail with attachments. Result on this 4-processor container: 53,622 mails (2 GB) in 36.7 s with 1 worker, 9.9 s with 4; peak memory 85 MB, largest worker 40 MB.
