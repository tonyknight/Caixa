---
id: 20261112-12-imessage-edited-and-unsent-messages-replies-group
title: 'iMessage: edited and unsent messages, replies, group events'
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

The reader ignored everything about a message except its text, tapbacks and files: replies lost what they answered, an edited message showed one version, an unsent message was an empty bubble, and the rows Messages uses for events (someone added, the conversation named, …) were imported as blank messages.

## Acceptance criteria

- [x] A reply records what it answers and the page links to it with its first words (across year pages too).
- [x] An edited message shows its final text and keeps the earlier versions with their times, in an 'Edited' fold.
- [x] A wholly unsent message is a line saying who unsent it.
- [x] Rows with `item_type` other than 0 are sentences: added, removed, changed number, named, name removed, left, group photo, background, location sharing, kept audio, SOS transcript, emergency location; unknown ones are shown with their codes; an event with no actor names nobody.
- [x] The raw codes are kept with the message.

## Context

Ported from imessage-exporter 5.0.1. `chattr/imessage_events.py`: `edit_history` (binary property list: `ec` edits per part with `d` seconds since 2001 and `t` a typedstream, `rp` unsent parts, `otr` the parts) and `announcement`. The parser's `Message` now carries every probed column (`raw`). Stored without a schema change: `reply_to` holds the answered message's GUID (resolved when the page is drawn), edits and codes go in `service_specific`.

## Subtasks

- [x] Tests: the decoders, the importer, the page (tools/chattr/tests/test_imessage_events.py).
- [x] `imessage_events.py`.
- [x] The parser: `Message.raw`, replies, edits, unsent, events as system records.
- [x] Pages: the reply line, the edit fold; styles.
- [x] Collector.md and NOTICE.

## Implementation plan

Status: done
Current task:

### T01: Tests: the decoders, the importer, the page (tools/chattr/tests/test_imessage_events.py).
### T02: `imessage_events.py`.
### T03: The parser: `Message.raw`, replies, edits, unsent, events as system records.
### T04: Pages: the reply line, the edit fold; styles.
### T05: Collector.md and NOTICE.

## Completion report

- **Outcome:** Replies, edits, unsent messages and conversation events are read and shown.
- **Files:** tools/chattr/src/chattr/{imessage_events,render,pages}.py, parsers/{imessage_parser,imessage_database_parser}.py, templates/{page,base}.html, tools/chattr/tests/test_imessage_events.py, docs/Documentation/Collector.md, tools/chattr/NOTICE
- **Errors:** none
- **Verify:** Chattr suite 770 passed; whole Python suite passed; black and mypy clean.

## Review

Minors. (1) A message with several parts where only some were edited or unsent: the history is kept per part, but the page shows the message as one bubble (upstream draws one bubble per part). (2) An edit made after the message was first imported changes its text, so a later import updates it; an edit history added without a text change is not picked up, because a message is only rewritten when its content changes. (3) Text effects, mentions and expressive send styles are not read. (4) The sentences are English only.

## Notes

- 2026-11-13: Tested against databases built by the tests from upstream's description; NEEDS MAINTAINER CONFIRMATION on real edited and unsent messages.
