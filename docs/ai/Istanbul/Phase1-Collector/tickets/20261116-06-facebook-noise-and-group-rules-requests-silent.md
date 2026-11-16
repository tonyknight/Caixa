---
id: 20261116-06-facebook-noise-and-group-rules-requests-silent
title: 'Facebook noise and group rules: requests, silent members, numbers in groups'
type: feature
priority: medium
status: done
created: 2026-11-16
updated: 2026-11-16
closed: 2026-11-16
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Maintainer, 2026-11-16: unfamiliar names after a Facebook import, possibly from people never messaged directly and spam groups left at once; asked exactly what is read from the download. Then a rule for every group conversation: the owner must have written in it; only members who wrote are brought in; a phone number from a group is never brought in, even if it wrote.

## Acceptance criteria

- [x] message_requests and filtered_threads are left out unless 'Include message requests and filtered messages' is ticked
- [x] Every group conversation (any source) the owner never wrote in is removed; only for a source whose owner is recognised, otherwise all its groups are kept and the import says so
- [x] In groups, members who never wrote lose their place, their reactions keep the emoji without the sender, and handles left with nothing are removed
- [x] A phone number that wrote only in groups is never listed under Not yet named (in the import result, the preview and the People page); a number with a direct conversation still is
- [x] The owner's own Facebook name (from the export's profile) is the owner on Messenger and Instagram
- [x] Each import says what was left out and why; the job's log names each
- [x] The documentation lists exactly which parts of a Facebook download are read

## Context

What a Facebook import read before this: every folder with a message_1.json (inbox, archived_threads, e2ee_cutover, message_requests, filtered_threads), every participant of every thread, every reaction's sender. The unfamiliar names most likely came from members of kept groups who never wrote, and from groups kept because one friend was in them. The three separate 'unresolved' queries now share chattr.database_manager.unresolved_rows. NEEDS MAINTAINER CONFIRMATION: (1) a number from a group stays the sender shown on the group page, and a number Contacts know is shown under that person (rule 3 read as: never brought in as a name to give); (2) the rules are not optional.

## Subtasks

- [x] Leave out requests and filtered threads
- [x] tidy_groups for every source; shared unresolved_rows
- [x] Owner's Facebook name is the owner; notes and log
- [x] Tests and documentation

## Implementation plan

Status: done
Current task:

### T01: Leave out requests and filtered threads
### T02: tidy_groups for every source; shared unresolved_rows
### T03: Owner's Facebook name is the owner; notes and log
### T04: Tests and documentation

## Completion report

- **Outcome:** Done.
- **Files:** tools/chattr/src/chattr/{database_manager,commands,meta_friends}.py, caixa/collectors/{chattr,messages}.py, tests/{test_group_rules,test_messenger_friends,test_messenger_scale,test_chattr_collectors}.py, tools/chattr/tests/test_meta_friends.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1304 passed, 6 skipped; harness vitest: 275 passed; black and mypy clean. Not run on a real Facebook download.

## Review

Self-review, minors only. Checked: removing a group deletes its reactions and attachment rows first; the owner rule never runs for a service with no owner messages; tidy is repeatable.

## Notes

- 2026-11-16: done; two choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
