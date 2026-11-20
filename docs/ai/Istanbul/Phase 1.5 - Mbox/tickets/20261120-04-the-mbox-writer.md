---
id: 20261120-04-the-mbox-writer
title: The mbox writer
type: feature
priority: high
status: done
created: 2026-11-20
updated: 2026-11-20
closed: 2026-11-20
notes: 'Done: Cleaned/Reduced names, byte-for-byte copy checked mail by mail, recorded
  in the index.'
parent:
depends_on:
- 20261120-02-mail-index-and-parallel-reading
subtasks: []
plan_status: done
---
## Description

Write a Cleaned or Reduced mbox: the kept mails' byte ranges copied in order, byte for byte, to a
`.part` file, every mail checked against the index (in the workers), then renamed into place. Used by
Clean (ticket 5) and Reduce (ticket 13).

## Acceptance criteria

- [ ] Names and placement as in *The mbox family*: `(YYYY-MM-DD) <name> [Cleaned|Reduced].mbox` in the source's folder (beside a `.zip`); an old date and tag replaced; ` (2)` on a clash
- [ ] Stops before any work when the folder cannot be written or free space is short, saying how much is needed
- [ ] The source is only ever opened read-only; a test checks its bytes and time are unchanged
- [ ] The written file holds exactly the requested mails, byte-identical and in order (checked mail by mail before the rename); a failure leaves no file under the final name
- [ ] The new file is recorded in the index as a child of its source, with its account

## Context

Phase 1.5 - Mbox Tasks Breakdown item 4. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Components* (Mbox writer), *The mbox family*; M6.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/mail/write.py`, `write_mbox(index, source_id, keep, tag)`. The mails to keep are
given by their positions in the source; their byte ranges (from the index) are copied in order,
byte for byte, into `<final name>.part` in the source's folder: from a plain mbox by seeking (runs of
neighbouring mails copied as one), from a zip member as one stream. The `.part` file is then checked
mail by mail (each range's SHA-256 against the index's, in worker processes, and the total size), and
only then renamed to its final name. The new file is recorded in the index as a child of its source,
with the source's account, its mails copied from the source's rows with their new positions and
offsets (status `read`, so it is never read again and its decisions follow it). Names: the base is
the source's file name (a zip member's own name; for Apple Mail's `<name>.mbox/mbox`, the folder's
name) without `.mbox`, an earlier `(YYYY-MM-DD) ` date and ` [Cleaned]`/` [Reduced]` tag; the new
name is `(today) <base> [<tag>].mbox`, with ` (2)`, ` (3)` … before the extension if that name is
taken. The folder is the source file's (a zip's folder; the folder holding an Apple Mail
`<name>.mbox`). Before any work it is checked that the folder can be written and has room for the
mails plus a margin; a failed check, a failed comparison or a cancel leave no file behind. The
source is only ever opened for reading.

### T01: Names, placement and the checks before writing

- `caixa/mail/write.py`: `output_name(source_name, tag, today)`, `output_path(...)` (folder and
  clashes), `preflight(folder, needed)` raising `MailError`.
- Tests (`tests/test_mail_write.py`): plain, already tagged, zip member and Apple Mail names;
  ` (2)` on a clash; an unwritable folder and too little room are refused before anything is
  written.
- Verify: `python -m pytest -q tests/test_mail_write.py`
- [x] done

### T02: Copying, checking and recording the new mbox

- `write_mbox(index, source_id, keep, tag, today=None, workers=1, progress=None)` →
  `WriteResult(path, source_id, mails, size)`; `MailIndex.record_written(...)` in
  `caixa/mail/index.py`.
- Tests: a subset of the plain mbox is written byte-identical, in order, as a valid mbox; the
  source's bytes and time are unchanged; from the zip, beside the zip; 1 and 4 workers write the
  same file; the new file is in the index as a `cleaned` child with the account, and reading it
  again reuses it; a failed check and a cancel leave neither the file nor its `.part`.
- Verify: `python -m pytest -q tests/test_mail_write.py && python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `caixa/mail/write.py` writes a Cleaned or Reduced mbox beside its source:
  `(YYYY-MM-DD) <name> [Cleaned|Reduced].mbox` (an earlier date and tag replaced, ` (2)` on a
  clash; a zip's folder; beside an Apple Mail `<name>.mbox`), after checking the folder can be
  written and has room. The kept mails are copied byte for byte in order into a `.part` file,
  checked mail by mail (size and SHA-256, in the workers), then renamed; a failed check, a cancel or
  an error leave nothing. The new file is recorded in the index as the source's child, with its
  account and the kept mails' rows, so it is never read again.
- **Files:** new `caixa/mail/write.py`, `tests/test_mail_write.py`; changed `caixa/mail/index.py`
  (`record_written`, a shared `_sum_senders`).
- **Errors:** none.
- **Verify:** `python -m pytest -q` → 1347 passed, 1 skipped, 1 deselected; black and mypy clean.

## Review

### 2026-11-20: 6b439ed..HEAD (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** `os.access` says yes to the superuser for any folder; a folder that still cannot be
  written then fails when the `.part` file is opened, which also leaves nothing behind.
- **Minor:** if the source changed after it was read, the copy no longer matches the index and the
  check refuses it ("a mail differs from its source"); the message could say to read the mbox again.
  Ticket 05's window reads the source before cleaning, so it is unlikely.
- **Spec:** M6 met; every acceptance criterion met. Ticket 02's "a Cleaned or Reduced file gets its
  parent's account" is now complete.
- **TDD:** RED then GREEN (collection errors before each task).
- **Commits:** `{ticket-id} {task-id}: {title}`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-20
T02: write_mbox copies runs of neighbouring mails in one go (seek for a plain mbox; read forward through a zip member), fsyncs the .part, checks its size and every mail's SHA-256 (workers share the mails), then renames. record_written copies the kept mails' index rows (flags, protections and thread keys included) with new positions and offsets, so a Cleaned or Reduced mbox is never read again and keeps its account and lineage. This completes ticket 02's 'a Cleaned or Reduced file gets its parent's account'.
