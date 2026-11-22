---
id: 20261122-10-merge-by-dragging-one-person-onto-another
title: "Merge by dragging one person onto another"
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

Merging people should be as easy as dragging one onto another: the dragged person and their data take the identity of the person dropped onto.

## Acceptance criteria

- [ ] Dragging a person onto another person's tile (in Caixa) asks once, then merges the dragged one into the other: their conversations, files and names become the other's
- [ ] Someone known only by a number or address can be dragged onto a named person (their numbers join that person); dropping onto someone with no name is refused, saying to name them first
- [ ] The dragged tile goes, the other's count grows, and the pages are redrawn

## Context

From the maintainer's first imports of older boxes (2026-11-22). Requirements: *Hot fixes*.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: approved
Current task: T01

**Design:** in the index page's script a tile is also a drop target. Dropping a named person on another asks ("Merge X into Y?", Merge focused, so Enter confirms) and calls `people.merge` (source, target by id, from `people.list`); a tile with no name has its numbers and addresses linked to the target (`people.link`, as naming does). The source's tile is removed, the target's item count adds the source's, and the redraw job the change starts redraws the pages.

### T01: Drop one person on another

- `tools/chattr/src/chattr/templates/{index.js,index.html}`.
- Tests (`web/tests/e2e-categories.test.ts`): a person dragged onto another, confirmed, is merged (gone from the people list, the other's count grown); a number dragged onto a person joins them; dropping onto a tile with no name is refused.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
