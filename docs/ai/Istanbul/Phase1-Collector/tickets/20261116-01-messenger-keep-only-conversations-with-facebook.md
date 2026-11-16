---
id: 20261116-01-messenger-keep-only-conversations-with-facebook
title: 'Messenger: keep only conversations with Facebook friends; name-only contacts'
type: feature
priority: medium
status: done
created: 2026-11-16
updated: 2026-11-16
closed: 2026-11-16
notes: Done; four choices need maintainer confirmation
parent:
depends_on: []
subtasks: []
---
## Description

Maintainer, 2026-11-16: (1) why are handles with recognizable names listed as 'Not yet named'? (2) Messenger imports are full of noise (Marketplace replies and others); Facebook's export lists friends and removed friends, and Messenger should be limited to the people on those two lists.

## Acceptance criteria

- [x] Messenger conversations with nobody on the friends or removed-friends list are left out; a group with at least one friend is kept; a thread that names nobody is kept
- [x] The import (and the preview) says how many were left out; the job's log lists who they were with, without the owner's own name
- [x] Friends and removed friends are named by their Facebook name, so they leave 'Not yet named'
- [x] The lists are found beside the messages in a folder or zip, in the three known layouts; friend requests are not friends; a separately downloaded list can be pointed at; a wrong path is an error
- [x] No list found: everything kept, and said so; 'Only conversations with Facebook friends' can be unticked; Instagram is never filtered
- [x] A contact with a name but no phone or email (vCard or Mac Contacts) now names a handle that is exactly that name

## Context

Answer to (1): a name handle is named only when a contact has exactly that name (case and spacing aside), an alias or the owner says so; there is no fuzzy matching. Found while answering: contacts without a phone or email were dropped entirely, so their names never matched; fixed here. NEEDS MAINTAINER CONFIRMATION: (a) people in Contacts but not on the friends list are left out of Messenger too, as asked; (b) a deactivated friend appears as 'Facebook user' and such a thread is left out; (c) friends are named on every Messenger import even with the filter off; (d) WhatsApp and Google Voice display names (which come from the user's own contacts) are still not taken as names by themselves.

## Subtasks

- [x] Chattr: read Meta friends lists; keep= on convert with LeftOut
- [x] Chattr: name-only contacts count
- [x] Caixa: Messenger options, filter, notes and log, name friends
- [x] Documentation

## Implementation plan

Status: done
Current task:

### T01: Chattr: read Meta friends lists; keep= on convert with LeftOut
### T02: Chattr: name-only contacts count
### T03: Caixa: Messenger options, filter, notes and log, name friends
### T04: Documentation

## Completion report

- **Outcome:** Done. chattr/meta_friends.py reads the lists; commands.convert takes keep=; the Messenger collector filters, reports and names friends via DatabaseManager.name_handles.
- **Files:** tools/chattr/src/chattr/{meta_friends,commands,database_manager,people}.py, caixa/collectors/chattr.py, tools/chattr/tests/{test_meta_friends,test_people,test_imessage_people}.py, tests/{test_messenger_friends,test_translation}.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1283 passed, 6 skipped; harness vitest: 270 passed; black and mypy clean. NOT verified against a real Facebook export: the file names and keys are written from known export layouts; if the maintainer's export uses another, the import will say no list was found.

## Review

Self-review, minors only. Checked: a left-out thread stores nothing, files included; the filter never touches Instagram threads in the same export; the walk up from a thread checks fixed paths only (never searches the whole disk).

## Notes

- 2026-11-16: done; four choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
