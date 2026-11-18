---
id: 20261118-04-google-voice-texts-forwarded-to-the-phone
title: Google Voice texts forwarded to the phone duplicated as iMessage
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

Maintainer, 2026-11-18: the messages recovered from '(no chat)' never appeared in Messages; they are Google Voice texts, whose Google Voice export has both sides by day. They were read from chat.db (only the iMessage reader records a transport), so the likely cause is Google Voice forwarding incoming texts to the phone as SMS: Messages kept those (often with no chat left), without the owner's replies, which went through Google Voice. This also explains why the replies did not resurface from chat.db.

## Acceptance criteria

- [x] A message in iMessage's database is dropped when Google Voice has one from the same number (normalised), with the same words (spaces aside), within ten minutes
- [x] Google Voice's record stays; a conversation left with nothing goes; files only those copies showed are deleted from the box
- [x] Runs after every import and redraw, whichever source was imported first; safe to repeat
- [x] The import says how many it found
- [x] Nothing is dropped without a Google Voice twin: other people, other words, or hours apart

## Context

Hypothesis from the maintainer's observation and the data's shape (incoming only; in chat.db); not verified on the maintainer's own data. If Google Voice forwarded from a relay number rather than the sender's, the numbers will not match and nothing is dropped.

## Subtasks

- [x] Test with synthetic data: copies, a number written two ways, another person with the same words, the same person hours later, no Google Voice at all
- [x] DatabaseManager.drop_forwarded_copies
- [x] Caixa: run it in _name_people, note the count, delete the files
- [x] Caixa test through a redraw; guide

## Implementation plan

Status: done
Current task:

### T01: Test with synthetic data: copies, a number written two ways, another person with the same words, the same person hours later, no Google Voice at all
### T02: DatabaseManager.drop_forwarded_copies
### T03: Caixa: run it in _name_people, note the count, delete the files
### T04: Caixa test through a redraw; guide

## Completion report

- **Outcome:** Forwarded copies go; Google Voice's conversations, with both sides, are what the box shows.
- **Files:** tools/chattr/src/chattr/database_manager.py, caixa/collectors/chattr.py, tools/chattr/tests/test_forwarded_copies.py, tests/test_owner.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q (1290 passed); vitest run (225 passed); black; mypy

## Review

Clean. The match is strict (same number, same words, ten minutes), so a real Messages conversation is not touched.

## Notes

- NEEDS MAINTAINER CONFIRMATION: the ten-minute window and exact-words match.
- The 'Sent, recipient not recorded' messages are a separate matter: they are the owner's own messages in chat.db.
