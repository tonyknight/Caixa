---
id: 20261122-13-characters-the-mail-s-encoding-cannot-explain
title: Characters the mail's encoding cannot explain
type: bug
priority: high
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: Stray bytes recovered (UTF-8, else Windows-1252, else �); imports no longer
  stop
parent:
depends_on: []
subtasks: []
---
## Description

Importing a larger mbox stopped with "UnicodeEncodeError: 'utf-8' codec can't encode character
'\udcf1' ... surrogates not allowed". Python's mail parser keeps each byte that the mail's
declared encoding cannot explain as a stand-in character (U+DC80–U+DCFF); SQLite and UTF-8 refuse
them. The maintainer asked for code that copes with characters that cannot be converted.

## Acceptance criteria

- [x] A mail with stray bytes in its subject, headers or body imports; the import does not stop.
- [x] A stray byte is recovered when it makes sense: UTF-8 first, else Windows-1252 (0xF1 → "ñ").
- [x] A byte nothing explains becomes "�" (U+FFFD).
- [x] The database repairs any record a parser hands it (safety net for every source).

## Context

- `tools/chattr/src/chattr/parsers/mbox_parser.py` (`_record`, `_synthetic_id`, attachment names)
- `tools/chattr/src/chattr/database_manager.py` (`upsert`)
- `tools/chattr/src/chattr/records.py` (hashes encode UTF-8)

## Subtasks

- [x] T01 Recover or replace stand-in characters in mail records and before the database.

## Implementation plan

Status: done
Current task: T01

### T01: Recover or replace stand-in characters

- New `chattr/surrogates.py`: `repair_text(s)` turns each run of U+DC80–U+DCFF back into its
  bytes and decodes them as UTF-8, else Windows-1252, replacing what cannot be mapped with "�";
  `repair(value)` applies it through strings, dicts, lists, tuples and frozen dataclasses.
- `MboxParser._record`: repair the subject, text and display name before they are hashed, and
  return the repaired record (headers, HTML, header block, attachment names).
- `DatabaseManager.upsert`: repair the conversation and each record first.
- Test: `tools/chattr/tests/test_mail_stray_bytes.py` (helper, parser, `convert`, upsert).
- Verify: `cd tools/chattr && python -m pytest -q`; `python -m pytest -q` at the root.

## Completion report

- **Outcome:** Mail with bytes its encoding cannot explain imports. Stray bytes in headers,
  subject, sender name, body (undeclared or wrong charset), HTML, the header block and attachment
  names are recovered as UTF-8, else Windows-1252 ("ñ"), and become "�" only when nothing fits.
  `DatabaseManager.upsert` repairs every record from any parser before storing it.
- **Files:** `tools/chattr/src/chattr/surrogates.py` (new), `parsers/mbox_parser.py`
  (`_headers`/`_header`, `_body` charset fallbacks, repaired record), `database_manager.py`
  (`upsert`), `tools/chattr/tests/test_mail_stray_bytes.py` (new, 5 tests).
- **Errors:** The first GREEN attempt still stored "�": the mail library had already replaced
  undeclared 8-bit text in parsed headers and bodies. Fixed by reading headers from their raw form
  and decoding bodies with charset fallbacks.
- **Verify:** Chattr `pytest -q`: 890 passed. Caixa `pytest -q`: 1491 passed, 1 skipped (shallow
  clone). black and mypy clean on the changed files; ruff clean on the new files.

### Review

Clean. Valid mail decodes exactly as before (declared charset first; the library's own header
parsing runs on the repaired raw value). The repair is a no-op without surrogates (one regex
search per string). Minor: Windows-1252 is a guess for undeclared 8-bit text; it is the usual
charset of the old Western clients that send it.

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
Fixed the surrogate crash the maintainer hit on a larger mbox; tests and both suites pass.
