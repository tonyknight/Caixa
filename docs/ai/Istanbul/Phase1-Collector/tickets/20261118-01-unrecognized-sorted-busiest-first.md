---
id: 20261118-01-unrecognized-sorted-busiest-first
title: Unrecognized sorted busiest first
type: feature
priority: medium
status: done
created: 2026-11-18
updated: 2026-11-18
closed: 2026-11-18
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Maintainer, 2026-11-18: sort the Unrecognized category by number of items, largest on top, so the most important ones are worked on first.

## Acceptance criteria

- [x] Unrecognized lists the tiles with the most items first (ties in name order)
- [x] Every other view keeps name order, including a tile named from Unrecognized (it takes its new name's place)
- [x] Shift-click ranges follow the order on screen
- [x] Works on pages drawn before tiles carried their item count

## Context

Done in the index script, so existing pages sort without a redraw: tiles carry data-items, and older pages are read from their counts line.

## Subtasks

- [x] pages.py and index.html: data-items on each tile
- [x] index.js: arrange tiles busiest first in Unrecognized, name order elsewhere; a renamed tile takes its name's place
- [x] Browser test (a busier number listed first though it sorts after; name order back in Unassigned); guide

## Implementation plan

Status: done
Current task:

### T01: pages.py and index.html: data-items on each tile
### T02: index.js: arrange tiles busiest first in Unrecognized, name order elsewhere; a renamed tile takes its name's place
### T03: Browser test (a busier number listed first though it sorts after; name order back in Unassigned); guide

## Completion report

- **Outcome:** Unrecognized is busiest first.
- **Files:** tools/chattr/src/chattr/{pages.py,templates/index.html,templates/index.js}, web/tests/e2e-categories.test.ts, docs/Documentation/Collector.md
- **Errors:** The template's p.items read as the dictionary's items method (the same trap as the dashboard once); the field is item_count.
- **Verify:** python -m pytest -q (1281 passed); vitest run (225 passed)

## Review

Clean.

## Notes


