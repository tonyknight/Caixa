---
id: 20261101-24-import-wizard-and-jobs-pages
title: Import wizard and jobs pages
type: feature
priority: high
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: Breakdown item 24.
parent:
depends_on:
- 20261101-22-harness-plugin-skeleton
- 20261101-23-caixa-serve-launcher
subtasks: []
plan_status: done
---
## Description

The browser import flow.

## Acceptance criteria

- [x] Source list with 'how to export' cards; file picker and inbox
- [x] Options forms generated from collector schemas; preview; run with live progress; result report
- [x] Jobs and logs page; toasts on completion
- [x] Browser imports match CLI imports for every fixture

## Context

Phase1-Collector Tasks Breakdown item 24. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Authoring pages; F19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** the Caixa page grows from a status line into the authoring application: one sidebar icon,
one page, with sections (Box, Import, Jobs now; People and Browse and Settings in tickets 25 and 26).
React 18, CSS Modules, no component library, all text in `locales.ts` (English and Chinese).

- **One store** (`src/client/store.ts`, no React): box status, jobs and toasts, fed by one stream
  (`/api/caixa/events`) opened when the plugin loads. Pages read it with `useSyncExternalStore`; the
  toast host is registered in DSH's `shell.overlay` slot, so a finished import is announced wherever
  the person is in DSH.
- **Generated forms:** the import options form is drawn from each collector's JSON Schema (string,
  integer, number, boolean, enum, min/max, title, description), so a new collector appears in the
  wizard with no UI code.
- **The wizard:** source → "how to export" card → input (server-side file picker limited to the
  user's folders, the box's Inbox, or a typed path) → options → preview (a dry run) → run with live
  progress → result report (with the unnamed handles and a way to the People section).
- **Jobs:** a list with status, progress and cancel; a log view needs one new worker method,
  `jobs.log` (the tail of a job's log; reads only, so allowed read-only).
- **Build:** `*.module.css` through lightningcss in the esbuild preset, injecting a tagged style, as
  DSH's own preset does.
- **Names to confirm with the maintainer:** the section names and order; `jobs.log`; the toast
  wording.

### T01: Foundations

- The CSS Modules step in `scripts/preset.mjs`; typed API wrappers; the store; translation helper;
  `jobs.log` in the Python service and worker.
- Tests: `tests/test_service_jobs.py` (log tail); vitest for the store (events, jobs, toasts), the
  schema form model, the build's CSS handling.
- Verify: `python -m pytest -q tests/test_service_jobs.py tests/test_worker_protocol.py && pnpm --dir harness test`
- [x] done

### T02: Box and import wizard

- Box section (create, open, dashboard) and the wizard (all steps) with the generated options form,
  file picker and inbox.
- Tests: jsdom component tests driving each step with a fake API.
- Verify: `pnpm --dir harness test`
- [x] done

### T03: Jobs page and toasts

- Jobs section (list, details, log, cancel) and the toast host in `shell.overlay`.
- Tests: jsdom; the toast text and dismissal.
- Verify: `pnpm --dir harness test`
- [x] done

### T04: In the real browser, against the CLI

- End-to-end through the real DSH in a browser: importing a fixture through the wizard gives the same
  database rows and files as `caixa import` for the same fixture; the toast appears; the log shows.
- Verify: `pnpm --dir harness test` (with Node 24.9+)
- [x] done

## Completion report

- **Outcome:** The Caixa page is now an application with Box, Import and Jobs sections. Box: create or
  open a box (with a server-side folder picker), a dashboard of counts by type, people and recent
  imports. Import: a six-step wizard (source cards; the collector's own "how to export"; file picker,
  the box's Inbox, or a typed path; an options form generated from the collector's JSON Schema; a
  dry-run preview; a run with live progress; a result report). Jobs: a list with status, stage and
  cancel, and each job's log (new worker method `jobs.log`). Toasts appear in DSH's `shell.overlay`,
  so an import's end is announced anywhere in DSH. English and Chinese text throughout.
- **Verified in a real browser against the real DSH and worker:** every fixture of the synthetic
  family (iMessage, WhatsApp, Messenger, mail, Google Voice, voicemail) imported through the pages
  gives the same items, people, links, files and byte-identical HTML pages as `caixa import` for the
  same fixtures; the toast, the jobs list and a job's log show.
- **Files:** `harness/src/client/*` (store, api, pages, components, locales, CSS module),
  `harness/scripts/preset.mjs` (CSS Modules), `harness/tests/*`, `caixa/service.py` (`jobs.log`),
  `tests/test_service_jobs.py`, `tests/test_worker_protocol.py`.
- **Errors:** the first e2e run showed the Import tab does not reset a finished wizard (by design: the
  report stays until "Import another"; the test now uses that button); the old e2e page assertion
  correctly failed once the page changed; the build test's fake `react` needed `createContext`.
- **Verify:** `pnpm --dir harness test` 114 passed (jsdom component tests for every step, store,
  form model, build contract, and the two end-to-end files against real DSH); `check-types` clean;
  Python suite, black and mypy clean.

## Review

Reviewed in-session. Accepted: the result report's "unchanged" counts every item the sync passed over
in the whole box, not only this import's (so a second source shows, say, "5 new, 0 changed, 14
unchanged"): true but potentially confusing, and a candidate for the collector's RunResult to count
only its own source later; the page keeps only the last state of a progress bar's redraws in its log
view; sections hold their state while you move between them but not across a reload (except the
remembered last box); the Settings section DSH offers (`settings.section` slot) is ticket 26's;
accessibility was checked by the tests through roles and names (labels, alerts, `aria-current`,
`aria-live`), not by an audit tool. No blockers.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01-T04 done. NEEDS MAINTAINER CONFIRMATION: section names and order (Box, Import, Jobs; People, Browse, Settings follow); the worker method `jobs.log`; the toast wording; the wizard step names; remembering the last box in the browser's localStorage (`caixa.lastBox`).
