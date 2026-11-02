---
id: 20261101-24-import-wizard-and-jobs-pages
title: Import wizard and jobs pages
type: feature
priority: high
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 24.
parent:
depends_on:
- 20261101-22-harness-plugin-skeleton
- 20261101-23-caixa-serve-launcher
subtasks: []
current_task: T02
plan_status: in-progress
---
## Description

The browser import flow.

## Acceptance criteria

- [ ] Source list with 'how to export' cards; file picker and inbox
- [ ] Options forms generated from collector schemas; preview; run with live progress; result report
- [ ] Jobs and logs page; toasts on completion
- [ ] Browser imports match CLI imports for every fixture

## Context

Phase1-Collector Tasks Breakdown item 24. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Authoring pages; F19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

### T03: Jobs page and toasts

- Jobs section (list, details, log, cancel) and the toast host in `shell.overlay`.
- Tests: jsdom; the toast text and dismissal.
- Verify: `pnpm --dir harness test`
- [ ] done

### T04: In the real browser, against the CLI

- End-to-end through the real DSH in a browser: importing a fixture through the wizard gives the same
  database rows and files as `caixa import` for the same fixture; the toast appears; the log shows.
- Verify: `pnpm --dir harness test` (with Node 24.9+)
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
