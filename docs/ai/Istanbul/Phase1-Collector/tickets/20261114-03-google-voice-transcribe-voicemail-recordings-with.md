---
id: 20261114-03-google-voice-transcribe-voicemail-recordings-with
title: 'Google Voice: transcribe voicemail recordings with the local speech model'
type: feature
priority: medium
status: done
created: 2026-11-14
updated: 2026-11-14
closed: 2026-11-14
notes: Done; two choices need maintainer confirmation
parent:
depends_on: []
subtasks: []
---
## Description

The maintainer imported a Google Voice archive with a speech model saved in Settings and found the voicemails were not transcribed. Only the iPhone voicemail importer had speech-to-text; the Google Voice importer had no Transcribe option, so the model was never used and the job was quick.

## Acceptance criteria

- [x] Google Voice has the same three speech options as iPhone voicemail (transcribe, model, language), following the same Settings
- [x] With transcribe ticked, every voicemail recording (with or without a page) goes through the model, with the Transcribing stage and timing lines
- [x] The model's text is the transcript; Google's own is kept as google_transcript and stays the transcript when the model fails or hears nothing
- [x] Importing the same export again with transcribe ticked adds transcripts to voicemail already in the box

## Context

NEEDS MAINTAINER CONFIRMATION: (1) the local model's text replaces Google's on the page (Google's is kept in the data, not shown); (2) as with iPhone voicemail, transcription must be ticked for each import: a model saved in Settings never turns it on by itself. That rule is what made this look like a fault; it can be changed to 'on whenever a model is saved' if preferred.

## Subtasks

- [x] GoogleVoiceParser takes a transcriber
- [x] Caixa: shared speech options and engine for both sources; documentation

## Implementation plan

Status: done
Current task:

### T01: GoogleVoiceParser takes a transcriber
### T02: Caixa: shared speech options and engine for both sources; documentation

## Completion report

- **Outcome:** Done. The speech options and the engine set-up are now shared by the two sources.
- **Files:** tools/chattr/src/chattr/parsers/google_voice_parser.py, tools/chattr/src/chattr/commands.py, caixa/collectors/chattr.py, tools/chattr/tests/test_google_voice_parser.py, tests/test_transcription_progress.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1263 passed, 6 skipped; harness vitest: 268 passed; black and mypy clean. Not run with a real speech model or a real Takeout.

## Review

Self-review, clean. Checked: without the option nothing changes (Google's transcript as before); a preview never runs the model.

## Notes

- 2026-11-14: done; two choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
