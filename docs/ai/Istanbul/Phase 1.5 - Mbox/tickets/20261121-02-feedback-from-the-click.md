---
id: 20261121-02-feedback-from-the-click
title: Feedback from the click
type: feature
priority: medium
status: done
created: 2026-11-21
updated: 2026-11-21
closed: 2026-11-21
notes: 'Done: meter beside Import and Write from the click; buttons disabled until
  the job ends.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

Feedback from the moment Import is clicked: counting what the choice brings can take long on a large mbox, and nothing showed.

## Acceptance criteria

- [x] Clicking Import shows a progress meter beside the button at once: 'Counting…' while the preview is worked out
- [x] Once the import runs, the meter beside the button shows its stages with n of N and the time taken
- [x] The Import button is disabled from the click until the job has ended (done, failed or cancelled)
- [x] Clean mail's Write button behaves the same

## Context

Phase 1.5 - Mbox hot fixes (approved 2026-11-21). See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`: *Hot fixes from the first real mbox*; M17.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** two causes of the silence: the preview (counting what the choice brings) can take long
on a large mbox with nothing on screen, and right after the job starts the window does not know
the job yet (it learns it from the next event), so it is not "busy": no bar, button enabled. Fix
both in the windows: a small meter component beside the primary button (`InlineProgress`:
"Counting…" while the preview runs, then the job's stage, n of N, a bar and the time so far); the
window counts as busy from the click until its job is known to have ended, and asks for the jobs
list right after starting one. The detailed bar at the top stays for the stage list.

### T01: The meter beside Import and Write

- `web/src/client/mail/{InlineProgress.tsx,SortMail.tsx,CleanMail.tsx,mail.module.css}`,
  `locales.ts`, the built window.
- Tests (`web/tests/sort-mail.test.tsx`, `web/tests/clean-mail.test.tsx`): while the preview is
  pending the meter says Counting and Import is disabled; after starting, before any event, the
  meter shows and Import stays disabled; a progress event shows its stage and count beside the
  button; when the job ends the button is enabled again; Clean's Write the same.
- Verify: `cd web && pnpm exec vitest run tests/sort-mail.test.tsx tests/clean-mail.test.tsx && pnpm exec tsc --noEmit`
- [x] done

## Completion report

- **Outcome:** Clicking Import shows a meter beside the button at once ("Counting what this brings…", then "Starting", then the job's stage with n of N, a bar and the time), and the button stays disabled until the job has ended; Clean mail's Write the same. The window no longer forgets a job it has not heard of yet.
- **Files:** `web/src/client/mail/{InlineProgress.tsx,SortMail.tsx,CleanMail.tsx,mail.module.css}`, `web/src/client/locales.ts`, `caixa/data/web/*`; tests `web/tests/{sort-mail,clean-mail}.test.tsx`.
- **Errors:** none.
- **Verify:** `pnpm exec vitest run` 258 passed (the real-browser Clean and Sort mail tests included); `tsc` clean.

## Review

2026-11-21, in-session. **Verdict: clean (minors only).**

- Minor: the preview itself still takes as long as before on a large mbox; it is now visible, not faster. If it is slow on real mail, making `mail.import.preview` faster is a follow-up.

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: two causes found: the preview runs with nothing on screen, and right after starting the window did not know the job yet (busy was false: no bar, button enabled). New InlineProgress beside the primary button: 'Counting what this brings…' during the preview, 'Starting' until the job is heard of, then stage, n of N, bar and time. Sort mail and Clean mail are busy from the click until the job has ended, and refresh the jobs list right after starting one. RED: 2 tests, then GREEN; web suite 258 passed; window rebuilt.
