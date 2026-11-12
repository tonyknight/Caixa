---
id: 20261112-06-hot-fix-progress-during-preview-and-import
title: 'Hot fix: progress during preview and import'
type: feature
priority: medium
status: done
created: 2026-11-12
updated: 2026-11-12
closed: 2026-11-12
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

A large export gave no sign of life: the preview showed only 'Looking at the export…' for as long as it took, and the import showed a stage name and a bar with no numbers. The maintainer asked for better progress during import.

## Acceptance criteria

- [x] The preview shows its stages, 'N of M', what is being read, a bar and the time so far, and can be stopped (the worker stops counting).
- [x] The import shows all six stages with the current one marked, 'N of M', the time so far and, once there is enough to go on, roughly how long is left.
- [x] Reporting progress does not slow a large import: thousands of quick steps are announced at most a few times a second, always including each stage's first and last step.
- [x] A collector whose preview takes no progress callback still works.

## Context

The worker answers requests on a thread pool, so a preview can announce `preview.progress` while it runs; the host already forwards any notification to the browser. `import.preview` takes an optional `token`; `import.preview.cancel(token)` makes the progress callback raise. Job progress used to save to the jobs table and announce on every step (one commit per conversation); `_Pace` now passes on stage changes, a stage's first and last step, and otherwise one step per 0.2 s.

## Subtasks

- [x] Tests: preview progress, cancelling, pacing, an older collector (tests/test_progress.py).
- [x] `Service._Pace`, `import.preview(token)`, `import.preview.cancel`; `_Chattr.preview(progress=)`.
- [x] Client: `ProgressView` (stages, count, time so far, time left), the store's `previews`, the wizard's preview and run steps; tests.
- [x] Browser tests made steadier: wait for Caixa's routes before the first call; wait for the People list instead of counting it at once.

## Implementation plan

Status: done
Current task:

### T01: Tests: preview progress, cancelling, pacing, an older collector (tests/test_progress.py).
### T02: `Service._Pace`, `import.preview(token)`, `import.preview.cancel`; `_Chattr.preview(progress=)`.
### T03: Client: `ProgressView` (stages, count, time so far, time left), the store's `previews`, the wizard's preview and run steps; tests.
### T04: Browser tests made steadier: wait for Caixa's routes before the first call; wait for the People list instead of counting it at once.

## Completion report

- **Outcome:** A person can see what a preview or an import is doing, how far it is, and stop a preview.
- **Files:** caixa/service.py, caixa/collectors/{base,chattr}.py, harness/src/client/{api.ts,store.ts,locales.ts,caixa.module.css,components/Progress.tsx,pages/ImportPage.tsx}, tests/test_progress.py, harness/tests/{progress,import-page}.test.tsx, e2e-support.ts, e2e-people.test.ts
- **Errors:** none
- **Verify:** `python -m pytest -q` 1077 passed, 6 skipped; harness 248 passed, twice in a row; black, mypy, tsc clean.

## Review

Clean. Not done: a preview still does the whole conversion to count, so for a very large export the work is done twice (preview, then import). Skipping or sampling the preview for large exports is a possible follow-up; it was left alone because the preview is also what tells a person which names are unknown.

## Notes

- 2026-11-12: The 'time left' is only shown after 5 steps and 3 seconds of a counted stage, from that stage's own speed.
