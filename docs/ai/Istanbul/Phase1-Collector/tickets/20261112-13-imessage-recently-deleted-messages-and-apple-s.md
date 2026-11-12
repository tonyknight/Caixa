---
id: 20261112-13-imessage-recently-deleted-messages-and-apple-s
title: 'iMessage: recently deleted messages and Apple''s filter categories'
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

A message deleted in Messages is kept for 30 days in a separate table, outside its conversation, so it was imported into a catch-all conversation with no chat. Messages also gives a message its own filter category (junk, promotion, transaction), which the reader ignored. The maintainer's database has both features.

## Acceptance criteria

- [x] A recently deleted message is read back into the conversation it was deleted from and marked.
- [x] Messages' category is kept with the message (`apple_filter`: junk, promotion, transaction); it reads only when both filter columns exist.
- [x] With spam filtering on, a message Messages called junk is tagged (never dropped); promotions and transactions are categories, not spam. With filtering off nothing is tagged.
- [x] The page marks deleted and categorised messages.
- [x] A conversation event is never also called spam.

## Context

Ported from imessage-exporter 5.0.1 (`query_parts.rs`, `models/filter_action.rs`). The projection joins `chat_recoverable_message_join` when the table exists and takes the chat from it when the message has none. Found on the way: Chattr's own filter tagged event rows (no text) as spam in aggressive mode; an event now wins.

## Subtasks

- [x] Tests (tools/chattr/tests/test_imessage_events.py).
- [x] `message_select` joins the recoverable table; `FILTER_CATEGORIES`.
- [x] The parser records `recently_deleted` and `apple_filter`, and tags junk when filtering is on.
- [x] Marks on the page.

## Implementation plan

Status: done
Current task:

### T01: Tests (tools/chattr/tests/test_imessage_events.py).
### T02: `message_select` joins the recoverable table; `FILTER_CATEGORIES`.
### T03: The parser records `recently_deleted` and `apple_filter`, and tags junk when filtering is on.
### T04: Marks on the page.

## Completion report

- **Outcome:** Deleted messages are back in their conversations; Messages' own categories are kept and shown.
- **Files:** tools/chattr/src/chattr/imessage_schema.py, parsers/imessage_parser.py, pages.py, templates/{page,base}.html, tools/chattr/tests/test_imessage_events.py
- **Errors:** none
- **Verify:** Chattr suite 775 passed; whole Python suite passed; mypy clean.

## Review

Clean. Not done: `filter_sub_action` (finer categories such as 'finance' or 'orders') is read but not interpreted. The maintainer's 2,619 messages 'not associated with a chat' are mostly not recently deleted ones (13 are); the rest still go to the catch-all conversation.

## Notes

- 2026-11-13: NEEDS MAINTAINER CONFIRMATION on the real database: whether tagging Messages' junk as spam is wanted by default.
