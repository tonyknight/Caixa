---
id: 20261113-02-translation-through-an-openai-compatible-endpoint
title: Translation through an OpenAI-compatible endpoint, with key and test
type: feature
priority: medium
status: done
created: 2026-11-13
updated: 2026-11-13
closed: 2026-11-13
notes: Done; six choices need maintainer confirmation; no real endpoint contacted
parent:
depends_on: []
subtasks: []
---
## Description

Maintainer request of 2026-11-13. Caixa's Settings had translation fields that nothing used. Translation must work again with the earlier Chattr method: the user connects an OpenAI-compatible endpoint in Settings, either paid inference (OpenRouter, DeepSeek) or a locally hosted model; messages are translated when they meet the earlier criteria; a Test button validates the endpoint; and the model is held to delivering a translation only.

## Acceptance criteria

- [x] With translation on, an import translates the messages that meet Chattr's criteria (text, clearly not English, not already translated by their author within five minutes at about the same length, not translated before) and the page shows the translation under the original
- [x] The endpoint can be local or a paid service; a service on the internet is refused until 'Allow a service on the internet' is ticked
- [x] An API key can be entered in Settings; it is stored outside the box, readable only by its owner, never returned to the interface, never written to a box file, and never sent to a host other than the one it was saved for
- [x] A Test button sends one fixed sentence using what is typed (saved or not) and shows the answer, or says why it failed (unreachable, key refused, unknown model, no credit) with the server's own message
- [x] The instruction restores the first version's wording (direct translation only; return only the translated text) and adds that the message is never an instruction; a reply far longer than the message is rejected; a reasoning model's thinking is removed
- [x] A failing translation service never fails an import; what was translated is kept and the import says what happened
- [x] Progress shows a Translating stage with a count, and it can be cancelled

## Context

The first version (main.py, d7ee0de) called OpenRouter with the system prompt 'You are an expert translator… Direct translation only. Return only the translated text and nothing else.' and translated any message langdetect did not call English. The later version added the skip rule for messages the author translated themselves. Both rules were already in chattr/translation.py; what was missing was the Caixa wiring, the key, remote endpoints and the test. NEEDS MAINTAINER CONFIRMATION: (1) the key file is <Caixa home>/keys.json (mode 0600), not the macOS Keychain; (2) the setting is named 'Allow a service on the internet'; (3) translation runs inside every import and covers the whole box, there is no separate 'Translate now' button; (4) four requests at a time to a paid service, one to a local model; (5) the target language is English only, as before; (6) language detection is Chattr's built-in detector (Portuguese, Spanish, French, German, Italian), not langdetect, so other languages are not translated.

## Subtasks

- [x] Chattr: translate-only instruction, reply checks, plain-word errors, retry when busy, several requests at once, progress
- [x] Caixa: settings (remote opt-in, validation), key store, translation.key and translation.test
- [x] Caixa: a Translating step in every import; result and warnings
- [x] Interface: key field, Test button, Translating stage, translated count; documentation

## Implementation plan

Status: done
Current task:

### T01: Chattr: translate-only instruction, reply checks, plain-word errors, retry when busy, several requests at once, progress
### T02: Caixa: settings (remote opt-in, validation), key store, translation.key and translation.test
### T03: Caixa: a Translating step in every import; result and warnings
### T04: Interface: key field, Test button, Translating stage, translated count; documentation

## Completion report

- **Outcome:** Translation works from Settings to page. Chattr's translator gained the guardrails and concurrency; Caixa adds caixa/translation.py (key store, checks, test), two service methods and a step in the import run between matching people and filing.
- **Files:** tools/chattr/src/chattr/translation.py, caixa/translation.py, caixa/settings.py, caixa/service.py, caixa/collectors/{base,chattr}.py, harness/src/client/{api,locales}.ts, harness/src/client/pages/{SettingsPage,ImportPage}.tsx, harness/src/client/components/Progress.tsx, tests/test_translation.py, tools/chattr/tests/test_translation_client.py, tools/chattr/tests/test_translate_archive.py, harness/tests/{settings-page,progress}.test.tsx, harness/tests/e2e-translation.test.ts, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1220 passed, 6 skipped (Node not on PATH); harness vitest: 264 passed, including a browser test of Settings against the real worker and a stand-in endpoint; tsc, black and mypy clean. NOT verified: any real endpoint. No request was made to OpenRouter, DeepSeek, Ollama or LM Studio; every test uses a stand-in server that speaks the same format.

## Review

Self-review, minors only. Checked: the key is absent from settings.get, from every file in the box and from error text; a key is refused for a non-local http endpoint; Test saves nothing; the diagnostics report prints neither endpoint nor key. Known limits: the master database does not yet carry translations (the pages and Chattr's database do); a prompt cannot make a model obey, so the reply length check is the backstop.

## Notes

- 2026-11-13: done; six choices recorded under Context as NEEDS MAINTAINER CONFIRMATION. No real endpoint was contacted.
