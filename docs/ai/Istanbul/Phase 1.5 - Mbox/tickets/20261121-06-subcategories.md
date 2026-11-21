---
id: 20261121-06-subcategories
title: Subcategories
type: feature
priority: medium
status: done
created: 2026-11-21
updated: 2026-11-21
closed: 2026-11-21
notes: 'Done: subcategories two levels deep on the people page, kept through a reset.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

Subcategories under Family, Friends, Business and Acquaintances on the people page.

## Acceptance criteria

- [x] Each of the four categories has a folding chevron; unfolded, its subcategories are listed alphabetically with counts, and a centered + at the bottom adds one
- [x] A subcategory can have subcategories, which cannot; double click renames; deleting moves its people (and its children's) up to its parent
- [x] People are sorted into a subcategory by dragging or the buttons; a category's count and view include its subcategories
- [x] Stored in the master (`subcategories`, `people.subcategory_id`), kept through a reset like categories; from disk, subcategories show and filter but cannot be changed

## Context

Phase 1.5 - Mbox hot fixes (approved 2026-11-21). See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`: *Hot fixes from the first real mbox*; M20.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:**

- **Stored** in the master (migration 5): `subcategories (id, category, parent_id, name)`, unique by
  category, parent and name (case ignored); `people.subcategory_id`. A subcategory's parent is
  another subcategory of the same category or none (directly under the category); a subcategory
  with a parent cannot have children (two levels at most). A person in a subcategory has its
  category too; sorting into a category alone clears the subcategory. Deleting a subcategory moves
  its people, and its children's, up to its parent (or the category itself) and deletes its
  children. Kept in `owner.json` (`subcategories`: each with its category and path of names;
  `placed`: each person's path), so they outlive a reset like categories.
- **Service:** `people.subcategories` (the tree with counts), `people.subcategory.add` (category,
  parent, name), `.rename` (id, name), `.delete` (id); `people.categorize` takes `subcategory`.
  Each change redraws the pages (one shared refresh job), as categories do.
- **The page:** Chattr's index draws, under each of the four categories, a folding chevron and its
  subcategories (alphabetical, counts, nested once), and a centered + at the bottom of the
  unfolded list; tiles carry `data-sub`. `index.js` folds and unfolds (remembered), adds with +,
  renames on double click, deletes with a × (asking first), shows a subcategory's people (a
  category's view includes its subcategories), and takes people dragged onto a subcategory (from
  Unassigned or from a category). Opened from disk: subcategories show and filter; +, rename,
  delete and dragging are not offered.

### T01: Subcategories in the master and the service

- `caixa/schema.py` (migration 5), `caixa/master.py`, `caixa/owner.py`, `caixa/service.py`.
- Tests (`tests/test_subcategories.py`): add under a category and under a subcategory, not under a
  sub-subcategory, not twice; rename; sort a person into one (and back to the category); delete
  moves people up and removes children; the tree's counts include children; owner.json keeps them
  through a reset; the service methods redraw.
- Verify: `python -m pytest -q tests/test_subcategories.py tests/test_owner.py tests/test_worker_protocol.py`
- [x] done

### T02: The index draws them

- `tools/chattr/src/chattr/{commands.py,pages.py}`, `templates/index.html`,
  `caixa/collectors/chattr.py` (passes them from the master).
- Tests: the index has each category's subcategories nested with counts, the + only for the four
  categories, and `data-sub` on tiles.
- Verify: `python -m pytest -q tests/test_subcategories.py tools/chattr/tests/test_render_pages.py`
- [x] done

### T03: Folding, adding, renaming, deleting and sorting on the page

- `tools/chattr/src/chattr/templates/index.js`.
- Tests (`web/tests/e2e-categories.test.ts`, real browser against `caixa serve`): unfold Friends,
  add "School" with +, add "Class of 98" under it and no + under that, rename on double click,
  drag a person onto it (counted in Friends too), delete it (the person back in Friends); from
  `file://` the subcategories show and filter with no + and no dragging.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** Family, Friends, Business and Acquaintances each fold open on the people page to their subcategories (alphabetical, with counts) and a centered + to add one; a subcategory can hold its own, which cannot. Double click renames, the × on hover deletes (its people move up). People are dragged into a subcategory from Unassigned or from a category, and a category's count and view include its subcategories. Stored in the master (migration 5) and in `owner.json`, so they outlive a reset. From disk they show and filter only.
- **Files:** `caixa/{schema,master,owner,service}.py`, `caixa/collectors/chattr.py`, `tools/chattr/src/chattr/{commands,pages}.py`, `tools/chattr/src/chattr/templates/{index.html,index.js}`; tests `tests/test_subcategories.py` (new), `tests/{test_owner,test_worker_protocol}.py`, `web/tests/e2e-categories.test.ts`.
- **Errors:** my first index test expected two + buttons (there are three: one per category list and one per top-level subcategory); a reworded footer message broke the existing test (the original wording kept); the chevron alignment took two tries (screenshots).
- **Verify:** `python -m pytest -q` 1463 passed, 1 skipped; black and mypy clean; web `tsc` clean, vitest 265 passed.

## Review

2026-11-21, in-session. **Verdict: clean (minors only).**

- Minor: in one full web run the existing category e2e test timed out waiting 30 s while all browser tests started servers at once; it passed alone three times and in the next full run. Watch for it.
- Minor: a subcategory made on the page is drawn into `index.html` by the redraw job that follows; until then a page reloaded from disk does not have it.
- Spec: files as planned; all acceptance criteria met.

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: migration 5 (subcategories table with a case-insensitive unique index on category, parent and name; people.subcategory_id). Master: add_subcategory (four categories only; under a category or a top-level subcategory), rename, delete (people and children's people up to the parent; children deleted), subcategory(person), subcategories() (by category order, parent then children by name, counts include children), subcategory_path/ensure_subcategory; set_category takes a subcategory of the same category (none = the category itself); merge carries it. owner.json gains subcategories (category + path) and placed (person → path), applied after a reset. Service: people.subcategories, people.subcategory.add/rename/delete (write, redraw), people.categorize(subcategory). RED: 5 tests, then GREEN.

### 2026-11-21
T02: Chattr publish/render_pages/_index take subcategories {tree, placed}; Caixa's collector passes them from the master on every redraw. The index's sidebar draws each of the four categories in a row with a folding chevron, its subcategories (alphabetical, counts incl. children) and their own, nested once, and a + (hidden until the script shows it in Caixa) at the bottom of each list that may grow; tiles carry data-sub. Hidden on the narrow layout. RED then GREEN (my first expectation of two + was wrong: Friends and each top-level subcategory have one).

### 2026-11-21
T03: index.js: sub-<id> views (a subcategory's people and its own's; a category's view includes them), chevrons fold and unfold (folded to begin with, remembered in localStorage), + makes a subcategory inline (Enter saves, Escape or leaving cancels), double click renames, a × on hover deletes after asking (people move up; the view follows), drop targets delegated so new subcategories take dragged people; people can be dragged from a category or a subcategory view too. Read-only from disk: no +, ×, renaming or dragging. Rows without a chevron indented to line up. RED: the e2e test failed (nothing folded), then GREEN; the existing footer wording kept. Visual check from a screenshot.
