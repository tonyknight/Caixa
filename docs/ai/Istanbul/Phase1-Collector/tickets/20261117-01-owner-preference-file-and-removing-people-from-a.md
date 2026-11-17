---
id: 20261117-01-owner-preference-file-and-removing-people-from-a
title: Owner preference file and removing people from a box
type: feature
priority: high
status: done
created: 2026-11-17
updated: 2026-11-17
closed: 2026-11-17
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

The owner keeps what they decided about people in a preference file inside the box, `.caixa/owner.json`, which outlives a reset: names given by hand (a number or address linked to a person, renames, merges), the category each person is in, and the people removed from the box. Removing people replaces the proposed pruning rule (imports stay as they are): a removed person's one-to-one conversations and the files in them are deleted, and later imports do not bring them back.

## Acceptance criteria

- [x] `.caixa/owner.json` (0600) is written after every link, rename, merge, categorize and delete, and read when the box opens and at every import
- [x] Names and categories typed into the file while Caixa is closed are taken up
- [x] A reset keeps the file; forgetting names clears names and categories but keeps the removed list
- [x] Service `people.delete(people, handles)` removes people (by id or name) and unnamed handles; refuses the owner; the redraw job deletes their one-to-one conversations, files, pages and master items
- [x] Removed people stay out after the same export is imported again and after a reset
- [x] Group messages they wrote stay in the group

## Context

Maintainer, 2026-11-17: preference file lives in .caixa ("the .caixa folder is useful for maintaining persistent data"); two manual mass-deletion methods instead of a pruning rule. Chattr schema v6 adds `handles.removed`; master schema v3 allows `delete` in change_log.

## Subtasks

- [x] Chattr: `DatabaseManager.remove_people`, schema v6, removed handles never named or listed
- [x] Master: `delete_items`, `delete_person`, `mark_by_hand`; sync deletes items that left Chattr
- [x] `caixa/owner.py`: load, apply, save, forget_names, add_removed, removed_matcher
- [x] Wire into imports/refresh (`_options`, `_name_people`, `_aliases`) with file deletion inside the box only
- [x] Service `people.delete`, owner file saved after people changes, one shared refresh job
- [x] Reset keeps and uses the owner file; publish redraws an emptied archive

## Implementation plan

Status: done
Current task:

### T01: Chattr: `DatabaseManager.remove_people`, schema v6, removed handles never named or listed
### T02: Master: `delete_items`, `delete_person`, `mark_by_hand`; sync deletes items that left Chattr
### T03: `caixa/owner.py`: load, apply, save, forget_names, add_removed, removed_matcher
### T04: Wire into imports/refresh (`_options`, `_name_people`, `_aliases`) with file deletion inside the box only
### T05: Service `people.delete`, owner file saved after people changes, one shared refresh job
### T06: Reset keeps and uses the owner file; publish redraws an emptied archive

## Completion report

- **Outcome:** Owner file and removing people work end to end on the synthetic family; 1,326 tests pass.
- **Files:** caixa/owner.py, caixa/service.py, caixa/reset.py, caixa/master.py, caixa/schema.py, caixa/collectors/{chattr,messages}.py, tools/chattr/src/chattr/{database_manager,schema,commands}.py, tests/test_owner.py, tools/chattr/tests/test_remove_people.py
- **Errors:** An archive emptied by removal skipped rendering, leaving the old page and index; publish now redraws when a pages list exists.
- **Verify:** python -m pytest -q (1326 passed, 6 skipped); black; mypy clean

## Review

Clean. Files are deleted only inside the box root and never under .caixa.

## Notes

- NEEDS MAINTAINER CONFIRMATION: file name `owner.json`; settings stay in `box.yaml`.
- NEEDS MAINTAINER CONFIRMATION: deleting a person removes one-to-one conversations and their files; their messages in groups the owner took part in stay.
- NEEDS MAINTAINER CONFIRMATION: removals are remembered (re-imports do not bring them back); deleting an entry from `removed` in the file lets them return.
