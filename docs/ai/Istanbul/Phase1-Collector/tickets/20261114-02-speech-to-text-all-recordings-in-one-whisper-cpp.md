---
id: 20261114-02-speech-to-text-all-recordings-in-one-whisper-cpp
title: 'Speech-to-text: all recordings in one whisper.cpp run'
type: feature
priority: medium
status: done
created: 2026-11-14
updated: 2026-11-14
closed: 2026-11-14
notes: Done; not run against a real whisper-cli
parent:
depends_on: []
subtasks: []
---
## Description

whisper.cpp was started once per recording, so the model was loaded every time. For a large model (large-v3-turbo) and short voicemails, loading is most of the time. The maintainer asked (2026-11-14) to batch the recordings into one run.

## Acceptance criteria

- [x] All recordings of an import go to one run of whisper-cli (the model is loaded once); a long list is split into runs of 100
- [x] Each result is reported as soon as the program has written it, so the progress bar, job log and terminal still move per recording
- [x] A recording whisper fails on, or a run that dies part way, does not cost the others: what the run left is tried again one at a time, with its own error
- [x] Audio that cannot be read is reported and the rest go on
- [x] Engines that cannot take many (faster-whisper) work as before

## Context

From whisper.cpp's cli.cpp (master): inputs are every -f and positional argument; the model is loaded before the loop over inputs; -otxt writes a text file per input, named by the matching -of (by position) or else '<input>.txt'; a file it cannot read is skipped and the exit code is 11. The single-recording path (text on standard output) is kept for the fallback. NEEDS MAINTAINER CONFIRMATION: runs of 100 recordings; the time limit for a run is 15 minutes per recording in it.

## Subtasks

- [x] WhisperCppTranscriber.transcribe_many: one run, results as they are written, fallback
- [x] transcribe_all uses it; TimedTranscriber times each result; documentation

## Implementation plan

Status: done
Current task:

### T01: WhisperCppTranscriber.transcribe_many: one run, results as they are written, fallback
### T02: transcribe_all uses it; TimedTranscriber times each result; documentation

## Completion report

- **Outcome:** Done. transcribe_all asks the engine for transcribe_many when it has one. Results are found by watching for each recording's text file while the program runs.
- **Files:** tools/chattr/src/chattr/transcription.py, caixa/collectors/chattr.py, tools/chattr/tests/test_transcription.py, tests/test_transcription_progress.py, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q passes; black and mypy clean. NOT verified with the real whisper-cli: it is not installed here. The tests use a stand-in program that takes the same arguments; the argument handling was read from whisper.cpp's source, and a version that ignores -of is allowed for. The maintainer's first voicemail import with transcription on is the real check; the per-recording times in the terminal will show whether the model is loaded once.

## Review

Self-review, minors only. Checked: the program's output goes to a file, not a pipe, so a long run cannot block; the process is killed if the import is cancelled or the time limit passes; temporary WAV and text files are removed with the run's folder.

## Notes

- 2026-11-14: done; not run against a real whisper-cli.
