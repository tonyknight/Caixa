---
id: 20261101-11-google-voice-parser
title: Google Voice parser
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: texts, calls, voicemail with audio.'
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
plan_status: done
---
## Description

Parse Google Voice Takeout: texts, calls and voicemails with audio.

## Acceptance criteria

- [x] Texts, calls and voicemails become entries with correct content types
- [x] Voicemail audio kept as an attachment

## Context

Phase1-Collector Tasks Breakdown item 11. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F1; Stable IDs.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

### T02: Conversations and voicemail audio kept

- One conversation per counterpart (set); texts, calls and voicemails interleave by time; a group
  chat is a group.
- Voicemail audio (whatever its extension) is stored by hash like mail attachments
  (`blobs.store_by_hash`) and recorded as the message's attachment.
- Tests: fixture conversations; audio bytes intact and stored once; a voicemail without audio
  still imports.
- Verify: `python -m pytest -q tools/chattr/tests/test_google_voice_parser.py`
- [x] done

### T03: Import and `chattr-cli convert googlevoice`

- `commands.convert(..., "googlevoice", <folder>)`; folder input allowed for this service.
- Central route, `--json`, `--html`, `--attachments-dir` (default
  `Output/GoogleVoice/Attachments`), `--owner`, `--aliases`; menu entry.
- Tests: counts, content types, owner flag, durations, idempotent re-import, subcommand, JSON.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `chattr-cli convert googlevoice <Takeout folder>` imports Google Voice into the central
  archive: texts (`text`), calls (`call`, with direction and duration) and voicemails
  (`voicemail`, with transcript, duration and the audio kept by hash), each with the offset the
  page states. One conversation per counterpart, so a person's texts, calls and voicemails share
  one timeline. The folder may be `Calls/`, `Voice/` or `Takeout/`. Re-import changes nothing.
- **Files:**
  - New: `parsers/google_voice_parser.py`.
  - Changed: `commands.py` (`_convert_batches` replaces the mail-only helper; folder services),
    `cli.py` (choice, folder prompt), docs.
  - Tests: `test_google_voice_parser`, `test_google_voice_import`.
- **Errors:** none in existing code. Notes:
  - The page layout is from the fixture (built from the format's documented microformat classes),
    not from a real Takeout.
  - The `Google Voice` display name and `googlevoice` key reuse the existing defaults file
    (`Services/GoogleVoice.json`) and output folder.
- **Verify:** `python -m pytest -q` → 356 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean.

## Review

### 2026-11-02: 20cfc59..HEAD (T01–T03), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** verify against a real Takeout: file-name patterns, group conversation naming,
  MMS attachment markup (images and videos in texts are read from `<img>` and `a.photo` only, from
  memory), and times stated in local time without an offset.
- **Minor:** Google Voice has no record ids, so message ids are hashes of (conversation, time,
  sender, text, occurrence); an edited or re-timestamped export would re-add entries.
- **Minor:** a text page that contains only the owner's messages is filed under the name from the
  file name, with no number; people resolution (ticket 14) should link it.
- **Minor:** the owner's own number (the "Me" vcard) is dropped rather than recorded; ticket 14
  can derive it.
- **Minor:** pages are read whole into memory one at a time; fine for Takeout sizes.
- **Spec:** both acceptance criteria are met. Files match the plan. T01 and T02 were implemented
  together because they share the parser; their tests were written first and cover both.
- **TDD:** RED then GREEN (collection error, then 18/19 passing with one wrong path in the test
  fixed; T03 first run 10 failing).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: GoogleVoiceParser reads Takeout pages with a small stdlib html.parser tree (no new dependency). File-name kind (Text/Received/Placed/Missed/Voicemail) is authoritative, page wording the fallback; 'Me' is the owner (no sender handle). Times keep the offset the page states (aware, tz not assumed). Calls: direction + duration_seconds in service_specific; voicemails: transcript, duration, audio. Pages of other kinds (greetings etc.) are skipped. Group conversation pages are detected by more than one non-owner sender.

### 2026-11-02
T02: one conversation per counterpart (set of counterparts for a group), so texts, calls and voicemails with a person form one timeline. Voicemail audio is found via the <audio> src or a same-named file beside the page, whatever its extension, and stored by hash (blobs.store_by_hash) when an attachments_dir is given. A voicemail with no audio still imports. A text page where only the owner wrote is filed under the name from the file name.

### 2026-11-02
T03: convert googlevoice wired; commands._convert_batches now serves mail and Google Voice (parser classes take owner/aliases/attachments_dir); folder input accepted for FOLDER_SERVICES; default attachment folder Output/GoogleVoice/Attachments; menu choice 6.
