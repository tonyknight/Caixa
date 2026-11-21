---
id: 20261121-05-apple-intelligence-in-settings
title: Apple Intelligence in Settings
type: feature
priority: medium
status: in-progress
created: 2026-11-21
updated: 2026-11-21
closed:
notes: ''
parent:
depends_on:
- 20261121-03-switches-for-each-import
- 20261121-04-the-apple-intelligence-helper-and-provider
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

Choose Apple Intelligence or an endpoint for summaries and for translation, in Settings, with a Test for both.

## Acceptance criteria

- [ ] Settings → Summaries and → Translation each choose Apple Intelligence (on this Mac) or An endpoint; the Apple choice is offered only when the helper says ready, with the reason otherwise
- [ ] Test works for both choices; summaries and translations during imports use the chosen one, several helpers at once
- [ ] A conversation sent to Apple Intelligence is held to 6,000 characters (first and last mails); a declined one keeps its opening words and is counted in the result

## Context

Phase 1.5 - Mbox hot fixes (approved 2026-11-21). See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`: *Hot fixes from the first real mbox*; M19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: settings summaries.provider and translation.provider (endpoint | apple, with x-labels). With apple: no endpoint checks, model name 'Apple Intelligence', client/translator = AppleIntelligence(Workers) after check() (builds the helper), closed after each run/test; summaries held to APPLE_BUDGET (6,000); Declined conversations counted ('declined') and skipped, with a warning; the run goes on. apple_intelligence.check(build=False) reports not_built without building; apple.check method; settings.get marks the Apple choice x-unavailable with the reason unless only not built. RED: 6 tests, then GREEN (84 in the four files).
