---
id: 20261123-01-deleted-people-come-back-from-their-mail
title: Deleted people come back from their mail
type: bug
priority: high
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Removed people get no tile; their mail is kept (People/Removed/Mail/<Account>)
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

- [x] Removing someone met in mail (from their tile, or from Unrecognized) leaves no tile for them;
      none comes back after the redraw or after opening the box again.
- [x] Every mail stays (decided 2026-11-23: removing ends a person, not their mail). A thread with
      nobody else in it is kept in `People/Removed/Mail/<Account>/` with its attachments and stays
      in the index page's Mail list with the name the mail gives; a thread shared with someone still
      in the box is filed with them.
- [x] Texts on other sources are deleted with them, as before.
- [x] A box where people were removed before this fix is put right when it is next opened.

## Context

- `tools/chattr/src/chattr/render.py` (`_mail_home`, `_mail_page`, `REMOVED`)
- `tools/chattr/src/chattr/pages.py` (`DRAWING` in `templates_fingerprint`; the Mail list's person)
- `tools/chattr/src/chattr/database_manager.py` (`remove_people`: mail untouched, as in Phase 1)
- Requirements, What the box holds: **Removing someone met in mail**.

## Subtasks

- [x] T01 Delete a removed person's mail (pushed as 22be041, reverted in 086afb2: wrong rule).
- [x] T02 Keep a removed person's mail under People/Removed; no tile for them (858b016).

## Implementation plan

Status: done
Current task: T02

### T01: (reverted)

Deleting the mail threads of removed people fixed the returning tiles but threw their mail away.
The maintainer wants every mail kept; reverted before it reached the box.

### T02: Keep their mail, drop their tile

- `Renderer._mail_home`: pass by removed handles; None when nobody else is left.
- `Renderer._mail_page`: with no home, the folder is `People/Removed/Mail/<Account>/`; the
  page keeps a `correspondent` (who the mail names) for the index page's Mail list.
- `pages.DRAWING = 2` in the fingerprint: boxes drawn before are redrawn when opened.
- The delete dialog (people page and Caixa window, English and Chinese) says mail is kept.
- Tests: `tests/test_remove_mail_people.py` (by name, by address, a shared thread, a box removed
  from before the fix); the archive's test that mail is never removed stands.
- Verify: Chattr, Caixa and web suites.

## Completion report

- **Outcome:** Removed people stay off the people page and out of Unrecognized; all their mail is
  kept, under `People/Removed/Mail/<Account>/` when nobody else is in a thread, listed under Mail
  with their name. Shared threads are filed with someone still in the box.
- **Files:** `tools/chattr/src/chattr/render.py`, `pages.py`, `templates/index.js`;
  `web/src/client/locales.ts` and the built `caixa/data/web/`; `tests/test_remove_mail_people.py`
  (new); Requirements (decision recorded).
- **Errors:** T01 took the wrong rule (deleting mail) and was reverted; the revert also took this
  ticket out, restored here. The fixture's mail-only people start unnamed; the tests name them
  first, as sorting a tile does.
- **Verify:** Chattr `pytest -q`: 890 passed. Caixa `pytest -q`: 1495 passed, 1 skipped (shallow
  clone). Web: type check clean, 273 tests passed. The new tests fail without the fix (4 failed).

### Review

Clean. Mail is never removed from the archive; only where a thread is filed changes. Minor: a
person really named "Removed" would share that folder's name; their own page stays separate
(`People/Removed/Removed.html`).

## Notes

Append-only running log. Each entry dated.

### 2026-11-23
Fixed: mail was left out of removal, so deleted people came back as addresses in Unrecognized.

### 2026-11-23
Reverted deleting mail; now kept under People/Removed per the maintainer.
