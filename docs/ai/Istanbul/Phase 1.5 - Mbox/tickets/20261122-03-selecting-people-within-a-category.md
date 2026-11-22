---
id: 20261122-03-selecting-people-within-a-category
title: Selecting people within a category
type: feature
priority: medium
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: Cmd-click, Shift-Cmd-click and box selection within categories.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

In a category a click opens the person's page (right), so there was no way to select several people there and move them into a subcategory. The maintainer asked for Cmd-click to select in place, Shift-Cmd-click for a range, and (nice to have) drawing a box around people with the mouse.

## Acceptance criteria

- [x] In a category or subcategory (in Caixa), Cmd-click (Ctrl-click elsewhere) selects or deselects a person without opening their page; a plain click still opens it
- [x] Shift-Cmd-click selects everyone between the last person selected and this one
- [x] Pressing on the empty space between people and dragging draws a box; everyone it touches is selected (added to the selection with Cmd held); a press without dragging clears the selection
- [x] The footer counts the selection; Escape clears it; dragging a selected person onto a subcategory moves everyone selected
- [x] The page says how (a hint in category views, in Caixa only); from disk nothing changes

## Context

Follows ticket 21 (`20261121-06`). `tools/chattr/src/chattr/templates/index.js` and `index.html`. Requirements: *Hot fixes*, Subcategories; M20.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** all in the index page's script (and a hint line in its template). In a category or
subcategory view, in Caixa:

- **Cmd-click** (`metaKey`, or `ctrlKey` off a Mac) on a person toggles their selection and does
  not follow the link; **Shift-Cmd-click** selects the range from the last one selected (the
  existing range selection). A plain click opens the page, as now.
- **Drawing a box:** a press with the main button on the content's empty space (not on a person,
  a button, a field or the dashboard) starts a box drawn over the page; everyone whose tile it
  touches is selected while it is drawn (added to what was selected when Cmd is held); a press
  without moving clears the selection. Also in Unassigned and Unrecognized, where a click already
  selects.
- The footer counts the selection in these views; Escape clears it; dragging a selected person
  moves everyone selected (as from Unassigned).
- A hint under the title in category views says how, shown only in Caixa.

### T01: Cmd-click, Shift-Cmd-click and drawing a box

- `tools/chattr/src/chattr/templates/{index.js,index.html}`.
- Tests (`web/tests/e2e-categories.test.ts`, real browser): in Family, Cmd-click two people (no
  page opens; "2 selected"), drag them onto a subcategory ("2 people moved to Cousins."); in the
  subcategory, Cmd-click then Shift-Cmd-click selects the range; a box drawn across the tiles
  selects them all; a press on the empty space clears; a plain click still opens a page.
- Verify: `python -m pytest -q tools/chattr/tests/test_render_pages.py tests/test_web_server.py && (cd web && pnpm exec vitest run tests/e2e-categories.test.ts)`
- [x] done

## Completion report

- **Outcome:** In a category or subcategory on the people page, ⌘-click (Ctrl-click) selects someone without opening their page, Shift-⌘-click selects everyone up to them, and dragging a box from the empty space selects everyone it touches; the selection is counted, Escape clears it, and dragging any selected person onto a subcategory moves them all. A plain click still opens the page. A hint says how, in Caixa only.
- **Files:** `tools/chattr/src/chattr/templates/{index.js,index.html}`; tests `web/tests/e2e-categories.test.ts`.
- **Errors:** the new test's subcategory upset the next test's counts (the test now removes it).
- **Verify:** `python -m pytest -q` 1469 passed, 1 skipped; black and mypy clean; web `tsc` clean, vitest 266 passed.

## Review

2026-11-22, in-session. **Verdict: clean (minors only).**

- Minor: a press on the empty space in Unassigned now clears the selection there too (it did nothing before), the same in every view.
- Minor: the box does not scroll the page when dragged past its edge; for a long category, select in parts with ⌘ held.

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: index.js: in a category or subcategory view in Caixa, Cmd/Ctrl-click toggles a person's selection without following the link, Shift-Cmd-click selects the range from the last one; a press on the content's empty space and a drag draws a box (.marquee) selecting everyone it touches (added to the selection with Cmd held; also in Unassigned and Unrecognized), a press without dragging clears; the footer counts the selection there, Escape clears. index.html: a hint shown only in Caixa in category views, and the box's style. RED: the new e2e test failed, then GREEN (the test removes its subcategory so the next one starts clean). Full verify: pytest 1469 passed, vitest 266 passed.
