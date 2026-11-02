---
id: 20261101-09-messenger-and-instagram-parser
title: Messenger and Instagram parser
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: encoding, UTC, threads, links, attachments, Instagram.'
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
plan_status: done
---
## Description

Complete the Messenger/Instagram parser.

## Acceptance criteria

- [x] Encoding fix applied to all text fields
- [x] Attachments recorded
- [x] Shared links stored, not folded into the body

## Context

Phase1-Collector Tasks Breakdown item 9. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F1; Chattr — Carry forward.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

### T02: Instagram and the unified records

- `InstagramParser` and `convert instagram`; an `Instagram` service folder, default settings and
  state.
- The conversation is named from the thread title and keyed by `thread_path`; more than two
  participants make a group.
- `records_from_parser` carries lists of attachments, reactions, link and link text.
- Tests: both fixture threads reach the archive with attachments, reactions, links; re-import is
  idempotent.
- Verify: `python -m pytest -q`
- [x] done

### T03: Media archive for Messenger and Instagram

- `--attachments-dir` works for Messenger and Instagram (every attachment of every message).
- Tests: the fixture photo is archived dated by its message; originals untouched.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** Messenger and Instagram exports convert into the central archive
  (`chattr-cli convert messenger|instagram <message_1.json>`): every text field decoded, UTC
  times, whole threads, every attachment (hashed) and reaction, shared links stored beside the
  body, calls, unsent messages and group events kept. Conversations are keyed by thread path and
  named by title; `--attachments-dir` archives media for every service.
- **Files:**
  - Rewritten: `parsers/messenger_parser.py` (plus `InstagramParser`).
  - Changed: `records.py` (attachment and reaction lists), `commands.py` (thread conversations,
    safe file names, media archive for all services), `cli.py`, `preflight.py`, `importing.py`.
  - New: `defaults/Services/Instagram.json`.
  - Tests: `test_messenger_parser`, `test_messenger_records`, `test_messenger_media`.
- **Errors:** found and fixed, each with a test:
  - Times came from `datetime.fromtimestamp`, the machine's zone.
  - Only the first photo or video of a message was recorded.
  - Threads split over `message_2.json` and later were silently cut short.
  - The encoding fix crashed on text that was already proper UTF-8.
  - The share link and preview were folded into the body.
  - A thread path as a file name would have contained a slash.
- **Verify:** `python -m pytest -q` → 282 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean.

## Review

### 2026-11-02: d22788a..HEAD (T01–T03), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** layouts were built from the fixture family, not from real exports. Check against a
  real Messenger and Instagram download (field names such as `audio_files`, `sticker`,
  `call_duration`, `is_unsent`, `Subscribe` come from memory of the format).
- **Minor:** a reaction carries only an emoji and an actor in these exports; no time or target part
  is stored.
- **Minor:** Meta lets a person's name change between exports; people are matched by name here.
  Ticket 14 resolves identities.
- **Minor:** `photos[i].creation_timestamp` is ignored; archived names use the message time
  (UTC). Ticket 13 settles which date wins.
- **Minor:** a thread with its other files missing (`message_2.json` absent) is read as far as it
  goes, without a warning.
- **Spec:** all three acceptance criteria are met. Files match the plan.
- **TDD:** RED then GREEN for every task (T01 collection error then 19 passing, T02 7 failing, T03
  3 failing).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: parser rewritten. Found: (1) timestamps used datetime.fromtimestamp, i.e. the machine's local zone, so the same export gave different times on different machines; now aware UTC. (2) Only the first photo or video of a message was recorded; now every attachment kind. (3) Threads over one file (message_2.json, …) were silently cut to message_1.json; now read whole. (4) The encoding fix crashed on text that was already proper UTF-8 (newer exports); now tolerant. (5) The share link and preview were folded into the body as '[Shared Link: …] Preview: …'; now shared_link/link_text. Reactions, calls, unsent messages and group events kept. 'photos[i].creation_timestamp' is not used yet (ticket 13 will use file dates).

### 2026-11-02
T02: Instagram is a service of its own (InstagramParser, Services/Instagram.json default, Output/Instagram, state key). Conversations from Meta exports are keyed by thread_path (survives a renamed export folder) and named by the thread title; more than two participants make a group. Found: naming files by source_id would have put the thread path's slash into file names; a _file_stem() now sanitises names for JSON and HTML files (also used for iMessage). Reactions have only an emoji and an actor: stored as type 'Reaction' with the emoji, no timestamp, no target part. The menu gained Instagram, shifting iMessage to choice 4.

### 2026-11-02
T03: media archive now covers every attachment of every message for all services (the single-file WhatsApp case and Meta's attachment lists share _media_files); --attachments-dir is accepted for messenger and instagram.
