---
id: 20261118-02-imessage-messages-without-a-chat-mixed-into-one
title: iMessage messages without a chat mixed into one (no chat) person
type: bug
priority: high
status: done
created: 2026-11-18
updated: 2026-11-18
closed: 2026-11-18
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Maintainer, 2026-11-18: a contact called '(no chat)' held over 2,000 messages from many people. Looked at the page's structure only (counts, keys; no message text): one iMessage conversation, source id '(no chat)', with 2,597 messages from 420 handles. These are messages chat.db keeps with no chat (their chat was deleted). The parser put every such message into one conversation. Of them: 2,002 received, each with its sender; 417 sent by the owner (whose recipient the record dropped); 178 events of groups that no longer exist.

## Acceptance criteria

- [x] A message without a chat goes to the person it was with (its handle, whoever sent it): their one-to-one conversation when one exists, through handle groups and merged chats
- [x] Otherwise a conversation of its own with them, named for them
- [x] Messages the owner sent with no recipient recorded: one conversation, Sent, recipient not recorded, listed with the groups
- [x] Events (item_type not 0) without a chat are left out
- [x] Importing the same chat.db again removes the old (no chat) conversation, its messages and its files; Caixa then drops the master items and the page

## Context

Shown by the maintainer's own box. No real data was stored or committed; the test uses a synthetic chat.db.

## Subtasks

- [x] Reproduce with a synthetic chat.db: orphans from and to a person with a chat, a person without one, a sent message naming nobody, a lost group's event
- [x] imessage_parser: _home places each orphan; one-to-one chat per handle group; conversations for people without one and for no recipient
- [x] DatabaseManager.drop_conversation; the iMessage import drops the old (no chat) conversation and returns its files; Caixa deletes them from the box
- [x] Guide: what happens to messages without a conversation

## Implementation plan

Status: done
Current task:

### T01: Reproduce with a synthetic chat.db: orphans from and to a person with a chat, a person without one, a sent message naming nobody, a lost group's event
### T02: imessage_parser: _home places each orphan; one-to-one chat per handle group; conversations for people without one and for no recipient
### T03: DatabaseManager.drop_conversation; the iMessage import drops the old (no chat) conversation and returns its files; Caixa deletes them from the box
### T04: Guide: what happens to messages without a conversation

## Completion report

- **Outcome:** No more (no chat) person: those messages are with their people.
- **Files:** tools/chattr/src/chattr/{parsers/imessage_parser.py,database_manager.py,commands.py}, caixa/collectors/chattr.py, tools/chattr/tests/test_imessage_orphans.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q (1285 passed); vitest run (225 passed); black; mypy

## Review

Clean.

## Notes

- NEEDS MAINTAINER CONFIRMATION: the name Sent, recipient not recorded, and listing it with the groups.
- NEEDS MAINTAINER CONFIRMATION: events of groups that no longer exist are left out.
