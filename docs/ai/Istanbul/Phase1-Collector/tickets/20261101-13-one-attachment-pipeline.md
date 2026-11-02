---
id: 20261101-13-one-attachment-pipeline
title: One attachment pipeline
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 13.
parent:
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
current_task: T02
plan_status: in-progress
---
## Description

Generalize AttachmentManager for all services.

## Acceptance criteria

- [ ] Archival `(YYYY-MM-DD) HH-MM-SS <sender> <n>.<ext>` names with no collisions
- [ ] Originals kept; date written into standard metadata where supported
- [ ] Per-person `Attachments/` folders

## Context

Phase1-Collector Tasks Breakdown item 13. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Organizing principles; F8.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

### T03: Every file-based service uses it

- WhatsApp, Messenger, Instagram and the iMessage JSON route pass sender, person and group to the
  pipeline; archive paths stored on the attachment records are `<Person>/Attachments/<name>`.
- Tests: per-person folders for each service; one folder for a person's files from one service.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: AttachmentManager rebuilt as the one pipeline in three steps (hash+capture date in parallel; names assigned sequentially in time-then-source order; copy in parallel). Names: (YYYY-MM-DD) HH-MM-SS [mmm] <sender> <n>.<ext> in <Person>/Attachments/ or Groups/<Name>/Attachments/; the time is shown as the message states it (its own offset). A manifest .attachments.json (relative path -> source SHA-256) lets a re-run reuse names it already placed; a file it does not know is never overwritten. Names/folders are sanitised (no path escapes). Found: the previous '_claim_path' numbering was nondeterministic across parallel workers and only protected one run.
