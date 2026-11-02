---
id: 20261101-12-iphone-voicemail-and-local-speech-to-text
title: iPhone Voicemail and local speech-to-text
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 12.
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
current_task: T01
---
## Description

Parse iPhone voicemail and transcribe it locally.

## Acceptance criteria

- [ ] A transcription interface with a local model backend and a test stub
- [ ] Transcript stored with the entry; audio kept as an attachment
- [ ] No network access during transcription

## Context

Phase1-Collector Tasks Breakdown item 12. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F5; N2; Open questions (speech-to-text model).

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T01

**Design:** a `Transcriber` interface (`transcribe(audio) -> Transcript`) with a deterministic
test stub and two local backends: `WhisperCppTranscriber` (runs a local `whisper-cli` after an
ffmpeg conversion to 16 kHz mono WAV) and `FasterWhisperTranscriber` (the optional
`faster-whisper` package, loading a local model folder). Neither ever downloads a model: the model
must already be a local path. Transcription runs inside `offline_only()`, which makes any network
connection from this process raise. **Open question "which local runtime and model"**: both
backends are provided and none is the silent default; the choice is a setting
(`services.voicemail.preferences.transcription`). No model is installed in this environment, so the
real backends are tested against a fake `whisper-cli` and a fake module, and that gap is stated in
the completion report.

### T01: Transcription interface, backends and the offline guard

- `Transcript(text, language, model)`, `Transcriber` protocol, `StubTranscriber`.
- `offline_only()` blocks `socket` connections (and sets the Hugging Face offline variables) for
  its duration, restoring everything afterwards, even on error.
- `WhisperCppTranscriber`: ffmpeg → 16 kHz mono WAV in a temporary folder → `whisper-cli -m MODEL
  -f WAV -nt -np [-l LANG]` → text from stdout; clear errors for a missing executable, model,
  ffmpeg, or a failing run.
- `FasterWhisperTranscriber`: lazy import; a clear error when the package or local model folder
  is missing.
- `make_transcriber(settings)` from the Voicemail preferences; disabled or unconfigured gives None.
- Tests: stub; guard blocks sockets and restores them; the whisper.cpp wiring against a fake
  executable and real ffmpeg; faster-whisper against a fake module; error cases; factory.
- Verify: `python -m pytest -q tools/chattr/tests/test_transcription.py`
- [ ] done

### T02: iPhone voicemail parser

- `VoicemailParser(BaseParser)` reads a folder holding `voicemail.db` (and its `<ROWID>.*` audio):
  sender (callback number), Unix-seconds date (UTC), duration, trashed flag.
- Records: `voicemail` entries; the audio kept by hash as the attachment whatever its extension;
  the transcript from the transcriber (a failure leaves no transcript and records the error;
  the import continues).
- One conversation per caller.
- Tests: the fixture (2 voicemails); stub transcripts; audio stored once; a failing backend.
- Verify: `python -m pytest -q tools/chattr/tests/test_voicemail_parser.py`
- [ ] done

### T03: Import and `chattr-cli convert voicemail`

- `convert voicemail <folder> [--transcribe] [--model PATH] [--language CODE]`; settings supply
  provider, model path, language; central route, `--json`, `--html`, `--attachments-dir`,
  `--owner`, `--aliases`; menu entry.
- Tests: import with a stub (transcript on the entry, audio attached), re-import idempotent, the
  CLI with a fake `whisper-cli`, no network at any point.
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
OPEN QUESTION (speech-to-text runtime/model) answered conservatively, NEEDS MAINTAINER CONFIRMATION: two local backends (whisper.cpp CLI, faster-whisper) behind one interface, selected by setting; no default model, no downloads. No STT model/runtime is installed in the build container, so real transcription is untested here.
