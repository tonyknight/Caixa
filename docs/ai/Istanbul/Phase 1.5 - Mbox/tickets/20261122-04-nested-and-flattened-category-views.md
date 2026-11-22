---
id: 20261122-04-nested-and-flattened-category-views
title: Nested and flattened category views
type: feature
priority: medium
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: categories nested like folders; Cmd-click flattens (blue label).'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

A category's view and count included everyone in its subcategories, so there was no way to see who was still loose in the category. The maintainer asked for it to work like a file system (a category or subcategory shows and counts only its own members), with a flattened view on demand: Cmd-click a category's label to show and count everyone in it and its subcategories, its label in blue; Cmd-click again to go back.

## Acceptance criteria

- [x] A category's view and count hold only its people not in a subcategory; a subcategory's, only its own people (not its subcategories')
- [x] Cmd-click (Ctrl-click) on a category's label, or on a subcategory that can have subcategories, flattens it: its view and count include everyone beneath it, and its label is blue (also when it is the selected view)
- [x] Cmd-click on a flattened label goes back to the nested view and count; the choice is remembered like folding
- [x] It works from disk too (it only changes what is shown); moving people keeps working in both modes

## Context

Follows ticket 21 (`20261121-06`). `tools/chattr/src/chattr/templates/{index.js,index.html}`; `docs/Documentation/Collector.md` (the index page). Requirements: *Hot fixes*, Subcategories; M20 (changes "a category's count and view include its subcategories": now on request).

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** in the index page's script, each label (the four categories and the subcategories that
can have their own) is **nested** (the default: its view and count hold only its own people, as a
folder holds only its own files) or **flattened** (everyone beneath it too). Cmd-click (Ctrl-click)
on the label switches it and shows it; a flattened label has blue text (and, when selected, a light
background with a blue outline rather than the filled one, so the blue stays visible) and the view's
title says "with its subcategories". The choice is remembered in the browser, as folding is. The
counts the page is drawn with stay as they are; the script counts again as now. This changes the
Requirements' "a category's count and view include its subcategories" to "on request (flattened)",
recorded there.

### T01: Nested by default, flattened with Cmd-click

- `tools/chattr/src/chattr/templates/{index.js,index.html}`, `docs/Documentation/Collector.md`,
  the Requirements' subcategories paragraph.
- Tests (`web/tests/e2e-categories.test.ts`): after Sara is moved into Class of '98, Friends counts
  0 and shows nobody, School too; Cmd-click Friends: it counts 1, shows Sara, its label is blue;
  Cmd-click School the same; Cmd-click Friends again: 0; a plain click on a flattened label keeps it
  flattened.
- Verify: `python -m pytest -q tools/chattr/tests/test_render_pages.py tests/test_subcategories.py && (cd web && pnpm exec vitest run tests/e2e-categories.test.ts)`
- [x] done

## Completion report

- **Outcome:** On the people page each category and subcategory shows and counts only its own people, as a folder does. ⌘-click (Ctrl-click) on a category's label, or on a subcategory that has its own, flattens it: everyone beneath it is shown and counted, its label is blue and the title says "with its subcategories"; ⌘-click again nests it. Remembered in the browser, and works from disk too.
- **Files:** `tools/chattr/src/chattr/templates/{index.js,index.html}`, `docs/Documentation/Collector.md`, the Requirements; tests `web/tests/e2e-categories.test.ts`.
- **Errors:** an `await` inside a non-async arrow in the test (fixed).
- **Verify:** `python -m pytest -q` 1469 passed, 1 skipped; black and mypy clean; web `tsc` clean, vitest 266 passed.

## Review

2026-11-22, in-session. **Verdict: clean (minors only).**

- Minor: the counts written into the page (seen only without its script) are still the flattened ones; the script recounts as soon as the page opens.

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: index.js: belongs() is nested by default (a category: its people with no subcategory; a subcategory: its own people) and flattened per label (everyone beneath it) when flat[view]; Cmd/Ctrl-click on a category's label or a top-level subcategory's toggles it (remembered in localStorage, as folding), marks the label .flat and the title 'X, with its subcategories'; counts follow. index.html: blue label (a light background with a blue outline when selected), and the hint mentions it. Collector.md and the Requirements (M20 and the subcategories paragraph) updated. RED: the updated e2e test (Friends still counted 1), then GREEN. Full verify: pytest 1469 passed, vitest 266 passed.
