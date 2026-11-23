---
id: 20261123-03-merge-people-anywhere-by-dropping
title: Merge people anywhere by dropping
type: bug
priority: high
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Merge anywhere by dropping; people with mail can be merged and deleted
parent:
depends_on: []
subtasks: []
---
## Description

In Safari, dropping a person on another in Friends asked to merge, but after Merge nothing was
merged; in Unrecognized a drop did nothing. The maintainer wants merging wherever people can be
dragged, the one dropped on keeping their name.

Cause: a person whose imported mail was filed with them (`mail_threads.home_person_id`) could not
be removed from the master, so `people.merge` (and `people.delete`) failed on the foreign key; the
page only said so in the status bar. A drop on a tile with no name was refused ("Name … first").

## Acceptance criteria

- [x] People with mail can be merged (their mail threads go to the one who stays) and deleted.
- [x] One or several people dropped on someone join them, in every view; the one dropped on keeps
      their name.
- [x] A tile with no name dropped on becomes a person under the name it shows; one showing only its
      number or address joins a named person dropped on it.
- [x] A failed merge is shown in a dialog.

## Context

- `caixa/master.py` (`merge_people`, `delete_person`), `caixa/service.py` (`people.join`)
- `tools/chattr/src/chattr/templates/index.js` (drop, `joining`, `confirmMerge`, `merge`, `tell`)
- Requirements: **Merging by dropping**.

## Subtasks

- [x] T01 Mail threads follow a merge and let go on delete; `people.join`; drop anywhere.

## Implementation plan

Status: done
Current task: T01

### T01: Merge anywhere

- `Master.merge_people`: move `mail_threads.home_person_id` to the target; `delete_person`: clear
  it (the next redraw files the mail again).
- `people.join(target | name + target_handles, people, handles)`: all of it or nothing; the owner
  is never merged away; registered as a write method.
- Page script: drop on any tile not being dragged, with any number dragged; the plan (`joining`)
  picks the name; confirm; one `people.join` call; tiles updated; errors in a dialog (`tell`).
- Tests: `tests/test_merge_anywhere.py` (mail recorded as the mail window does: merge, delete,
  join named, join a tile with no name, a person onto one, refusals);
  `web/tests/e2e-categories.test.ts` (a number onto a person, a person onto a bare number, one
  Unrecognized tile onto another); `tests/test_worker_protocol.py` (method lists).
- Verify: Chattr, Caixa and web suites.

## Completion report

- **Outcome:** Merging works for people with mail, and anywhere: named or not, one or several,
  the one dropped on keeping their name. Deleting people with mail works too.
- **Files:** `caixa/master.py`, `caixa/service.py`, `tools/chattr/src/chattr/templates/index.js`,
  `tests/test_merge_anywhere.py` (new), `tests/test_worker_protocol.py`,
  `web/tests/e2e-categories.test.ts`; Requirements.
- **Errors:** The first merge test picked a thread with no home (its subject ends in "?"). The
  method lists in the protocol tests needed `people.join`.
- **Verify:** Chattr 891 passed; Caixa 1502 passed, 1 skipped; web 273 passed. The new tests failed
  before the fix with "FOREIGN KEY constraint failed", as in the maintainer's box. Safari itself
  could not be run here (Chromium only).

### Review

Clean. Minor: two tiles that both show only a number make a person named by the number dropped
on; it can be renamed.

## Notes

Append-only running log. Each entry dated.
