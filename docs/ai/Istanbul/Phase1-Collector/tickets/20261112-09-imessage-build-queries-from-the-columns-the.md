---
id: 20261112-09-imessage-build-queries-from-the-columns-the
title: 'iMessage: build queries from the columns the database has'
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

The iMessage reader had two fixed queries, 'new' and 'old', and fell back from one to the other on an error. Message schemas differ between macOS releases and even between two Macs on one release, so a new macOS could make the import fail or silently lose columns. The maintainer runs the newest macOS.

## Acceptance criteria

- [x] The reader looks at the live schema once and asks only for columns that exist; missing ones read as empty.
- [x] An old database (seven message columns) imports with no fallback and no complaint; columns the reader does not know are ignored.
- [x] Paired and optional features are detected: filter categories (both columns), recently deleted, conversation lookup, person-centric IDs, replies, edits, tapbacks.
- [x] A database with no `message` table says it is not a Messages database.
- [x] `chattr-cli doctor` lists the schema's capabilities.

## Context

Ported from imessage-exporter 5.0.1 (`tables/capabilities.rs`, `tables/messages/columns.rs`). New module `chattr/imessage_schema.py`: `Capabilities.determine`, `message_select`. The single and the parallel read paths now share one projection. The projection already carries the columns the later tickets need (replies, edits, group events, filter categories, payloads).

## Subtasks

- [x] Tests with an old schema, an unknown column, optional tables, a non-Messages database (tests/test_imessage_schema.py).
- [x] `imessage_schema.py`.
- [x] The parser uses it for both read paths; `NotMessagesDatabase` reaches the person as a plain message.
- [x] `doctor` prints the capabilities.

## Implementation plan

Status: done
Current task:

### T01: Tests with an old schema, an unknown column, optional tables, a non-Messages database (tests/test_imessage_schema.py).
### T02: `imessage_schema.py`.
### T03: The parser uses it for both read paths; `NotMessagesDatabase` reaches the person as a plain message.
### T04: `doctor` prints the capabilities.

## Completion report

- **Outcome:** The reader adapts to whatever columns the database has.
- **Files:** tools/chattr/src/chattr/imessage_schema.py, parsers/imessage_database_parser.py, commands.py, imessage_tools.py, tools/chattr/tests/test_imessage_schema.py
- **Errors:** none
- **Verify:** Chattr suite 717 passed; whole Python suite passed; mypy clean.

## Review

Clean. Not covered: a UTF-16 database (upstream casts text to preserve its bytes); none has been seen and it is left out. No real macOS 27 database has been read here: NEEDS MAINTAINER CONFIRMATION from `chattr-cli doctor` on the real chat.db.

## Notes

- 2026-11-13: The maintainer's database reports recently deleted messages, reply threads, tapbacks and filter categories as detected (from imessage-exporter's own diagnostic).
