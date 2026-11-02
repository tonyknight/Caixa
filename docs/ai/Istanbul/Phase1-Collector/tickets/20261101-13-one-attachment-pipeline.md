---
id: 20261101-13-one-attachment-pipeline
title: One attachment pipeline
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: one pipeline, per-person dated names, no collisions.'
parent:
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
plan_status: done
---
## Description

Generalize AttachmentManager for all services.

## Acceptance criteria

- [x] Archival `(YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>` names with no collisions
- [x] Originals kept; date written into standard metadata where supported
- [x] Per-person `Attachments/` folders

## Context

Phase1-Collector Tasks Breakdown item 13. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Organizing principles; F8.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `AttachmentManager` (first built for iMessage) becomes the one pipeline. It archives
`(file, time, sender, person)` items into `<archive>/<Person>/Attachments/` (groups under
`Groups/<Name>/Attachments/`) as `(YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>`:

1. **Plan (parallel):** hash each file and read its capture date.
2. **Name (sequential, sorted by time then source path):** assign `<n>` so names never collide and
   are the same on every run. A small manifest in the archive (`.attachments.json`: relative path →
   source SHA-256) lets a re-run reuse a name whose content it already placed instead of piling up
   copies.
3. **Copy (parallel):** faithful copy by default (conversions stay available as an option), the
   date written into standard metadata on the copy where it is missing and a tool is present.

Originals are never moved or changed. The old symlink-for-duplicates is dropped: a file sent twice
is two dated copies (links break when an archive is zipped or moved). Mail, Google Voice and
voicemail extract their files from containers and keep them by content hash; they join this naming
when the box is assembled (tickets 18, 21): recorded as a Minor follow-up.

### T01: Date names, per-person folders, no collisions, repeatable

- Name `(YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>` from the capture date (EXIF when present) or the
  message time as stated (its own offset), with a `[mmm]` part when milliseconds exist.
- Folder `<Person>/Attachments/`, or `Groups/<Group>/Attachments/`; names are made safe for file
  systems.
- Same second + same sender → numbered; a re-run reuses the names it already placed.
- Tests: `tests/test_attachment_pipeline.py` (manager directly).
- Verify: `python -m pytest -q tools/chattr/tests/test_attachment_pipeline.py`
- [x] done

### T02: Metadata, originals kept, failures isolated

- Faithful copies by default (`convert=False`); originals byte-identical afterwards.
- A missing date is written (`exiftool`, when installed) on the copy only; a date already present
  names the file and is left alone; no exiftool is not an error.
- A file that can't be read doesn't stop the others.
- Tests: fake `exiftool` on `PATH`; originals checked by hash.
- Verify: `python -m pytest -q tools/chattr/tests/test_attachment_pipeline.py`
- [x] done

### T03: Every file-based service uses it

- WhatsApp, Messenger, Instagram and the iMessage JSON route pass sender, person and group to the
  pipeline; archive paths stored on the attachment records are `<Person>/Attachments/<name>`.
- Tests: per-person folders for each service; one folder for a person's files from one service.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `AttachmentManager` is the one attachment pipeline for the file-based services
  (iMessage's JSON route, WhatsApp, Messenger, Instagram). Files are copied to
  `<Person>/Attachments/` (groups: `Groups/<Name>/Attachments/`) as
  `(YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>`, dated by capture date or the message time as
  stated, with names assigned in a fixed order so nothing collides and running again changes
  nothing. Originals are never touched; a missing capture date is written on the copy when exiftool
  is installed; unreadable files don't stop the rest.
- **Files:**
  - Rewritten: the `AttachmentManager` class in `attachment_manager.py`; `media_archive.py`
    (`MediaItem`).
  - Changed: `commands.py`, `imessage_export.py` (sender, person, group passed through).
  - Tests: `test_attachment_pipeline` (the manager directly), `test_attachment_services`, plus the
    WhatsApp, Messenger and iMessage media tests moved to the new layout.
- **Errors:** found and fixed:
  - Numbering of same-second files depended on which parallel worker got there first, and only
    protected a single run.
  - Duplicates became symlinks, which break when an archive is zipped or moved; each file sent is
    now a real dated copy.
  - Conversion (PNG to JPG, and so on) was on by default, quietly degrading screenshots; it is now
    opt-in.
  - A missing exiftool printed a warning per file.
- **Verify:** `python -m pytest -q` → 423 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean. exiftool is not installed in the build container,
  so reading and writing capture dates is tested with a fake exiftool.

## Review

### 2026-11-02: 4906c24..HEAD (T01–T03), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** mail attachments, Google Voice audio and voicemail audio are still stored by content
  hash (`<hh>/<sha256>.<ext>`), not in dated per-person folders; they join this naming when the box
  is assembled (tickets 18 and 21).
- **Minor:** the person folder is the conversation's name (for WhatsApp, the export folder name
  without its "WhatsApp Chat with" prefix; for iMessage the chat name, often a phone number).
  Ticket 14 (people) replaces these with resolved people.
- **Minor:** the manifest `.attachments.json` is how re-runs recognize their own files. Moving or
  renaming archived files, or deleting the manifest, makes a re-run add numbered copies rather
  than overwrite (safe, but duplicates).
- **Minor:** with `convert=True` a re-run is not idempotent (the archived bytes differ from the
  source), so reuse is switched off in that mode.
- **Minor:** iMessage times carry no zone, so file names use UTC for them; a message sent at
  23:41 local can be dated the next day. The same applies to Messenger (UTC).
- **Minor:** Windows reserved device names (`CON`, `NUL`, …) are not special-cased in `safe_name`.
- **Minor:** EXIF dates are read as naive local times and used for naming without checking they
  are plausible (a camera clock reset to 2000 will name a photo 2000).
- **Spec:** all three acceptance criteria are met. Files match the plan.
- **TDD:** RED then GREEN: 20 pipeline tests failed first, then passed; the six service tests
  moved to the new layout; four new service tests.
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: AttachmentManager rebuilt as the one pipeline in three steps (hash+capture date in parallel; names assigned sequentially in time-then-source order; copy in parallel). Names: (YYYY-MM-DD) HH-MM-SS [mmm] <sender> <n>.<ext> in <Person>/Attachments/ or Groups/<Name>/Attachments/; the time is shown as the message states it (its own offset). A manifest .attachments.json (relative path -> source SHA-256) lets a re-run reuse names it already placed; a file it does not know is never overwritten. Names/folders are sanitised (no path escapes). Found: the previous '_claim_path' numbering was nondeterministic across parallel workers and only protected one run.

### 2026-11-02
T02: copies are faithful by default (conversion is now opt-in via convert=True; the old default silently turned PNG screenshots into JPG); originals are never moved or changed (verified by hash in tests). exiftool is looked up once; without it capture dates are simply not read or written (before: a warning per file). A date is written only on the copy, only for formats that can carry one (not GIF/BMP), and only when the file has none; an existing capture date names the file and is left alone. A missing/unreadable file is isolated (status failed).

### 2026-11-02
T03: WhatsApp, Messenger, Instagram and the iMessage JSON route pass sender/person/group into the pipeline (Message.sender and chat_name for iMessage; groups from the parser's group-chat test). The archive path recorded on the attachment records and in the native JSON is now <Person>/Attachments/<name>. Existing service tests moved to the new layout.
