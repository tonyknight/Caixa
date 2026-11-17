---
id: 20261117-02-index-page-unassign-select-delete-open-in-new
title: 'Index page: unassign, select, delete, open in new window, name unrecognized'
type: feature
priority: high
status: done
created: 2026-11-17
updated: 2026-11-17
closed: 2026-11-17
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

On the box's index page: a close box (×) on hover sends a person in Family, Friends, Business or Acquaintances back to Unassigned; in Unassigned and Unrecognized people are selected and Delete or Backspace removes them after a confirmation dialogue; hovering a tile there shows a button that opens the page in a new window, keeping the selection; an Unrecognized tile has a name field with Apply that keeps the person under that name (stored in the owner's preference file).

## Acceptance criteria

- [x] × on hover in assigned categories moves the person back to Unassigned (people.categorize with null)
- [x] Click and Shift-click select in Unassigned and Unrecognized
- [x] Delete/Backspace asks in an in-page dialog, then calls people.delete and removes the tiles
- [x] ↗ on hover opens the page in a new window; the selection is kept
- [x] Name field + Apply (or Enter) on Unrecognized tiles links every handle of the tile to the name; the tile moves to Unassigned
- [x] Works inside Caixa's viewer; opened from the folder, the page browses and says changes need Caixa

## Context

Maintainer, 2026-11-17 (fix-ups 2 and the deletion methods). Unrecognized tiles carry `data-handles` (service, identifier) so they can be named or removed. Caixa's viewer frame now allows popups (escaping the sandbox) for the new-window button; the script hash in page-scripts.ts follows index.js.

## Subtasks

- [x] Tiles wrapped in cells by the script, with × and ↗ tools and the name field (static HTML unchanged)
- [x] Selection in Unrecognized, Delete/Backspace and the confirmation dialog
- [x] Naming from the tile through people.link
- [x] Viewer sandbox allows popups; script hash updated
- [x] Browser test extended (×, naming, new window, delete); docs

## Implementation plan

Status: done
Current task:

### T01: Tiles wrapped in cells by the script, with × and ↗ tools and the name field (static HTML unchanged)
### T02: Selection in Unrecognized, Delete/Backspace and the confirmation dialog
### T03: Naming from the tile through people.link
### T04: Viewer sandbox allows popups; script hash updated
### T05: Browser test extended (×, naming, new window, delete); docs

## Completion report

- **Outcome:** All four interactions work in Caixa's viewer; the redrawn index file reflects them.
- **Files:** tools/chattr/src/chattr/{pages.py,templates/index.html,templates/index.js}, harness/src/host/page-scripts.ts, harness/src/client/pages/BrowsePage.tsx, harness/tests/{e2e-categories.test.ts,browse-page.test.tsx}, tools/chattr/tests/test_render_pages.py, docs/Documentation/Collector.md
- **Errors:** A sandboxed frame never fires a form's submit event (no allow-forms), so Apply is a plain button with Enter handled by the script. The ↗ label kept the old name after naming; labels now follow.
- **Verify:** python -m pytest -q (1326 passed); vitest run (276 passed); tsc clean

## Review

Clean. A just-named tile still links to its old page until the redraw job finishes (documented in the test).

## Notes

- NEEDS MAINTAINER CONFIRMATION: the name field is on Unrecognized tiles only; select/delete/new window work in both Unassigned and Unrecognized.
- NEEDS MAINTAINER CONFIRMATION: the confirmation is an in-page dialog, not the browser's own confirm().
