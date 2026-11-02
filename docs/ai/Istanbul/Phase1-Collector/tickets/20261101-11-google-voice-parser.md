---
id: 20261101-11-google-voice-parser
title: Google Voice parser
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 11.
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
current_task: T01
---
## Description

Parse Google Voice Takeout: texts, calls and voicemails with audio.

## Acceptance criteria

- [ ] Texts, calls and voicemails become entries with correct content types
- [ ] Voicemail audio kept as an attachment

## Context

Phase1-Collector Tasks Breakdown item 11. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F1; Stable IDs.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T01

**Design:** `GoogleVoiceParser(BaseParser)` reads a Takeout `Calls/` folder (or its `Voice/` or
`Takeout/` parents). Each page is one text conversation, call or voicemail; the parser reads the
pages' microformat classes with a small tree built on the standard library `html.parser` (no new
dependency). A conversation is the counterpart (or the set of counterparts in a group), so one
person's texts, calls and voicemails form one timeline, as in the box layout's per-person
view. Records: `text`, `call`, `voicemail` content types. Times keep the offset the page states.

### T01: Texts, calls and voicemail records

- Text pages: every message (time with offset, sender number and name, text); "Me" is the
  owner (`is_from_owner`, no sender handle).
- Call pages (Received, Placed, Missed): `call` records with direction and duration in
  `service_specific`; Placed is from the owner, Received/Missed from the counterpart.
- Voicemail pages: `voicemail` records with the transcript, duration, and the audio file.
- File-name kind is authoritative, page classes are the fallback; non-Google-Voice HTML is skipped.
- Tests: the fixture folder (6 records), durations (`PT5M12S`, `PT95S`, `PT1H2M3S`), groups,
  pages with unknown names.
- Verify: `python -m pytest -q tools/chattr/tests/test_google_voice_parser.py`
- [ ] done

### T02: Conversations and voicemail audio kept

- One conversation per counterpart (set); texts, calls and voicemails interleave by time; a group
  chat is a group.
- Voicemail audio (whatever its extension) is stored by hash like mail attachments
  (`blobs.store_by_hash`) and recorded as the message's attachment.
- Tests: fixture conversations; audio bytes intact and stored once; a voicemail without audio
  still imports.
- Verify: `python -m pytest -q tools/chattr/tests/test_google_voice_parser.py`
- [ ] done

### T03: Import and `chattr-cli convert googlevoice`

- `commands.convert(..., "googlevoice", <folder>)`; folder input allowed for this service.
- Central route, `--json`, `--html`, `--attachments-dir` (default
  `Output/GoogleVoice/Attachments`), `--owner`, `--aliases`; menu entry.
- Tests: counts, content types, owner flag, durations, idempotent re-import, subcommand, JSON.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
