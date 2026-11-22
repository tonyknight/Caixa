---
id: 20261122-09-drag-anyone-onto-any-category
title: Drag anyone onto any category
type: feature
priority: medium
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: drag anyone onto any category, from every view.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

Only Unassigned (and, since ticket 21, a category's people) could be dragged onto a category; the maintainer wants it allowed everywhere, Unrecognized included.

## Acceptance criteria

- [x] In Caixa, a person can be dragged onto a category or subcategory from every view (All, each category and subcategory, Unassigned, Unrecognized)
- [x] Someone known only by a number or address (Unrecognized) dragged onto a category is kept as a person under that name, then sorted
- [x] Unassigned takes people dropped on it (back to no category)

## Context

From the maintainer's first imports of older boxes (2026-11-22). Requirements: *Hot fixes*.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** in the index page's script every tile is draggable in Caixa, whatever the view (a plain click still opens the page where it did). Dropping a tile with no name first links its numbers and addresses to a person named as the tile is (as naming does), then sorts it. The Unassigned link becomes a drop target (`data-category=""`: back to none).

### T01: Dragging from anywhere, onto anything

- `tools/chattr/src/chattr/templates/{index.js,index.html}`.
- Tests (`web/tests/e2e-categories.test.ts`): from All and from Unrecognized, a person is dragged onto a category and sorted; the unrecognized one is kept as a person; dropping on Unassigned clears the category.
- Verify: `cd web && pnpm exec vitest run tests/e2e-categories.test.ts`
- [x] done

## Completion report

- **Outcome:** On the people page in Caixa, anyone can be dragged onto any category, subcategory or Unassigned, from every view. Someone known only by a number or address is kept as a person under that name as they are sorted.
- **Files:** `tools/chattr/src/chattr/templates/{index.js,index.html}`; tests `web/tests/e2e-categories.test.ts`.
- **Errors:** none.
- **Verify:** the categories e2e tests passed; `tests/test_web_server.py`, Chattr's page tests and the subcategory tests passed.

## Review

2026-11-22, in-session. **Verdict: clean (minors only).**

- Minor: a number dragged onto a category becomes a person named by that number; rename them on their tile or by merging (ticket `20261122-10`).

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: index.js: every tile is draggable in Caixa, in every view; a tile with no name dropped on a category is first kept as a person under its tile's name (people.link for each of its handles, as naming does), then sorted; Unassigned (data-category="") takes drops (no category); after a drop the view is drawn again; a drag that drops nowhere leaves nothing selected where selecting does not show. RED (the new e2e test), then GREEN.
