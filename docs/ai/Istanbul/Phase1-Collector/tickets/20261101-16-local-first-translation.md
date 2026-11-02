---
id: 20261101-16-local-first-translation
title: Local-first translation
type: feature
priority: low
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: local-first translation step with the skip heuristic.'
parent:
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
subtasks: []
plan_status: done
---
## Description

Optional translation through an OpenAI-compatible endpoint, local by default.

## Acceptance criteria

- [x] Endpoint configurable; local default; key from environment only
- [x] Translation-skip heuristic restored from `60b276c`

## Context

Phase1-Collector Tasks Breakdown item 16. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: F9; N2.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

### T03: `chattr-cli translate` and showing translations

- `translate_archive(db, translator, ...)`: for each conversation in time order, translate the
  messages that need it, store `translation` and the detected `language`, count translated,
  skipped (English, already translated by the author), failed, tokens; repeatable and resumable
  (messages with a translation are left alone); one failure doesn't stop the rest.
- `chattr-cli translate [--endpoint URL] [--model NAME] [--service S] [--limit N]`.
- Pages show the translation under the original; defaults updated (`ai_translation`).
- Tests: stub transport over a fixture archive; resumability; failures; the command; page text.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `chattr-cli translate [--endpoint URL] [--model NAME] [--service S] [--limit N]`
  translates the non-English text messages of the archive through an OpenAI-compatible chat endpoint
  (default `http://localhost:11434/v1`), in place (`messages.translation` and `.language`), resumably.
  A non-local endpoint is refused unless `global.ai_translation.allow_remote` is set; the API key is
  read only from the environment variable named in the settings. The first version's skip rule is
  restored: text the same author already translated within five minutes (English, about the same
  length) is left alone. Pages show the translation under the original. Conversion itself still
  never touches the network (a test cuts the network and converts and renders every service).
- **Files:**
  - New: `translation.py` (detection, rules, client, settings, `translate_archive`).
  - Changed: `commands.py` (`translate`), `cli.py` (`translate` command), `pages.py` and the page
    template (translation under the text), `defaults/config.json` (`ai_translation`).
  - Tests: `test_translation_rules`, `test_translation_client` (with a local stub server in
    `stub_server.py`), `test_translate_archive`, `test_no_network`.
- **Errors:** none in existing code. The old defaults pointed at OpenRouter with a placeholder key
  environment variable; they are replaced by the local-first defaults. The `langdetect` dependency
  the first version used never built here, so language detection is built in.
- **Verify:** `python -m pytest -q` → 616 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean. Not verified against a real model server: the client
  is tested against a stub that speaks the OpenAI chat-completions shape.

## Review

### 2026-11-02: ae929a2..HEAD (T01–T03), reviewed in-session

**Verdict:** clean; Minor items only; one decision for the maintainer.

- **Minor (decision):** the default endpoint `http://localhost:11434/v1` (Ollama's OpenAI-compatible
  address) and that no model is preset: confirm, or name a preferred local runtime.
- **Minor:** the built-in detector knows six languages (English, Portuguese, Spanish, French, German,
  Italian) and returns "unknown" otherwise, so text in other languages is never translated. A real
  language-identification model could replace it behind the same function.
- **Minor:** the heuristic compares an English neighbour's *length* only; it does not check that the
  neighbour actually says the same thing (the first version didn't either).
- **Minor:** the system prompt always asks for the configured target language; the source language is
  not named (the first version said "from Brazilian Portuguese").
- **Minor:** `translate` sends one request per message, sequentially. Fine for a family archive on a
  local model; batching and concurrency are possible later.
- **Minor:** local servers are reached without any proxy; a remote endpoint (when allowed) uses the
  environment's proxy settings.
- **Minor:** translations are not part of the message's content hash, so a changed translation
  doesn't bump the message `version`.
- **Spec:** both acceptance criteria are met. Files match the plan.
- **TDD:** RED then GREEN for every task (collection errors, then passing).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: translation.py: detect_language (built-in stopword detector for en/pt/es/fr/de/it; None when thin or tied, so short or mixed text is never guessed), needs_translation (text messages only; not English; not what the same author already translated: the nearest message by the same author on either side, within 300 s, English, length within 20% of that message). The old langdetect dependency never built, so detection is built in; accuracy outside these six languages is nil (they are reported as 'unknown' and not translated).

### 2026-11-02
T02: OpenAICompatibleTranslator over stdlib urllib (no 'requests' dependency); local endpoints bypass any configured internet proxy; error cases become TranslationError. make_translator: endpoint must be loopback unless global.ai_translation.allow_remote; key only from the env var named by api_key_env_var (an api_key in the file is ignored with a note). Defaults changed: ai_translation is now {enabled false, endpoint http://localhost:11434/v1, model '', target_language English, api_key_env_var CHATTR_TRANSLATION_API_KEY, allow_remote false, timeout_seconds 60} (the old OpenRouter defaults are gone for new roots; existing roots keep their old keys and gain the new ones). The default endpoint is Ollama's OpenAI-compatible address: a choice to confirm.

### 2026-11-02
T03: translate_archive(db, translator, service, limit): per conversation in time order; sets messages.language for every detected text message and messages.translation for translated ones; resumable (existing translations skipped); one failure doesn't stop the rest but 5 consecutive failures abort the run; stats separate English / author-translated / unknown / failed. chattr-cli translate (a --model turns it on). Pages show the translation (escaped) under the text. Added test_no_network (N2: every service converts and renders with sockets cut).
