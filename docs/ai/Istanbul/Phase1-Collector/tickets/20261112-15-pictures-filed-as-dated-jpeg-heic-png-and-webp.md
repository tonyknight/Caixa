---
id: 20261112-15-pictures-filed-as-dated-jpeg-heic-png-and-webp
title: Pictures filed as dated JPEG (HEIC, PNG and WebP converted)
type: feature
priority: medium
status: done
created: 2026-11-12
updated: 2026-11-12
closed: 2026-11-12
notes: Done; four choices need maintainer confirmation (see Context)
parent:
depends_on: []
subtasks: []
---

## Description

Chattr used to file picture attachments as JPEG at quality 85 (HEIC included), named by the date of their message, with DateTimeOriginal set. The code survived in attachment_manager.py but was switched off in Caixa, and the newer staging-then-filing path (iMessage most of all) never went through it. This ticket puts the behaviour back, once, at filing time, for every chat source.

## Acceptance criteria

- [x] HEIC/HEIF, PNG and WebP attachments of chat messages are filed as .jpg at quality 85; only the JPEG is kept in the box and the source is untouched
- [x] A filed picture carries DateTimeOriginal: its own when it has one, else the local time of its message
- [x] A JPEG with no date is dated without being recompressed; a JPEG that has its date, GIF and video are byte-identical
- [x] Mail attachments are never converted
- [x] Importing the same export again files nothing twice and leaves nothing in staging
- [x] A picture that cannot be read is kept in its original format and the import says how many
- [x] The page shows the converted picture

## Context

Maintainer request of 2026-11-12. Hot fix on the existing board. NEEDS MAINTAINER CONFIRMATION: (1) the original HEIC/PNG is not kept beside the JPEG (old Chattr behaviour; differs from audio, where the original is kept); (2) PNG and WebP are converted as before, which flattens see-through stickers onto white; (3) there is no setting to turn this off in Caixa (Chattr's publish takes convert_images=False); (4) pictures already filed in an existing box are not converted: rebuild the box.

## Subtasks

- [x] Convert HEIC, PNG and WebP to JPEG at filing, with the date taken and colour profile
- [x] Date JPEGs that carry no date, without recompressing
- [x] Re-imports: keep the filed picture, clear the staged duplicate
- [x] Report unconverted pictures in Caixa; document

## Implementation plan

Status: done
Current task:

### T01: Convert HEIC, PNG and WebP to JPEG at filing, with the date taken and colour profile
### T02: Date JPEGs that carry no date, without recompressing
### T03: Re-imports: keep the filed picture, clear the staged duplicate
### T04: Report unconverted pictures in Caixa; document

## Completion report

- **Outcome:** Done at filing time in chattr/filing.py with Pillow and pillow-heif (already dependencies). DateTimeOriginal is written by Pillow, so exiftool is no longer needed except for a JPEG that has EXIF but no date. What was done is recorded in attachments.processing_info, which also stops a re-import from filing the staged original again.
- **Files:** tools/chattr/src/chattr/{filing,commands,database_manager}.py, caixa/collectors/chattr.py, tools/chattr/tests/test_filing.py, tests/test_chattr_collectors.py, tools/chattr/tests/test_imessage_attachments.py, docs/Documentation/Collector.md
- **Errors:** Three older tests expected the fixture PNGs to stay PNG; updated to the new behaviour.
- **Verify:** python -m pytest -q: 1182 passed, 6 skipped (Node not on PATH); black and mypy clean. Not run against real iPhone HEIC files: the tests use pictures made by pillow-heif. exiftool is not installed here, so the EXIF-but-no-date JPEG path is untested.

## Review

Self-review, minors only. Found and fixed in review: an animated WebP or PNG would have been flattened to its first frame; moving pictures are now left as they are (test added). Checked: a failed conversion leaves no half-written file; the source export is never written to (only the staged copy is replaced); re-import and a deleted filed copy are both covered by tests.

## Notes

- 2026-11-12: done at filing time for all chat sources; four choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
