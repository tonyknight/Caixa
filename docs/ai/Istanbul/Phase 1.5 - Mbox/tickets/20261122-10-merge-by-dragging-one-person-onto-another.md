---
id: 20261122-10-merge-by-dragging-one-person-onto-another
title: Merge by dragging one person onto another
type: feature
priority: medium
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: merge by dropping one person onto another; redraw race fixed.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

Merging people should be as easy as dragging one onto another: the dragged person and their data take the identity of the person dropped onto.

## Acceptance criteria

- [x] Dragging a person onto another person's tile (in Caixa) asks once, then merges the dragged one into the other: their conversations, files and names become the other's
- [x] Someone known only by a number or address can be dragged onto a named person (their numbers join that person); dropping onto someone with no name is refused, saying to name them first
- [x] The dragged tile goes, the other's count grows, and the pages are redrawn

## Context

From the maintainer's first imports of older boxes (2026-11-22). Requirements: *Hot fixes*.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** in the index page's script a tile is also a drop target. Dropping a named person on another asks ("Merge X into Y?", Merge focused, so Enter confirms) and calls `people.merge` (source, target by id, from `people.list`); a tile with no name has its numbers and addresses linked to the target (`people.link`, as naming does). The source's tile is removed, the target's item count adds the source's, and the redraw job the change starts redraws the pages.

### T01: Drop one person on another

- `tools/chattr/src/chattr/templates/{index.js,index.html}`.
- Tests (`web/tests/e2e-categories.test.ts`): a person dragged onto another, confirmed, is merged (gone from the people list, the other's count grown); a number dragged onto a person joins them; dropping onto a tile with no name is refused.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** Dropping one person onto another merges them after one question: the dragged person and their data take the other's identity. A number or address dropped onto a person joins them; dropping onto someone with no name is refused. Also fixed, found while testing: a redraw could undo a category change made a moment before.
- **Files:** `tools/chattr/src/chattr/templates/{index.js,index.html}`, `caixa/{owner,reset,service}.py`, `docs/Documentation/Collector.md`; tests `web/tests/e2e-categories.test.ts`, `tests/test_owner.py`.
- **Errors:** the race (a redraw re-applying `owner.json` read its previous version and put an old category back); fixed by not re-applying a version Caixa wrote itself, except when opening a box or resetting.
- **Verify:** `python -m pytest -q` 1481 passed, 1 skipped; black and mypy clean; web `tsc` clean, vitest 272 passed; the categories e2e three times in a row.

## Review

2026-11-22, in-session. **Verdict: clean (minors only).**

- Minor: a merge cannot be undone on its own (only by undoing the last import, which undoes changes to people since); the question says so.

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: index.js: a tile is a drop target while dragging (dashed outline); dropping one person on another asks ('Merge X into Y?' / 'Add +number to Y?', Merge focused) then calls people.merge with ids from people.list (or people.link for each handle of a tile with no name); the dragged tile goes and the target's item count grows; dropping onto a tile with no name says to name it first. Found while testing: a redraw job re-applying owner.json could undo a category change made a moment before (it read the file's previous version); owner.apply now skips a version Caixa wrote itself, except when forced (opening a box, a reset). RED: the merge e2e test and tests/test_owner.py's race test, then GREEN; the categories e2e passed three times in a row. Full verify: pytest 1481 passed, vitest 272 passed.
