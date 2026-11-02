---
id: 20261101-09-messenger-and-instagram-parser
title: Messenger and Instagram parser
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 9.
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
current_task: T01
---
## Description

Complete the Messenger/Instagram parser.

## Acceptance criteria

- [ ] Encoding fix applied to all text fields
- [ ] Attachments recorded
- [ ] Shared links stored, not folded into the body

## Context

Phase1-Collector Tasks Breakdown item 9. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F1; Chattr — Carry forward.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T01

**Design:** one parser reads both Meta formats (Messenger and Instagram share the JSON layout);
`MessengerParser` stays the class, `InstagramParser` is a subclass that only changes the service.
The parser keeps the legacy dict output and gains `attachments`, `reactions`, `shared_link` and
`link_text`; it also exposes the thread (`title`, participants, `thread_path`) so the import can
name the conversation and detect groups.

### T01: Parser correctness: encoding, times, threads, links, attachments

- The encoding fix applies to every text field (sender, content, link text, reaction actor and
  emoji, thread title, participants), not only some.
- Times are `timestamp_ms` UTC (aware, millisecond precision), not the machine's local time.
- A thread split over `message_1.json`, `message_2.json`, … is read whole, oldest first.
- Shared links are stored as `shared_link` + `link_text`; the body is the message's own text.
- Every photo, video, audio file, file and sticker is recorded (not just the first), with its
  path resolved against the export root. Reactions are kept. Calls and unsent messages keep their
  place with the right type.
- Tests: the fixture Messenger thread, generated split threads, calls, unsent, groups.
- Verify: `python -m pytest -q tools/chattr/tests/test_messenger_parser.py`
- [ ] done

### T02: Instagram and the unified records

- `InstagramParser` and `convert instagram`; an `Instagram` service folder, default settings and
  state.
- The conversation is named from the thread title and keyed by `thread_path`; more than two
  participants make a group.
- `records_from_parser` carries lists of attachments, reactions, link and link text.
- Tests: both fixture threads reach the archive with attachments, reactions, links; re-import is
  idempotent.
- Verify: `python -m pytest -q`
- [ ] done

### T03: Media archive for Messenger and Instagram

- `--attachments-dir` works for Messenger and Instagram (every attachment of every message).
- Tests: the fixture photo is archived dated by its message; originals untouched.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
