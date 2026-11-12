---
id: 20261112-10-imessage-group-handles-into-people-read-macos
title: 'iMessage: group handles into people, read macOS Contacts, merge split conversations'
type: feature
priority: medium
status: done
created: 2026-11-12
updated: 2026-11-12
closed: 2026-11-12
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Messages stores one handle per (address, service) and can split one conversation into several chats. Imported as they are, one person becomes several folders and one conversation several. The maintainer's database has 1,454 handles of which 209 merge into another, 25 duplicated chats, and no names resolved without Contacts.

## Acceptance criteria

- [x] Handle rows are one person when they share an address, a non-empty `person_centric_id`, or a Contacts card.
- [x] Chats with the same people and the same kind are one conversation (named ones only with the same name; unnamed ones join the earliest named); chats tied in `chat_lookup` are one; chats with nobody are left alone.
- [x] A split conversation is imported as one, with everyone's addresses as its participants.
- [x] Naming one address of a group names the others; two different names in a group are left alone.
- [x] People are named from the Mac's Contacts databases (every account under Sources/), read-only; the card marked 'me' gives the owner's addresses; a missing or unreadable database is skipped.
- [x] The Caixa iMessage source has a `mac_contacts` option (on by default); `chattr-cli convert imessage --mac-contacts`.

## Context

Ported from imessage-exporter 5.0.1. `chattr/imessage_groups.py` (union-find over handles, then chats), `Contacts.from_macos`, Chattr schema version 5 (`handle_groups`), `DatabaseManager.group_handles` and name sharing inside `resolve_people`. Differences from upstream, on purpose: the chat that stands for a merged conversation is its earliest named chat (else its earliest), not the most recently active, so the conversation's identity does not change as messages arrive.

## Subtasks

- [x] Tests: grouping, merging, the parser, name sharing, the address book (tools/chattr/tests/test_imessage_people.py).
- [x] `imessage_groups.py`; the parser groups before it reads and routes messages to the merged conversation.
- [x] `Contacts.from_macos`, `Contacts.merge`, the 'me' card as owner addresses.
- [x] Schema 5 and name sharing within a group.
- [x] `mac_contacts` in `convert_imessage`, the CLI and the Caixa collector; NOTICE and Collector.md.

## Implementation plan

Status: done
Current task:

### T01: Tests: grouping, merging, the parser, name sharing, the address book (tools/chattr/tests/test_imessage_people.py).
### T02: `imessage_groups.py`; the parser groups before it reads and routes messages to the merged conversation.
### T03: `Contacts.from_macos`, `Contacts.merge`, the 'me' card as owner addresses.
### T04: Schema 5 and name sharing within a group.
### T05: `mac_contacts` in `convert_imessage`, the CLI and the Caixa collector; NOTICE and Collector.md.

## Completion report

- **Outcome:** One folder per person and one conversation per conversation, named from the Mac's Contacts.
- **Files:** tools/chattr/src/chattr/{imessage_groups,people,schema,database_manager,commands,cli}.py, parsers/imessage_parser.py, caixa/collectors/chattr.py, tools/chattr/NOTICE, docs/Documentation/Collector.md, tools/chattr/tests/test_imessage_people.py
- **Errors:** none
- **Verify:** `python -m pytest -q` 1117 passed, 6 skipped; black and mypy clean.

## Review

Minors. (1) The Contacts databases here are built by the tests from upstream's description of the schema; a real macOS 27 address book has not been read. NEEDS MAINTAINER CONFIRMATION that names resolve on the real Mac (upstream reported 0 of 1,246 resolved for the maintainer, which suggests its own Contacts read found nothing: worth checking Full Disk Access first). (2) If a later import merges chats differently (a new Contacts link), messages already imported stay in the conversation they were first put in. (3) iOS backups' Contacts format is not read.

## Notes

- 2026-11-13: Full access to Contacts approved by the maintainer.
