---
id: 20261123-01-deleted-people-come-back-from-their-mail
title: Deleted people come back from their mail
type: bug
priority: high
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Removed people's mail goes with them; shared threads stay with the others
parent:
depends_on: []
subtasks: []
---
## Description

The maintainer deleted people from the people page; each seemed gone but came back in
Unrecognized. Deleting them there removed the tiles, but closing and opening the page showed them
again (57 people, after the redraw job reported done).

Cause: removing someone (`DatabaseManager.remove_people`) left mail out, a Phase 1 rule from when
mail was an archive by year with nobody's page. Their mail threads stayed; the handles were marked
removed and unnamed, so each thread was filed under the bare address (`Renderer._mail_home`) and
drew an Unrecognized tile. Deleting it there only took the tile off the open page.

## Acceptance criteria

- [x] Deleting someone met in mail deletes the mail threads nobody but them (and the owner) is in;
      no tile comes back, by name or by address, after the redraw or after opening the box again.
- [x] A thread they shared with someone still in the box stays, filed with that person.
- [x] Group conversations on other services keep what removed people wrote (unchanged).
- [x] A box where people were deleted before this fix is cleaned when it is next opened.

## Context

- `tools/chattr/src/chattr/database_manager.py` (`remove_people`)
- `tools/chattr/src/chattr/render.py` (`_mail_home`)
- `tools/chattr/src/chattr/pages.py` (`DRAWING` in `templates_fingerprint`; redraw on opening)
- `caixa/service.py` (`people.delete`), `caixa/owner.py` (removed list)

## Subtasks

- [x] T01 Remove a removed person's mail; file shared threads with someone still in the box.

## Implementation plan

Status: done
Current task: T01

### T01: A removed person's mail goes with them

- `remove_people`: mail conversations count whatever their type; one goes when every other
  handle in it besides the owner is removed (a list or a thread with someone else stays).
  Non-mail groups unchanged.
- `Renderer._mail_home`: pass by removed handles when choosing who a thread is filed with.
- `pages.DRAWING = 2` in the fingerprint, so boxes drawn before are redrawn (and their removed
  people's mail deleted) when opened.
- Tests: `tests/test_remove_mail_people.py` (by name, by address as from Unrecognized, a shared
  thread, a box deleted from before the fix); `tools/chattr/tests/test_remove_people.py` (mail at
  the archive level; the Phase 1 "mail is never removed" test updated).
- Verify: Chattr and Caixa `pytest -q`.

## Completion report

- **Outcome:** Deleted people stay deleted. Their mail threads go with them (by name or from
  Unrecognized); a shared thread stays with the others; a box with earlier deletions is cleaned
  on its next opening.
- **Files:** `tools/chattr/src/chattr/database_manager.py`, `render.py`, `pages.py`;
  `tools/chattr/tests/test_remove_people.py`; `tests/test_remove_mail_people.py` (new).
- **Errors:** The fixture's mail-only people start unnamed; the tests name them first (as sorting
  a tile does). The Phase 1 test that mail is never removed was rewritten for the new rule.
- **Verify:** Chattr `pytest -q`: 891 passed. Caixa `pytest -q`: 1496 passed, 1 skipped (shallow
  clone). black clean; mypy unchanged (pre-existing numpy stub and unused-ignore notes).

### Review

Clean. The removal stays repeatable and still never touches the owner. Minor: the delete dialog's
wording ("Their conversations with you ... are deleted") now holds for mail too; no text change.

## Notes

Append-only running log. Each entry dated.

### 2026-11-23
Fixed: mail was left out of removal, so deleted people came back as addresses in Unrecognized.
