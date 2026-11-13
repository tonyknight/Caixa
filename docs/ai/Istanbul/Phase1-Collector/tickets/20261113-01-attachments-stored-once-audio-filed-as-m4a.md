---
id: 20261113-01-attachments-stored-once-audio-filed-as-m4a
title: Attachments stored once; audio filed as m4a
type: feature
priority: medium
status: done
created: 2026-11-13
updated: 2026-11-13
closed: 2026-11-13
notes: Done; three choices need maintainer confirmation (see Context)
parent:
depends_on: []
subtasks: []
---
## Description

Two maintainer decisions of 2026-11-13. (1) Identical attachments (stickers, forwarded photos) must be stored once on disk, recognised by checksum, with every conversation linked to the single copy. (2) .m4a is the standard for audio: recordings are always transcoded so they play in a web page, and the original is not kept (as with JPEG for pictures). Looking at (1) showed a defect: staging already kept one file per checksum, but filing moved it for the first message only, so every other message that carried the same file showed 'file not in this archive'.

## Acceptance criteria

- [x] The same content attached to several messages is one file on disk; every message's page shows it
- [x] The copy is filed for the earliest message; it does not move when filing is repeated, when older messages arrive later, or when the export is imported again
- [x] The one copy follows a renamed person and the pages that link it follow
- [x] A converted picture (HEIC to JPEG) is shared the same way
- [x] Mail and chat each keep their own copy of a file both carry
- [x] amr, awb, caf, opus, ogg, oga, wma, wav, aif(f) and flac are filed as .m4a and only the .m4a is kept; mp3 and m4a are untouched; mail attachments are never converted
- [x] Without ffmpeg, or for a damaged recording, the original is filed and counted; importing again with ffmpeg converts it and removes the old file
- [x] A box made earlier, with .amr and .m4a side by side, is left with the .m4a

## Context

Old Chattr deduplicated with a manifest and symlinks inside Attachments/{service}/{year}/. Symlinks do not suit the box: they break on Windows, in zip files and in most sync services, and the box server refuses them. The page link does the same job with nothing special on disk. NEEDS MAINTAINER CONFIRMATION: (1) a file sent to two people sits only in the folder of the person it was first seen with; the other person's pages show it but their folder does not hold it; (2) .3gp/.3g2/.qta are no longer converted, because they can hold video and only the .m4a would be kept; (3) fixed bit rates per format (16k amr, 32k caf/opus, 64k ogg, 128k wav/aiff, 160k flac).

## Subtasks

- [x] One home per content: choose it, file it, link every other message to it
- [x] Keep the home stable across repeats, later imports and renames; clear staged duplicates
- [x] File audio as .m4a only; convert what an earlier run could not; tidy boxes that kept both
- [x] Caixa messages, older tests and documentation

## Implementation plan

Status: done
Current task:

### T01: One home per content: choose it, file it, link every other message to it
### T02: Keep the home stable across repeats, later imports and renames; clear staged duplicates
### T03: File audio as .m4a only; convert what an earlier run could not; tidy boxes that kept both
### T04: Caixa messages, older tests and documentation

## Completion report

- **Outcome:** file_attachments now works in message-time order and gives each (checksum, mail-or-chat) one home row; other rows are pointed at the home's path with processing_info {shared: true}. Every filed row is marked in processing_info, which is what stops a re-import from re-filing it. Audio conversion happens at filing like pictures.
- **Files:** tools/chattr/src/chattr/filing.py, caixa/collectors/chattr.py, tools/chattr/tests/test_filing.py, tests/test_chattr_collectors.py, docs/Documentation/Collector.md
- **Errors:** A first version let a re-import move the copy to another person (the home row lost its place to a linked row); fixed by marking every filed row. Mail and chat sharing one staged file left the second without one; the staged file is now copied when both need it.
- **Verify:** python -m pytest -q: 1193 passed, 6 skipped (Node not on PATH); harness vitest: 257 passed; black and mypy clean. Not run on a real export: the first real import is the check, in particular WhatsApp .opus voice notes and how much space sharing saves.

## Review

Self-review, minors only. Checked: nothing in the source export is written to; a failed transcode leaves no partial file; a linked row never deletes the home's file (path compared before removal); a duplicate inside the box is removed only when it holds the same checksum. Known limit: a file removed from the box as a duplicate is not restored by Undo (only arises in boxes made before this change).

## Notes

- 2026-11-13: done; three choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
