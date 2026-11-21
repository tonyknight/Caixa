---
id: 20261121-05-apple-intelligence-in-settings
title: Apple Intelligence in Settings
type: feature
priority: medium
status: done
created: 2026-11-21
updated: 2026-11-21
closed: 2026-11-21
notes: 'Done: Apple Intelligence or an endpoint for summaries and translation, chosen
  in Settings.'
parent:
depends_on:
- 20261121-03-switches-for-each-import
- 20261121-04-the-apple-intelligence-helper-and-provider
subtasks: []
plan_status: done
---
## Description

Choose Apple Intelligence or an endpoint for summaries and for translation, in Settings, with a Test for both.

## Acceptance criteria

- [x] Settings → Summaries and → Translation each choose Apple Intelligence (on this Mac) or An endpoint; the Apple choice is offered only when the helper says ready, with the reason otherwise
- [x] Test works for both choices; summaries and translations during imports use the chosen one, several helpers at once
- [x] A conversation sent to Apple Intelligence is held to 6,000 characters (first and last mails); a declined one keeps its opening words and is counted in the result

## Context

Phase 1.5 - Mbox hot fixes (approved 2026-11-21). See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`: *Hot fixes from the first real mbox*; M19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `summaries.provider` and `translation.provider` (`endpoint` | `apple`, default
`endpoint`) choose who writes. With `apple`, no endpoint or model is needed or checked, the model's
name is "Apple Intelligence", the client is `AppleIntelligence` with the Workers setting's number
of helpers (closed after the run), and a conversation is held to 6,000 characters. A conversation
the model declines keeps its opening words and is counted (`declined`), and the run carries on.
`apple.check` tells the window whether the Mac's model is ready; `settings.get` marks the Apple
choice unavailable (with the reason) when it cannot be used, except when the helper is only not
built yet (choosing it and pressing Test builds it). The form learns two generic schema marks:
`x-labels` (words for a choice) and `x-unavailable` (choices that cannot be picked, and why).

### T01: Apple Intelligence behind the settings

- `caixa/settings.py`, `caixa/summaries.py`, `caixa/translation.py`, `caixa/collectors/chattr.py`
  (closing the translator), `caixa/apple_intelligence.py` (`check(build=False)`),
  `caixa/service.py` (`apple.check`, `settings.get`), `tests/stand_in_apple.py` (declining on a
  word).
- Tests: with the stand-in, an import's summaries come from Apple Intelligence (model name stored,
  prompts within 6,000 characters), a declined conversation is counted and the rest written;
  translation through Apple during an import; settings accept `apple` without an endpoint; Test
  works for both; `settings.get` marks the choice unavailable when the Mac's model is not.
- Verify: `python -m pytest -q tests/test_summaries.py tests/test_translation.py tests/test_apple_intelligence.py tests/test_worker_protocol.py`
- [x] done

### T02: The choice in the Settings page

- `web/src/client/options-form.ts`, `components/OptionsForm.tsx` (labels, unavailable choices),
  `pages/SettingsPage.tsx` (Test sends the provider; the Apple status line), `mail/SortMail.tsx`
  (a switch is ready with Apple chosen), the built window.
- Tests (`web/tests/settings-page.test.tsx`): the choice shows its words; Apple is disabled with
  its reason when not available; Test sends the provider.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** Settings → Summaries and → Translation each choose who writes: an endpoint, or Apple Intelligence (on this Mac), which needs no address or model and runs as many helpers as Workers. The Apple choice is disabled with its reason when the Mac cannot run it (not when the helper is only unbuilt: Test builds it). Test works for both. Summaries through Apple are held to 6,000 characters; a conversation its safety filter declines keeps its opening words, is counted, and the rest carry on. Sort mail's switches count Apple Intelligence as set up.
- **Files:** `caixa/{settings,summaries,translation,apple_intelligence,service}.py`, `caixa/collectors/chattr.py`, `web/src/client/{api.ts,options-form.ts}`, `web/src/client/components/OptionsForm.tsx`, `web/src/client/pages/SettingsPage.tsx`, `web/src/client/mail/SortMail.tsx`, `caixa/data/web/*`; tests `tests/{test_summaries,test_translation,test_worker_protocol}.py`, `tests/stand_in_apple.py`, `web/tests/{settings-page,sort-mail}.test.tsx`, `web/tests/fake-api.ts`.
- **Errors:** none beyond expected test updates (Test now sends the provider).
- **Verify:** `python -m pytest -q` 1457 passed, 1 skipped; black and mypy clean; web `tsc` clean, vitest 264 passed.

## Review

2026-11-21, in-session. **Verdict: clean (minors only).**

- Minor: Apple Intelligence is exercised here only through the stand-in; the real model's speed, quality and refusals are for the maintainer's Mac (testing guide).
- Minor: `settings.get` runs the helper's `--check` each time Settings opens on a Mac (quick once built).

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: settings summaries.provider and translation.provider (endpoint | apple, with x-labels). With apple: no endpoint checks, model name 'Apple Intelligence', client/translator = AppleIntelligence(Workers) after check() (builds the helper), closed after each run/test; summaries held to APPLE_BUDGET (6,000); Declined conversations counted ('declined') and skipped, with a warning; the run goes on. apple_intelligence.check(build=False) reports not_built without building; apple.check method; settings.get marks the Apple choice x-unavailable with the reason unless only not built. RED: 6 tests, then GREEN (84 in the four files).

### 2026-11-21
T02: the options form reads x-labels (words for a choice) and x-unavailable (disabled choices, the reason shown under the field); Settings' Test for summaries and translation sends the provider (and Workers when typed); Sort mail counts Apple Intelligence as set up for its switches. RED: 2 Settings tests and 1 Sort mail test, then GREEN; older Test expectations updated for the provider. Full verify: pytest 1457 passed, vitest 264 passed.
