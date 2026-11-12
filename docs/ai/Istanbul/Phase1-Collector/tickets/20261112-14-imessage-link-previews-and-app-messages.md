---
id: 20261112-14-imessage-link-previews-and-app-messages
title: 'iMessage: link previews and app messages'
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

Messages that are not text (a link preview, an Apple Pay transfer, a move in a game, a Check In) showed as blank bubbles: only the app's identifier was kept. What they show is in `payload_data`, an NSKeyedArchiver property list.

## Acceptance criteria

- [x] A link preview keeps its address, title, site and summary, and the page shows them; the address is not repeated as the message's text.
- [x] Apple Pay, Check In, Find My, Fitness, polls, Business Chat, handwriting and Digital Touch are named; an app's message shows the app's name and caption.
- [x] A message sent with an effect says which.
- [x] A payload that cannot be read leaves the message named by its kind, never an error.
- [x] Balloons are not tagged as spam.

## Context

Ported from imessage-exporter 5.0.1. `chattr/imessage_payload.py`: `unarchive` (resolves the archive's object table to plain values), `describe`, `effect`. Stored without a schema change, in `service_specific` (`shared_link`, `link_text`, `link_summary`, `link_site`, `app`, `effect`); the page already drew `shared_link`.

## Subtasks

- [x] Tests with archives built by the tests (tools/chattr/tests/test_imessage_payload.py).
- [x] `imessage_payload.py`.
- [x] The parser reads balloons and effects; pages show the preview's site and summary and the effect.
- [x] Collector.md and NOTICE.

## Implementation plan

Status: done
Current task:

### T01: Tests with archives built by the tests (tools/chattr/tests/test_imessage_payload.py).
### T02: `imessage_payload.py`.
### T03: The parser reads balloons and effects; pages show the preview's site and summary and the effect.
### T04: Collector.md and NOTICE.

## Completion report

- **Outcome:** Link previews, Apple Pay and app messages are no longer blank.
- **Files:** tools/chattr/src/chattr/imessage_payload.py, parsers/imessage_parser.py, pages.py, templates/page.html, tools/chattr/tests/test_imessage_payload.py, docs/Documentation/Collector.md, tools/chattr/NOTICE
- **Errors:** none
- **Verify:** `python -m pytest -q` 1168 passed, 6 skipped; harness 257 passed; black and mypy clean.

## Review

This is the readable core of upstream's balloon support, not all of it. Not done, and said so: preview images, Apple Music and Maps details, App Store metadata, collaboration links, poll questions and votes, Check In times, Business Chat forms, and drawing handwritten or Digital Touch messages (they are named, not drawn). The payloads in the tests are built from upstream's description of the format; real ones may hold fields in other shapes, in which case the message is still named by its kind. NEEDS MAINTAINER CONFIRMATION on real link previews.

## Notes

- 2026-11-13: Last of the six iMessage tickets ported from imessage-exporter 5.0.1.
