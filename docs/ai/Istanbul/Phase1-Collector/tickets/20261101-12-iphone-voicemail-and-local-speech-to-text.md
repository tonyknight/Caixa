---
id: 20261101-12-iphone-voicemail-and-local-speech-to-text
title: iPhone Voicemail and local speech-to-text
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: iPhone voicemail, local transcription interface (real model untested
  here).'
parent:
depends_on:
- 20261101-02-synthetic-fixture-family
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
plan_status: done
---
## Description

Parse iPhone voicemail and transcribe it locally.

## Acceptance criteria

- [x] A transcription interface with a local model backend and a test stub
- [x] Transcript stored with the entry; audio kept as an attachment
- [x] No network access during transcription

## Context

Phase1-Collector Tasks Breakdown item 12. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F5; N2; Open questions (speech-to-text model).

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

### T02: iPhone voicemail parser

- `VoicemailParser(BaseParser)` reads a folder holding `voicemail.db` (and its `<ROWID>.*` audio):
  sender (callback number), Unix-seconds date (UTC), duration, trashed flag.
- Records: `voicemail` entries; the audio kept by hash as the attachment whatever its extension;
  the transcript from the transcriber (a failure leaves no transcript and records the error;
  the import continues).
- One conversation per caller.
- Tests: the fixture (2 voicemails); stub transcripts; audio stored once; a failing backend.
- Verify: `python -m pytest -q tools/chattr/tests/test_voicemail_parser.py`
- [x] done

### T03: Import and `chattr-cli convert voicemail`

- `convert voicemail <folder> [--transcribe] [--model PATH] [--language CODE]`; settings supply
  provider, model path, language; central route, `--json`, `--html`, `--attachments-dir`,
  `--owner`, `--aliases`; menu entry.
- Tests: import with a stub (transcript on the entry, audio attached), re-import idempotent, the
  CLI with a fake `whisper-cli`, no network at any point.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `chattr-cli convert voicemail <backup folder> [--transcribe] [--model PATH]
  [--language CODE]` imports an iPhone `voicemail.db` and its audio into the central archive: one
  `voicemail` message per row with the caller, UTC time, duration, the audio kept by hash, and a
  transcript made locally when asked. `chattr.transcription` provides the interface, a test stub,
  two local backends (whisper.cpp CLI, faster-whisper) and an offline guard that makes any network
  connection raise while transcribing. The schema's legacy view now shows a transcript as a
  voicemail's text (migration 2), so pages and exports show what was said.
- **Files:**
  - New: `transcription.py`, `parsers/voicemail_parser.py`.
  - Changed: `schema.py` (migration 2), `commands.py`, `cli.py` (flags, menu choice 7),
    `defaults/Services/Voicemail.json` (transcription settings), `pyproject.toml` (mypy override).
  - Tests: `test_transcription`, `test_voicemail_parser`, `test_voicemail_import`, `test_schema`.
- **Errors:** none in existing code. **What was not verified:** no speech-to-text model or runtime
  is installed in the build container, so neither real backend has transcribed real audio. The
  whisper.cpp path is tested end to end with a fake `whisper-cli` and real ffmpeg; the
  faster-whisper path against a fake module. A first run with a real model is needed.
- **Verify:** `python -m pytest -q` → 399 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean.

## Review

### 2026-11-02: ef4b18c..HEAD (T01–T03), reviewed in-session

**Verdict:** clean; Minor items only. One is a decision for the maintainer.

- **Minor (decision):** the open question "which local runtime and model" is answered by offering
  two backends behind one setting, with no default model and no downloads. The maintainer should
  choose a recommended default (and may want a model-fetch helper outside Chattr).
- **Minor:** the offline guard covers this Python process only. A program started by a backend
  (`whisper-cli`) is outside it; whisper.cpp does not use the network, but the guard can't prove
  that.
- **Minor:** every re-import re-transcribes each voicemail (transcripts are not cached by audio
  hash). Fine for a few hundred; a cache keyed by hash and model would help a large archive.
- **Minor:** a voicemail's transcript is a machine guess and is stored as `transcript` with
  `transcript_model` in `service_specific`; later layers (the personal model, Caixa) should treat it
  as lower-confidence text and cite the audio.
- **Minor:** the phone's time zone isn't in `voicemail.db`, so the stored instant is exact but the
  local offset is unknown (stored as UTC).
- **Minor:** `voicemail.db` layouts differ between iOS versions (column names, audio container, some
  versions keep audio as `.amr` and others `.m4a`); only the fixture's layout is tested. Verify on
  a real backup.
- **Minor:** Google Voice voicemails also carry audio; they use Google's transcript and are not
  re-transcribed.
- **Spec:** all three acceptance criteria are met. Files match the plan; migration 2 was added to
  make the transcript visible in pages and exports.
- **TDD:** RED then GREEN for every task (collection errors, then passing; T03 first run showed
  4+ failing, then one fixture mistake in the test fixed).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
OPEN QUESTION (speech-to-text runtime/model) answered conservatively, NEEDS MAINTAINER CONFIRMATION: two local backends (whisper.cpp CLI, faster-whisper) behind one interface, selected by setting; no default model, no downloads. No STT model/runtime is installed in the build container, so real transcription is untested here.

### 2026-11-02
T01: transcription.py: Transcriber interface, StubTranscriber, WhisperCppTranscriber (ffmpeg → 16 kHz mono wav → local whisper-cli) and FasterWhisperTranscriber (local model folder, local_files_only), make_transcriber(settings). offline_only() raises NetworkBlocked on any non-loopback connect/connect_ex/getaddrinfo and sets HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE, restoring all on exit. LIMITATION: a child process (whisper-cli) is outside the guard; whisper.cpp does not use the network. Voicemail defaults changed: transcription now {enabled false, provider 'whisper.cpp', model_path '', executable 'whisper-cli', language ''} ('whisper' still accepted as the old provider name; the unusable 'model: base' name key is gone for new roots; existing roots keep theirs). Real models are not installed here: the backends are tested against a fake whisper-cli (real ffmpeg) and a fake faster_whisper module.

### 2026-11-02
T02: VoicemailParser reads voicemail.db read-only (chatdb.connect_readonly) and finds each row's audio by <ROWID>.* (extension not trusted); audio kept by hash as the attachment; transcripts from the supplied Transcriber via transcribe_all (offline guard on), failures recorded as service_specific.transcription_error; trashed voicemails kept and flagged; callers without a number are filed under 'unknown'. Message ids are hashes (no stable source id: ROWIDs can collide across backups), so a re-transcription with a different model shows as an update, not a duplicate.

### 2026-11-02
T03: convert voicemail wired (folder input; --transcribe/--model/--language, settings supply provider/executable/model_path; the menu uses the settings and never prompts for a model). Schema migration 2 recreates messages_view with COALESCE(body, transcript) so voicemail text shows in HTML and JSON. A re-import with a transcriber updates the same messages (version 2) instead of duplicating them. The state file uses total_messages_imported (the older total_voicemails_imported key is unused).
