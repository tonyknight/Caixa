---
id: 20261116-04-reset-a-box-s-data-keeping-its-settings
title: Reset a box's data, keeping its settings
type: feature
priority: medium
status: done
created: 2026-11-16
updated: 2026-11-16
closed: 2026-11-16
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Maintainer, 2026-11-16: during testing the box is recreated many times; add a data-only reset that keeps the box's settings (tool settings, contacts) so nothing has to be set up again.

## Acceptance criteria

- [x] Reset removes the pages, the files Caixa filed, index.html, the master's items and people, each collector's working data, undo copies, jobs and logs
- [x] It keeps box.yaml (all settings), the box name, the owner, README.md, Inbox and its contents
- [x] Names given by hand are kept and apply on the next import, unless 'forget names' is asked
- [x] Only files Caixa wrote are deleted; others are left and listed
- [x] Refused while an import runs and in read-only boxes; asks first in the browser and on the command line
- [x] Importing again after a reset gives the same box

## Context

Files Caixa wrote are known from .caixa/pages.json and the attachments' storage paths in Chattr's database. Found and fixed on the way: the service kept 'job finished' signals by job number across a change of jobs table, so after a reset (or opening another box) waiting on a new job 1 could return at once. NEEDS MAINTAINER CONFIRMATION: (1) names given by hand are kept by default; (2) the reset is not undoable (it removes the undo copies too).

## Subtasks

- [x] caixa/reset.py
- [x] Service box.reset and caixa reset
- [x] Settings card with confirmation; browser test; documentation

## Implementation plan

Status: done
Current task:

### T01: caixa/reset.py
### T02: Service box.reset and caixa reset
### T03: Settings card with confirmation; browser test; documentation

## Completion report

- **Outcome:** Done.
- **Files:** caixa/{reset,service,cli}.py, harness/src/client/{api,locales}.ts, harness/src/client/pages/SettingsPage.tsx, tests/{test_reset,test_worker_protocol}.py, harness/tests/{settings-page.test.tsx,e2e-reset.test.ts,fake-api.ts}, docs/Documentation/Collector.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1293 passed, 6 skipped; harness vitest: 273 passed (including a browser reset against the real worker). black, mypy, tsc clean.

## Review

Self-review, minors only. Checked: nothing outside the box root is deleted (paths are resolved and checked against it); .caixa/box.yaml is never among the removed parts.

## Notes

- 2026-11-16: done; two choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
