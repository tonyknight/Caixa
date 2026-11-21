---
id: 20261121-03-switches-for-each-import
title: Switches for each import
type: feature
priority: medium
status: in-progress
created: 2026-11-21
updated: 2026-11-21
closed:
notes: ''
parent:
depends_on: []
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

Translate and Summarize switches for each import, preset from Settings, and an import result that says why no summaries were written.

## Acceptance criteria

- [ ] The import wizard has a Translate switch; Sort mail's Import dialog has Translate and Summarize; each starts as Settings says
- [ ] Job options `translate` and `summarize` are honoured: off, that job translates or summarizes nothing
- [ ] A mail import's result says why no summaries were written (off in Settings, off for this job, not set up, the endpoint failed), shown in the window and on the Jobs page

## Context

Phase 1.5 - Mbox hot fixes (approved 2026-11-21). See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`: *Hot fixes from the first real mbox*; M18.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: every Chattr collector has a 'translate' option (no fixed default; x-setting translation.enabled, so the wizard starts it from Settings and an unspecified run follows the setting); off, the translation step is skipped. mail.import takes translate and summarize (absent: Settings), stored in the job's options and passed on. The summary step's result has a reason when none were written: off (Settings), off_for_job, not_set_up, failed, nothing_new; a job switched on runs summaries when they are set up even if Settings start them off. RED: 5 failing tests, then GREEN.
