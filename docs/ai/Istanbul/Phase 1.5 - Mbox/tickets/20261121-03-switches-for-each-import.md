---
id: 20261121-03-switches-for-each-import
title: Switches for each import
type: feature
priority: medium
status: done
created: 2026-11-21
updated: 2026-11-21
closed: 2026-11-21
notes: 'Done: Translate/Summarize per import; the reason when no summaries were written.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

Translate and Summarize switches for each import, preset from Settings, and an import result that says why no summaries were written.

## Acceptance criteria

- [x] The import wizard has a Translate switch; Sort mail's Import dialog has Translate and Summarize; each starts as Settings says
- [x] Job options `translate` and `summarize` are honoured: off, that job translates or summarizes nothing
- [x] A mail import's result says why no summaries were written (off in Settings, off for this job, not set up, the endpoint failed), shown in the window and on the Jobs page

## Context

Phase 1.5 - Mbox hot fixes (approved 2026-11-21). See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`: *Hot fixes from the first real mbox*; M18.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `translate` becomes an option every Chattr collector has (`_COMMON_OPTIONS`, a boolean
following the `translation.enabled` setting through `x-setting`), so the import wizard draws it
from the schema like any option and starts it from Settings; when a caller does not give it, the
setting decides. Off, the collector skips its translation step for that job. `mail.import` takes
`translate` and `summarize` (absent: Settings decide) and passes them on. The summary step returns
a `reason` when it wrote none: `off` (Settings), `off_for_job`, `not_set_up`, `failed`,
`nothing_new`. Sort mail's Import dialog has the two switches, preset from Settings and disabled
(with a word why) when that work is not set up; the window and the Jobs page say why no summaries
were written.

### T01: The worker honours the switches and says why

- `caixa/collectors/chattr.py` (`translate` option, `_translate`), `caixa/service.py`
  (`_options` presets a boolean from its setting, `mail.import` options, `_summarize` reason).
- Tests: `collectors.list` offers `translate` starting from the setting; an import with
  `translate: false` sends nothing to the endpoint while translation is on; a mail import with
  `summarize: false` writes none (reason `off_for_job`); with summaries off the reason is `off`.
- Verify: `python -m pytest -q tests/test_translation.py tests/test_summaries.py tests/test_mail_service.py tests/test_worker_protocol.py`
- [x] done

### T02: The switches in the windows

- `web/src/client/mail/SortMail.tsx` (dialog switches, the reason in the done bar),
  `pages/JobsPage.tsx` (the reason for a mail import), `locales.ts`, the built window.
- Tests (`web/tests/sort-mail.test.tsx`, `jobs-page.test.tsx`): the switches start from Settings
  and are sent; a switch for work not set up is disabled; the reason is shown.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** Every import has a Translate switch (the wizard draws it from the collectors' options, starting from Settings; Sort mail's Import dialog has it too) and a mail import a Summarize switch, preset from Settings, disabled when that work is not set up, and honoured by the worker. An import that wrote no summaries says why (off in Settings, off for this job, not set up, the model failed), in Sort mail and on the Jobs page.
- **Files:** `caixa/collectors/chattr.py`, `caixa/service.py`, `web/src/client/mail/{SortMail.tsx,mail.module.css}`, `web/src/client/pages/JobsPage.tsx`, `web/src/client/locales.ts`, `caixa/data/web/*`; tests `tests/test_translation.py`, `tests/test_summaries.py`, `web/tests/{sort-mail,jobs-page,page}.test.tsx`.
- **Errors:** a scripted edit of `service.py` did not apply (black had reflowed a line) and was redone; the first reason order said "off for this job" when Settings had summaries off (fixed: "off"); the locale guard did not know the new dynamic keys.
- **Verify:** `python -m pytest -q` 1441 passed, 1 skipped; black and mypy clean; web `tsc` clean, vitest 261 passed.

## Review

2026-11-21, in-session. **Verdict: clean (minors only).**

- Minor: a job may switch summaries on while Settings have them off, when an endpoint and model are set; this follows "preset from Settings, changeable for the job".
- Minor: the wizard's Translate switch shows even when translation is not set up; switched on, the import says "Nothing was translated" and why, as before.

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: every Chattr collector has a 'translate' option (no fixed default; x-setting translation.enabled, so the wizard starts it from Settings and an unspecified run follows the setting); off, the translation step is skipped. mail.import takes translate and summarize (absent: Settings), stored in the job's options and passed on. The summary step's result has a reason when none were written: off (Settings), off_for_job, not_set_up, failed, nothing_new; a job switched on runs summaries when they are set up even if Settings start them off. RED: 5 failing tests, then GREEN.

### 2026-11-21
T02: Sort mail's Import dialog has Translate and Summarize switches, preset from Settings, disabled with 'Set up in Settings first' when there is no endpoint and model (summaries may use translation's); they are sent with mail.import. The Imported bar and the Jobs page say why no summaries were written. Locale guard taught the two dynamic key families. RED: 3 Sort mail tests and 1 Jobs test, then GREEN. The import wizard's Translate needs no window code: it is drawn from the collector's schema.
