---
id: 20261123-04-mail-import-stops-when-two-readers-store-one
title: Mail import stops when two readers store one attachment
type: bug
priority: high
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Each writer has its own temporary file; missing files named, not blamed on
  voicemail
parent:
depends_on: []
subtasks: []
---
## Description

Importing a larger mailbox stopped with "No voicemail.db and no voicemail audio files named like
'(2018-12-21) 15 02 31 - Jane Smith.amr' were found in …/work/mail/import-565.mbox".

Two faults: Chattr reported every FileNotFoundError while parsing as missing voicemail, whatever
the source; and the real one: a larger mbox is read by several worker processes, and two storing
the same attachment at once (a signature logo in mails of two batches) both wrote
`<hash>.part`. The first moved it into place; the second's move found nothing.

Nothing from the failed import was stored: the parse runs before anything is written to the
archive, so the import can simply be run again.

## Acceptance criteria

- [x] Writers storing the same file at once each succeed; the file is whole; no `.part` is left.
- [x] A missing file in a mail (or any non-voicemail) import is named as such, not blamed on
      voicemail; a missing voicemail database still says so.

## Context

- `tools/chattr/src/chattr/blobs.py` (`store_by_hash`, `store_file_by_hash`)
- `tools/chattr/src/chattr/commands.py` (`_convert_batches`)

## Subtasks

- [x] T01 A temporary file per writer; the right message for a missing file.

## Implementation plan

Status: done
Current task: T01

### T01: Own temporary files, honest message

- `blobs._place`: write to `<name>.<pid>-<random>.part`, move into place, remove the temporary on
  failure (the file's permissions stay as before, unlike `mkstemp`).
- `_convert_batches`: the voicemail message only for voicemail with no file named; otherwise
  "A file went missing while reading … : <file>. Nothing from it was imported; try again."
- Tests: `tools/chattr/tests/test_blobs_race.py` (a second writer finishing first, for bytes and
  for files; the message for a mail import).
- Verify: Chattr and Caixa suites.

## Completion report

- **Outcome:** Concurrent workers no longer stop a mail import over a shared attachment; a
  missing file is reported for what it is.
- **Files:** `tools/chattr/src/chattr/blobs.py`, `commands.py`,
  `tools/chattr/tests/test_blobs_race.py` (new).
- **Errors:** A first draft used `mkstemp`, which would have made every stored file readable by
  its owner only; replaced by a unique name.
- **Verify:** Chattr 894 passed; Caixa 1506 passed, 1 skipped. The new tests failed before the fix
  with the same FileNotFoundError and the voicemail message.

### Review

Clean. The last of several identical writes wins with identical bytes.

## Notes

Append-only running log. Each entry dated.
