---
id: 20261112-05-hot-fix-voicemail-audio-that-plays-in-a-browser
title: 'Hot fix: voicemail audio that plays in a browser'
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

Imported iPhone voicemail transcribed correctly but would not play on the page: the recordings are AMR, which browsers do not decode. The maintainer asked for a lossless container switch if one exists, otherwise AAC at the same bit and sample rate.

## Acceptance criteria

- [x] A voicemail's page plays in a browser (checked in Chromium: the `.m4a` loads with its duration and no error).
- [x] The original recording is kept, untouched, beside the playable copy and linked from the page.
- [x] Without ffmpeg the import finishes, the originals are filed, and the result says how many recordings have no playable copy and why; a file ffmpeg cannot convert is not blamed on a missing program.
- [x] The copy is made once and moves with its original when a person is renamed.

## Context

There is no lossless route: Chrome and Firefox do not decode AMR in any container (3GP, MP4), so the audio must be re-encoded. The copy is AAC in `.m4a` at the original's own sample rate and channels (8 kHz mono for AMR-NB), at 16 kbit/s rather than AMR's 12.2: AAC degrades at very low rates, and the result is about 30% larger (62 KB against 48 KB for 30 seconds). It is made at filing time by `chattr.filing`, for `.amr`, `.awb`, `.caf`, `.qta`, `.3gp`, `.3g2`. The copy is treated like a page: derived, and made again if missing. The database records only the original.

## Subtasks

- [x] Tests with a real (silent, generated) AMR-NB file: the copy is made, played first, the original linked; no ffmpeg; a file that will not convert.
- [x] `filing._transcode` and `playable_copy`; `Filed.playable_made`, `unplayable`, `ffmpeg_missing`.
- [x] `page.html`: the copy as the first `<source>`, 'Original recording (.amr)', and a note when there is no copy.
- [x] Caixa: a plain warning on the import's result.

## Implementation plan

Status: done
Current task:

### T01: Tests with a real (silent, generated) AMR-NB file: the copy is made, played first, the original linked; no ffmpeg; a file that will not convert.
### T02: `filing._transcode` and `playable_copy`; `Filed.playable_made`, `unplayable`, `ffmpeg_missing`.
### T03: `page.html`: the copy as the first `<source>`, 'Original recording (.amr)', and a note when there is no copy.
### T04: Caixa: a plain warning on the import's result.

## Completion report

- **Outcome:** Voicemail plays on its page; the original AMR is kept beside an AAC copy of about the same size.
- **Files:** tools/chattr/src/chattr/filing.py, templates/page.html, pages.py, caixa/collectors/chattr.py, tests
- **Errors:** none
- **Verify:** Covered by the same runs as ticket 20261112-04. ffmpeg here decodes AMR-NB and encodes AAC; a 3-second generated AMR gives an 8 kHz mono AAC file that Chromium loads and reports as 3 s long.

## Review

Clean, with one limit: no real iPhone voicemail has been converted here (the test audio is generated silence), so the sound quality at 16 kbit/s is for the maintainer to judge. NEEDS MAINTAINER CONFIRMATION of the bit rate (16 kbit/s, not strictly 12.2) and of keeping the original beside the copy.

## Notes

- 2026-11-12: To change the rate, edit `UNPLAYABLE` in tools/chattr/src/chattr/filing.py; delete the `.m4a` files and import again to remake them.
