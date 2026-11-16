---
id: 20261116-07-index-page-categories-people-tiles-dashboard-nord
title: 'Index page: categories, people tiles, dashboard; Nord theme'
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

Maintainer, 2026-11-16: make the box's index clean, elegant and quick for grouping people. Categories All (without the unrecognized), Family, Friends, Business, Acquaintance, Unrecognized, Unassigned in a left sidebar; people as box tiles with the name under them and their counts, a tooltip with each source's share; in Unassigned a click selects (Shift for a range) and selections are dragged onto a category, leaving Unassigned; elsewhere a click opens the person; a footer with the count and, in Unassigned, the selection; a dashboard of the box's numbers (items and file size per source) above the tiles under All only; a button back to the index on every person's page; the Nord theme on every page.

## Acceptance criteria

- [x] Categories are stored on the master's people (migration 2), follow renames and merges, survive a reset unless names are forgotten
- [x] people.categorize sorts people by id or name; unknown people and categories are refused; read-only refuses it; at most one redraw waits
- [x] The index shows the sidebar with counts, tiles with initials, counts and a source tooltip, groups and mail views, and the footer
- [x] People known only by a number, address or a nameless account are Unrecognized automatically and cannot be dragged
- [x] In Unassigned, click selects, Shift-click selects a range, drag onto a category or the footer buttons save it through Caixa and the tiles leave Unassigned; opened outside Caixa the page says sorting needs Caixa
- [x] The dashboard (under All only) counts items, conversations, files and their size per source, and the box's totals
- [x] Every person and mail page has an 'All people' button near the top; all pages use the Nord palette, keeping the orange heat map and dates
- [x] Caixa's viewer allows the index script by its hash and lets it call Caixa (connect-src 'self')

## Context

The index is a plain file in the box, so the sorting is saved by Caixa: the page posts to /api/caixa/rpc when it is shown by Caixa. In a narrow window (Caixa's viewer) the categories become a bar that stays at the top so they can still be dropped on. Playwright cannot carry a native drag into a frame, so the browser test sends the browser's own drag events; the selection, buttons and saving are driven as a person would. NEEDS MAINTAINER CONFIRMATION: (1) Groups and Mail are listed in the sidebar under the categories; (2) the category label is 'Acquaintances' (plural, like the others); (3) light or dark Nord follows the computer's setting; (4) forgetting names at reset forgets categories too; (5) faces are initials until photo faces arrive.

## Subtasks

- [x] Master: categories; service people.categorize; reset keeps them
- [x] Index: data, template, script; dashboard
- [x] Nord theme; All people button
- [x] Viewer CSP; tests; browser test; documentation

## Implementation plan

Status: done
Current task:

### T01: Master: categories; service people.categorize; reset keeps them
### T02: Index: data, template, script; dashboard
### T03: Nord theme; All people button
### T04: Viewer CSP; tests; browser test; documentation

## Completion report

- **Outcome:** Done.
- **Files:** caixa/{schema,master,service,reset}.py, caixa/collectors/chattr.py, tools/chattr/src/chattr/{pages,commands}.py, tools/chattr/src/chattr/templates/{index.html,index.js,base.html,page.html,mail.html}, harness/src/host/{box-files,page-scripts}.ts, tests/test_categories.py, tools/chattr/tests/{test_render_pages,test_render_mail}.py, harness/tests/{e2e-categories,e2e-browse,e2e-wizard}.test.ts, docs/Documentation/Collector.md
- **Errors:** The dashboard first showed a Python method instead of the item count (a template looking up 'items' on a dict); caught by the undo tests and fixed. The tooltip was clipped by the tiles' layout containment; removed.
- **Verify:** python -m pytest -q: 1313 passed, 6 skipped; harness vitest: 276 passed, including sorting three people in Caixa's viewer (selection, drag, footer button, saved categories, redrawn index). Looked at light, dark, narrow and tooltip renders.

## Review

Self-review, minors only.

## Notes

- 2026-11-16: done; five choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
