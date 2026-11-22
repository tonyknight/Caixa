---
id: 20261122-09-drag-anyone-onto-any-category
title: "Drag anyone onto any category"
type: feature
priority: medium
status: todo
created: 2026-11-22
updated: 2026-11-22
closed:
notes: ""
parent:
depends_on: []
subtasks: []
---

## Description

Only Unassigned (and, since ticket 21, a category's people) could be dragged onto a category; the maintainer wants it allowed everywhere, Unrecognized included.

## Acceptance criteria

- [ ] In Caixa, a person can be dragged onto a category or subcategory from every view (All, each category and subcategory, Unassigned, Unrecognized)
- [ ] Someone known only by a number or address (Unrecognized) dragged onto a category is kept as a person under that name, then sorted
- [ ] Unassigned takes people dropped on it (back to no category)

## Context

From the maintainer's first imports of older boxes (2026-11-22). Requirements: *Hot fixes*.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: approved
Current task: T01

**Design:** in the index page's script every tile is draggable in Caixa, whatever the view (a plain click still opens the page where it did). Dropping a tile with no name first links its numbers and addresses to a person named as the tile is (as naming does), then sorts it. The Unassigned link becomes a drop target (`data-category=""`: back to none).

### T01: Dragging from anywhere, onto anything

- `tools/chattr/src/chattr/templates/{index.js,index.html}`.
- Tests (`web/tests/e2e-categories.test.ts`): from All and from Unrecognized, a person is dragged onto a category and sorted; the unrecognized one is kept as a person; dropping on Unassigned clears the category.
- Verify: `cd web && pnpm exec vitest run tests/e2e-categories.test.ts`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
