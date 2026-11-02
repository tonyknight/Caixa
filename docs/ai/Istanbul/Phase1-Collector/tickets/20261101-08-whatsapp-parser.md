---
id: 20261101-08-whatsapp-parser
title: WhatsApp parser
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: formats, placeholders, media records, media archive.'
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
plan_status: done
---
## Description

Restore WhatsApp processing from `60b276c:main.py` and extend formats.

## Acceptance criteria

- [x] iOS and Android/locale date formats parse
- [x] Continuation lines keep indentation; 'media omitted' kept as placeholders
- [x] Media renamed and dated via AttachmentManager

## Context

Phase1-Collector Tasks Breakdown item 8. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Chattr — Still missing / Fix; F1.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `WhatsAppParser` keeps its legacy dict output (`timestamp`, `author`, `message`,
`type`, `attachment_path`) and gains `precision`, `omitted` and `system` details that
`records_from_parser` turns into records. The old media renaming in `60b276c:main.py` is not
revived: the shared `AttachmentManager` (already used for iMessage) does the renaming and dating.
Day/month order is decided per file from the dates themselves; when a file is ambiguous the
parser assumes month-first for 12-hour (US) exports and day-first otherwise, and says so.

### T01: Date formats, continuation lines, placeholders

- iOS `[YYYY-MM-DD, HH:MM:SS]` (and bracketed locale variants), Android `DD/MM/YYYY, HH:MM - `,
  US `M/D/YY, H:MM AM - ` (regular or narrow no-break space before AM/PM).
- Day/month order from the file (`date_order`, `date_order_certain`); 12-hour clocks convert
  correctly (12 AM = 00:xx).
- Continuation lines keep their indentation; a message's trailing whitespace is trimmed.
- Omitted media (`image omitted`, `<Media omitted>`, …) is kept as a placeholder message; the
  encryption notice is a system message with no author.
- Minute precision for Android/US exports, second precision for iOS.
- Tests: the three fixture exports (counts, texts, timestamps, precision), plus ambiguous and
  unambiguous generated files.
- Verify: `python -m pytest -q tools/chattr/tests/test_whatsapp_parser.py`
- [x] done

### T02: Attachments, groups and records

- `<attached: NAME>` and `NAME (file attached)` resolve to the file in the export folder
  (`attachment_path`), with the kind (`image`, `video`, `audio`, `document`, `media`) from its
  extension; a missing file is still recorded.
- `records_from_parser` carries file attachments as `AttachmentRecord` (SHA-256 of the file),
  `precision` as `time_precision`, system notices as `system` messages; empty bodies are None.
- A chat with more than two distinct authors imports as a group conversation.
- HTML tolerates messages without a body.
- Tests: fixture attachments reach the database with hashes; group inference; HTML.
- Verify: `python -m pytest -q`
- [x] done

### T03: Media renamed and dated by AttachmentManager

- `commands.convert(..., attachments_dir=...)` and `chattr-cli convert whatsapp --attachments-dir`
  copy media through `AttachmentManager` (service "WhatsApp", originals kept) dated by the
  message time.
- Tests: the fixture photo lands as `(2024-03-01) 14-05-09.<ext>` in the archive, the original is
  untouched; Android's `IMG-…-WA0001` likewise.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `WhatsAppParser` reads iOS, Android and US-locale exports (day/month order decided
  from the file, 12-hour clocks, minute or second precision), keeps continuation-line
  indentation, keeps omitted media and system notices as messages, and resolves attachment lines to
  the files in the export folder. Media reaches the archive with a SHA-256, and
  `convert whatsapp --attachments-dir` copies it through `AttachmentManager`, renamed and dated by
  the message (originals untouched). Chats with more than two authors import as groups.
- **Files:**
  - New: `media_archive.py`.
  - Rewritten: `parsers/whatsapp_parser.py`.
  - Changed: `records.py` (`records_from_parser` carries attachments, precision, system notices),
    `commands.py`, `cli.py`.
  - Tests: `test_whatsapp_parser`, `test_whatsapp_records`, `test_whatsapp_media`.
- **Errors:** found and fixed, each with a test:
  - The old parser dropped "image omitted" messages and stripped continuation indentation.
  - Only the iOS ISO layout parsed at all.
  - `convert` computed an inferred group type but the import recomputed its own conversation, so
    it would have been lost.
  - Lines with no sender (Android group notices) were stored as text.
- **Verify:** `python -m pytest -q` → 252 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean.

## Review

### 2026-11-02: 18c42d4..HEAD (T01–T03), reviewed in-session

**Verdict:** clean apart from Minor items; the one defect found during review (sender-less lines
stored as text) was fixed with a test before closing.

- **Minor:** placeholder and notice wording ("omitted", "end-to-end encrypted", "(file attached)")
  is English only. Other locales need real samples.
- **Minor:** a system notice whose text contains ": " (for example a renamed group) would be split
  into a fake author. Real exports are needed to tell these apart safely.
- **Minor:** ambiguous files (every date has both numbers 12 or below) are read month-first for
  12-hour clocks and day-first otherwise; the parser prints a note and sets
  `date_order_certain = False`, but nothing is stored in the archive about it yet.
- **Minor:** group detection counts only authors who spoke, so a chat with three members of whom
  two wrote imports as one-to-one. The People work (ticket 14) can correct it.
- **Minor:** archived names use the message time, in the export's own (assumed) zone, and the
  per-service folder layout is ticket 13's to unify. `--attachments-dir` is not yet offered by the
  menu.
- **Minor:** the legacy `60b276c` media code (EXIF writing, video handling, ffmpeg) is not revived:
  `AttachmentManager` is the single path, and ticket 13 extends it.
- **Spec:** all three acceptance criteria are met. Files match the plan, plus `media_archive.py`.
- **TDD:** RED then GREEN for every task (T01 12 failing, T02 5, T03 5, review fix 1).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: parser rewritten. The old regex only knew the iOS ISO layout and silently dropped 'image omitted' messages; it also stripped continuation-line indentation. Day/month order is decided per file (date_order, date_order_certain; ambiguous 12-hour files assume month-first, ambiguous 24-hour files day-first, with a printed note). Placeholder and encryption-notice wording is English only; other locales need real samples (open follow-up). Attachment lines now set type from the extension and message None; attachment_path resolves against the export folder. Messages are naive local times (no zone in the export), precision minute for Android/US.

### 2026-11-02
T02: records_from_parser now carries attachments (SHA-256 of the file, or of the name when the export names a file that was not included), precision as time_precision, omitted placeholders and system notices; empty bodies are stored as no body. Found: commands.convert computed the conversation but import_messages recomputed its own, so an inferred group type would have been lost; the inferred conversation is now passed through. Groups are inferred from more than two distinct authors (a chat where only two of three members spoke imports as one-to-one).

### 2026-11-02
T03: new media_archive.archive_media wraps AttachmentManager (copy, never move; named and filed by date). convert(..., attachments_dir) and --attachments-dir support WhatsApp only; Messenger/Instagram arrive with ticket 09. The archive path is stored as the attachment's storage_path (relative to the archive folder; ticket 13 will redefine storage). A sender-less line is now always a system notice.
