---
id: 20261118-03-owner-replies-in-deleted-imessage-chats-missing
title: Owner replies in deleted iMessage chats missing from their person
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

Maintainer, 2026-11-18, after 20261118-02: the recovered messages showed only what people sent; the owner's replies were missing. In chat.db a message the owner sent in a chat that was since deleted often records no recipient (handle 0), so they all went to 'Sent, recipient not recorded'.

## Acceptance criteria

- [x] A message the owner sent with no recipient goes into the conversation of the message it came after (`reply_to_guid`), or of the message that came after it
- [x] A run of such replies follows along the chain
- [x] Each message so placed says so (service_specific placed_by: reply_to)
- [x] Only those with nothing to follow stay in 'Sent, recipient not recorded'
- [x] A full import rebuilds that conversation, so a box imported before is not left with copies

## Context

Messages keeps reply_to_guid on most messages: the guid of the message each came after in its conversation. It was not read until now.

## Subtasks

- [x] Test: replies with no recipient that follow a person's message, a chain of them, one following a message in an existing chat
- [x] imessage_schema reads reply_to_guid; imessage_parser places waiting messages by following it either way until nothing changes
- [x] A full iMessage import drops the old no-recipient conversation first
- [x] Guide

## Implementation plan

Status: done
Current task:

### T01: Test: replies with no recipient that follow a person's message, a chain of them, one following a message in an existing chat
### T02: imessage_schema reads reply_to_guid; imessage_parser places waiting messages by following it either way until nothing changes
### T03: A full iMessage import drops the old no-recipient conversation first
### T04: Guide

## Completion report

- **Outcome:** The owner's replies in deleted chats are back with the people they were written to, where Messages kept the thread.
- **Files:** tools/chattr/src/chattr/{imessage_schema.py,parsers/imessage_parser.py,commands.py}, tools/chattr/tests/test_imessage_orphans.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q (1287 passed); vitest run (225 passed); black; mypy

## Review

Clean. Not verified on the maintainer's own chat.db (how many replies carry reply_to_guid there is unknown); no time-based guessing is done.

## Notes

- NEEDS MAINTAINER CONFIRMATION: replies that carry nothing to follow stay in 'Sent, recipient not recorded'; placing them by time (the nearest message from someone) would be a guess and is not done.
