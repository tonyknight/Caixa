---
id: 20261112-11-imessage-copy-attachments-into-the-box-and-report
title: 'iMessage: copy attachments into the box, and report the ones missing from
  this Mac'
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

iMessage attachments were recorded but never copied into the box. And Messages only fetches an attachment from iCloud when its part of the conversation has been shown: the maintainer's database names 12,629 attachments, of which 5,274 are not on disk, and found that scrolling back in a conversation makes them appear. A way to see where the missing ones are was asked for.

## Acceptance criteria

- [x] Attachments that are on the Mac are copied (the Mac's store is untouched) and filed at `People/<Person>/iMessage/(date) time sender.ext`.
- [x] A file that is not on the Mac is counted, its message says so, and the import's result says how many.
- [x] Importing again after the file has arrived brings it in, with no left-over 'missing' entry.
- [x] `chattr-cli missing [chat.db] [--list TEXT]` lists the conversations with missing files, the most data first, with first and last dates; the preview in Caixa says how many are missing and where the most are.
- [x] The documented walkthrough gives 9 attachments in the box, 0 not copied.

## Context

The parser stages a copy by content hash (`blobs.store_file_by_hash`, streamed) in the importer's working folder; filing (ticket 20261112-04) then places it under the person. A missing file is recorded under a stand-in hash from its GUID; when the real file arrives the stand-in row is removed (`DatabaseManager.upsert`). `commands.missing_attachments` is read-only and shares nothing with the import.

## Subtasks

- [x] Tests: copy, publish, missing, arriving later, the report and its command (tools/chattr/tests/test_imessage_attachments.py; two collector tests).
- [x] `IMessageParser(attachments_dir=)`, `ConvertResult.missing_attachments`; the central route accepts an attachments folder.
- [x] Stand-in attachment rows give way to the real file.
- [x] `commands.missing_attachments`, `chattr-cli missing`.
- [x] Caixa: the iMessage source stages files and reports missing ones in the preview and the result; Collector.md.

## Implementation plan

Status: done
Current task:

### T01: Tests: copy, publish, missing, arriving later, the report and its command (tools/chattr/tests/test_imessage_attachments.py; two collector tests).
### T02: `IMessageParser(attachments_dir=)`, `ConvertResult.missing_attachments`; the central route accepts an attachments folder.
### T03: Stand-in attachment rows give way to the real file.
### T04: `commands.missing_attachments`, `chattr-cli missing`.
### T05: Caixa: the iMessage source stages files and reports missing ones in the preview and the result; Collector.md.

## Completion report

- **Outcome:** iMessage attachments are in the box; what is still in iCloud is listed by conversation.
- **Files:** tools/chattr/src/chattr/{blobs,commands,cli,database_manager}.py, parsers/imessage_parser.py, caixa/collectors/chattr.py, tests, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** `python -m pytest -q` 1127 passed, 6 skipped; harness 257 passed; mypy clean; the documented check script on a fresh box of the six synthetic sources: 9 in the box, 0 not copied, 0 missing.

## Review

Minors. (1) Caixa cannot make Messages download anything; the report only says where to look. Whether the remaining missing files are link-preview images (the maintainer's guess) is not known: the report could separate them by type in a follow-up. (2) Converting HEIC pictures and MOV video for browsers, which upstream does with `sips`/`ffmpeg`, is not done: files are kept as sent. NEEDS MAINTAINER DECISION if HEIC photos should get a JPEG copy the way AMR audio gets an M4A.

## Notes

- 2026-11-13: The maintainer observed that missing counts fall after scrolling back in a conversation in Messages.
