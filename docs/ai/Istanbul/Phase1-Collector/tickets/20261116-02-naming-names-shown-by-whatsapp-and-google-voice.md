---
id: 20261116-02-naming-names-shown-by-whatsapp-and-google-voice
title: 'Naming: names shown by WhatsApp and Google Voice count; deactivated Facebook
  accounts kept'
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

Maintainer decisions of 2026-11-16 after ticket 20261116-01: Facebook friends are a source of names in their own right and merge with Contacts when the names are identical; conversations with deactivated accounts ('Facebook user') come through and the owner links them; WhatsApp and Google Voice senders shown by a name (not just a number) are named people, merging with Contacts on an exact name.

## Acceptance criteria

- [x] A Messenger thread with a 'Facebook user' is kept by the friends filter
- [x] Each 'Facebook user' is a separate handle per thread ('Facebook user (<thread folder>)'), listed under Not yet named
- [x] WhatsApp and Google Voice handles shown by a name are named by that name after Contacts have had their say; numbers, email addresses, '~' self-given WhatsApp names and placeholders are not
- [x] The same name from WhatsApp, Google Voice, Contacts or Facebook is one person

## Context

Merging on identical names was already how the master works (people are found by name); friends were already named by their Facebook name. NEEDS MAINTAINER CONFIRMATION: (a) iPhone voicemail callers named in file names are not taken as names (only WhatsApp and Google Voice were asked for); (b) linking a handle that was named by its own name to another person now needs 'move' (the People page's rename and merge are the usual way).

## Subtasks

- [x] Messenger: tell deactivated accounts apart; keep their threads
- [x] Caixa: name WhatsApp and Google Voice handles by their own names; tests that assumed them unnamed; documentation

## Implementation plan

Status: done
Current task:

### T01: Messenger: tell deactivated accounts apart; keep their threads
### T02: Caixa: name WhatsApp and Google Voice handles by their own names; tests that assumed them unnamed; documentation

## Completion report

- **Outcome:** Done.
- **Files:** tools/chattr/src/chattr/parsers/messenger_parser.py, tools/chattr/src/chattr/meta_friends.py, caixa/collectors/chattr.py, tests/{test_messenger_friends,test_chattr_collectors,test_service_people,test_cli_commands,test_undo,test_worker_protocol}.py, harness/tests/e2e-people.test.ts, docs/Documentation/Collector.md
- **Errors:** Ten tests assumed WhatsApp 'Ana Costa' was unnamed; updated (link with move, or rename).
- **Verify:** python -m pytest -q: 1286 passed, 6 skipped; harness vitest: 270 passed. Not run on a real export.

## Review

Self-review, clean.

## Notes

- 2026-11-16: done; two choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
