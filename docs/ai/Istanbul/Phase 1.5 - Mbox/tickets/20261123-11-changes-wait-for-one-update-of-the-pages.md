---
id: 20261123-11-changes-wait-for-one-update-of-the-pages
title: Changes wait for one update of the pages
type: feature
priority: high
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Changes wait for Update the pages; index-only when sorting only
parent:
depends_on: []
subtasks: []
---
## Description

With 48,000 pages, every change on the people page started a redraw of the whole box, and the work
bar (ticket 06) made the owner wait for it before the next change. The maintainer asked to queue
the changes and draw them in one pass, when they click Update (decided 2026-11-23).

## Acceptance criteria

- [x] In Caixa, sorting, naming, merging, deleting and subcategory changes are saved at once and
      wait to be drawn: the people page's bar says "N changes not yet on the pages" with an
      "Update the pages" button; nothing is locked meanwhile.
- [x] Update draws them all in one pass (the work bar locks while it runs). When only sorting and
      subcategories changed, it writes the people page alone: no matching, filing or person pages.
- [x] Changes still waiting when Caixa closes are drawn when the box is next opened.
- [x] Reloaded before an update, the people page shows each person in their current category.
- [x] Caixa's command line, and the service used without Caixa's window, draw at once as before
      (a sorting-only change there redraws the people page alone).

## Context

- `caixa/box.py` (box state), `caixa/service.py` (`_redraw`, `people.update`, `pages.pending`,
  refresh jobs, opening a box), `caixa/worker.py`, `caixa/serve.py`, `caixa/collectors/chattr.py`
  (`refresh` by scope), `tools/chattr/src/chattr/pages.py` / `commands.py` (the index alone),
  `tools/chattr/src/chattr/templates/index.js` (the bar, Update, categories on load)

## Subtasks

- [x] T01 Changes wait; one update draws them; the index alone when that is enough.

## Implementation plan

Status: done
Current task: T01

### T01: Changes wait for Update

- `Box.pending()` / `add_pending(scope)` / `take_pending(taken)`: `{"changes", "scope"}` in
  `box.yaml` (scope `index` < `pages`), under a lock.
- `Service(batch_pages=...)`: Caixa's worker and server pass True. `_redraw(scope)`: batched,
  count the change and return no job; otherwise queue a refresh of that scope (a queued one that
  covers it is reused). People methods return `pending`.
- `people.update`: queue a refresh of the pending scope (or return the one queued); `pages.pending`
  reads it. A refresh, an import or an undo takes what was pending when it started off the count
  when it succeeds. Opening a box with changes waiting queues their refresh.
- `refresh(scope="index")`: the index alone (`commands.publish_index`, `pages.render_index`).
- index.js: `pending` from each change and from `pages.pending`; the blue bar with "Update the
  pages"; the yellow work bar as before while a job runs; categories from `people.list` on load.
- Tests: `tests/test_batched_pages.py`; e2e updated where a test needs the pages drawn.
- Verify: web, Chattr, Caixa suites.

## Completion report

- **Outcome:** In Caixa, changes to people wait for **Update the pages** (the people page's blue
  bar, and the Caixa window's People section); Update draws them in one pass, the people page
  alone when only sorting and subcategories changed. Waiting changes survive closing Caixa and are
  drawn on the next opening. The people page shows current categories on loading.
- **Files:** `caixa/box.py` (`pending`, `add_pending`, `take_pending`, `update_state`,
  `STATE_LOCK`), `caixa/settings.py` (saves through it), `caixa/service.py` (`batch_pages`,
  `_redraw(scope)`, `_refresh_job`, `_redrawn`, `pages.pending`, `people.update`, pending taken by
  refreshes, imports and undo, drawn on opening; deleted people's identifiers on the removed list),
  `caixa/worker.py`, `caixa/serve.py`, `caixa/collectors/base.py`, `caixa/collectors/chattr.py`
  (`refresh(scope)`, `_sorting`), `tools/chattr/src/chattr/pages.py` (`render_index`),
  `commands.py` (`publish_index`), `templates/index.js` (the bar, Update, categories on load),
  `web/src/client/pages/PeoplePage.tsx`, `api.ts`, `locales.ts`, built `caixa/data/web/`; tests
  `tests/test_batched_pages.py` (new), `tests/test_worker_protocol.py`,
  `web/tests/e2e-categories.test.ts`, `web/tests/e2e-people.test.ts`.
- **Errors:** Naming a number and deleting that person before an update left the number in the
  box (the name was never drawn into the archive): deleting now records the person's identifiers
  too. Browser tests that need the pages drawn press Update (`drawn`).
- **Verify:** Web 277 passed; Chattr 912; Caixa 1532, 1 skipped. Screenshot checked.

### Review

Clean. Minor: before an update, a merge or a name shows on the people page only after Update (the
bar says so); categories show at once.

## Notes

Append-only running log. Each entry dated.
