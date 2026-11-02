---
id: 20261101-08-whatsapp-parser
title: WhatsApp parser
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 8.
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
current_task: T02
plan_status: in-progress
---
## Description

Restore WhatsApp processing from `60b276c:main.py` and extend formats.

## Acceptance criteria

- [ ] iOS and Android/locale date formats parse
- [ ] Continuation lines keep indentation; 'media omitted' kept as placeholders
- [ ] Media renamed and dated via AttachmentManager

## Context

Phase1-Collector Tasks Breakdown item 8. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Chattr — Still missing / Fix; F1.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

### T03: Media renamed and dated by AttachmentManager

- `commands.convert(..., attachments_dir=...)` and `chattr-cli convert whatsapp --attachments-dir`
  copy media through `AttachmentManager` (service "WhatsApp", originals kept) dated by the
  message time.
- Tests: the fixture photo lands as `(2024-03-01) 14-05-09.<ext>` in the archive, the original is
  untouched; Android's `IMG-…-WA0001` likewise.
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
T01: parser rewritten. The old regex only knew the iOS ISO layout and silently dropped 'image omitted' messages; it also stripped continuation-line indentation. Day/month order is decided per file (date_order, date_order_certain; ambiguous 12-hour files assume month-first, ambiguous 24-hour files day-first, with a printed note). Placeholder and encryption-notice wording is English only; other locales need real samples (open follow-up). Attachment lines now set type from the extension and message None; attachment_path resolves against the export folder. Messages are naive local times (no zone in the export), precision minute for Android/US.
