---
id: 20261123-06-work-bar-that-pauses-changes-on-the-people-page
title: Work bar that pauses changes on the people page
type: feature
priority: high
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Work bar on the people page; changes wait for Caixa's queue
parent:
depends_on: []
subtasks: []
---
## Description

Sorting many people on the people page, the page shows each change at once while Caixa saves it
and redraws the pages in the background; nothing shows that work, and the owner can get ahead of
it. The maintainer asked for a prominent status bar for large jobs that locks out new changes until
the queue is done.

## Acceptance criteria

- [x] While Caixa has a job queued or running in the box (a redraw, an import, summaries…), the
      people page shows a bar across the top: what it is doing, its stage, its progress when known,
      how many more wait, and that changes are paused.
- [x] While the bar shows (and from the moment a change is sent), no new change starts: dragging,
      dropping, the move buttons, Delete, naming, merging, adding/renaming/deleting subcategories
      are refused with a word in the status bar. Browsing, switching views and selecting still work.
- [x] A save that is quick shows no bar; the bar goes when the queue is empty.
- [x] Opening the page while a job runs (a redraw when the box opens) shows the bar at once.
- [x] Opened from disk, nothing changes.

## Context

- `tools/chattr/src/chattr/templates/index.js` (rpc, the entry points of every change)
- `jobs.list` (status, kind, stage, message, current, total)

## Subtasks

- [x] T01 The work bar and the pause.

## Implementation plan

Status: done
Current task: T01

### T01: The work bar and the pause

- `rpc`: count the changes in flight (not `jobs.list` or `people.list`); when one ends, watch.
- `watch`: ask `jobs.list` every 0.7 s while anything is queued or running or a change is in
  flight; once at page load.
- `refresh`: `.app.locked` while busy; the bar (`role=status`, fixed at the top, Nord yellow) with
  the first running job's label (by kind), stage message, a fill for current/total (a moving stripe
  when unknown), "and N more waiting", and "Changes are paused until this is done."; shown at once
  for a job, after 0.6 s for a save alone.
- `blocked()`: at the start of dragstart (prevented), categorize/move, confirmRemoval, naming,
  confirmMerge (drop), subcategory add/rename/delete: when busy, say why, nudge the bar, refuse.
- Tests: e2e in `web/tests/e2e-categories.test.ts`: a change shows the bar and refuses a second
  one until the redraw is done, then works again; a unit-level check is not possible (browser
  script).
- Verify: web, Chattr and Caixa suites; a screenshot of the bar.

## Completion report

- **Outcome:** The people page shows a work bar while Caixa is busy and refuses new changes until
  the queue is empty; it appears at once when the page opens on a running job.
- **Files:** `tools/chattr/src/chattr/templates/index.js`; `web/tests/e2e-categories.test.ts`;
  Requirements (decision recorded).
- **Errors:** (1) A look at the queue begun before a change ended could read an empty queue and
  unlock too early: each change now waits for its own redraw job, and a stale look is repeated.
  (2) Sorting chained a step before its first request, letting a second drag in: a change of
  several steps now holds the lock from its first step. (3) The bar first showed without words and
  over the page: it now fills its words on every update and sits above the page. The browser
  tests that make changes back to back wait for the page to unlock (`unlocked`).
- **Verify:** Web 276 passed (a new browser test: a second change at once is refused, the bar
  shows, the change works after); Chattr 894; Caixa 1508, 1 skipped. Screenshot checked.

### Review

Clean. Minor: the page looks at the queue every 0.7 s while busy, so it unlocks up to 0.7 s after
Caixa is done.

## Notes

Append-only running log. Each entry dated.
