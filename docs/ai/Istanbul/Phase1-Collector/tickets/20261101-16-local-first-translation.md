---
id: 20261101-16-local-first-translation
title: Local-first translation
type: feature
priority: low
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 16.
parent:
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
current_task: T02
plan_status: in-progress
---
## Description

Optional translation through an OpenAI-compatible endpoint, local by default.

## Acceptance criteria

- [ ] Endpoint configurable; local default; key from environment only
- [ ] Translation-skip heuristic restored from `60b276c`

## Context

Phase1-Collector Tasks Breakdown item 16. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F9; N2.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** translation is a separate, explicit step after conversion (conversion itself never uses
the network, N2): `chattr-cli translate` sends the text of messages that need it to an
OpenAI-compatible chat endpoint and stores the result in `messages.translation`. The endpoint is
local by default (`http://localhost:11434/v1`, the address Ollama and similar servers use); a
non-local address is refused unless the settings say `allow_remote`. The API key, when there is
one, is read from an environment variable named in the settings and never from a file. Calls use
the standard library (`urllib`), so no new dependency. Language is detected by a small built-in
stopword detector (the old `langdetect` dependency never built); the skip heuristic is the one from
`60b276c`: a non-English message is not translated when the same author, within five minutes before
or after, wrote an English message of about the same length (they already translated it
themselves).

### T01: Language detection and the skip heuristic

- `detect_language(text)`: "en", "pt", "es", "fr", "de" or "it" when the evidence is clear, else
  None (too short, mixed, unknown).
- `needs_translation(messages, index)`: false for empty or non-text messages, English text, text with
  no detectable language, and text the author already translated (the heuristic, with its 300
  second window and 20% length tolerance, in both directions, same author only).
- Tests: sample sentences; the heuristic's boundaries (299/301 s, 19%/21%, other author, in between
  messages).
- Verify: `python -m pytest -q tools/chattr/tests/test_translation_rules.py`
- [x] done

### T02: The translation client and its settings

- `OpenAICompatibleTranslator(endpoint, model, ...)`: `POST {endpoint}/chat/completions` with a
  translation prompt; returns text and token usage; errors become `TranslationError`.
- `make_translator(settings)`: from `global.ai_translation` (provider, endpoint, model, target
  language, `api_key_env_var`, timeout, `allow_remote`); disabled or no model gives None; a
  non-local endpoint needs `allow_remote`; any `api_key` stored in the settings is ignored.
- Tests: a local test server (request shape, key header only when the variable is set, usage,
  errors); the local-only rule; the key never read from the settings file.
- Verify: `python -m pytest -q tools/chattr/tests/test_translation_client.py`
- [ ] done

### T03: `chattr-cli translate` and showing translations

- `translate_archive(db, translator, ...)`: for each conversation in time order, translate the
  messages that need it, store `translation` and the detected `language`, count translated,
  skipped (English, already translated by the author), failed, tokens; repeatable and resumable
  (messages with a translation are left alone); one failure doesn't stop the rest.
- `chattr-cli translate [--endpoint URL] [--model NAME] [--service S] [--limit N]`.
- Pages show the translation under the original; defaults updated (`ai_translation`).
- Tests: stub transport over a fixture archive; resumability; failures; the command; page text.
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
T01: translation.py: detect_language (built-in stopword detector for en/pt/es/fr/de/it; None when thin or tied, so short or mixed text is never guessed), needs_translation (text messages only; not English; not what the same author already translated: the nearest message by the same author on either side, within 300 s, English, length within 20% of that message). The old langdetect dependency never built, so detection is built in; accuracy outside these six languages is nil (they are reported as 'unknown' and not translated).
