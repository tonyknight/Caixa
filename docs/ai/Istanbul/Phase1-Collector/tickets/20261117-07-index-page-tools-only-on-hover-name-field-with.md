---
id: 20261117-07-index-page-tools-only-on-hover-name-field-with
title: Index page tools only on hover; name field with suggestions of known people
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

Maintainer, 2026-11-17: the close, open-page and name controls showed on every tile all the time. They should show only on hover; the close box in the upper right in every category but Unrecognized, which has only the open-page button; the name field on hover below the name and its counts, with Apply to its right once something is typed; and the field should look up known people as you type, so a number can join someone already in the box, while still taking a new name.

## Acceptance criteria

- [x] Nothing on a tile until the pointer (or keyboard focus) is on it
- [x] Family, Friends, Business, Acquaintances: one close box, upper right
- [x] Unassigned and Unrecognized: one open-page button, upper right (the selection tick moves to the upper left)
- [x] Unrecognized: a name field on hover below the name and counts; it stays while typing
- [x] Apply appears to the right only once something is typed; Enter applies
- [x] As you type, the people already in the box are offered (prefix first, then word and substring), with their item counts; click, or arrows and Enter, to pick
- [x] Picking a known person links the number to them and removes its tile; a new name makes a new person in Unassigned
- [x] Works on pages drawn by earlier versions

## Context

The controls showed because the maintainer's pages were drawn before their styles existed, while Caixa serves the current script (20261117-06). The script now carries its own styles, so the page's age no longer matters.

## Subtasks

- [x] index.js injects its own styles; cells hide with their tile (no :has rules in the template)
- [x] Tools: hover-only, one corner per view
- [x] Name field: hover reveal, Apply on typing, suggestions from people.list (names on the page outside Caixa), joining a known person
- [x] Template: styles and :has rules moved out; hint text
- [x] Browser test: hover-only tools, the corner, suggestions, a new name, joining a known person; guide updated

## Implementation plan

Status: done
Current task:

### T01: index.js injects its own styles; cells hide with their tile (no :has rules in the template)
### T02: Tools: hover-only, one corner per view
### T03: Name field: hover reveal, Apply on typing, suggestions from people.list (names on the page outside Caixa), joining a known person
### T04: Template: styles and :has rules moved out; hint text
### T05: Browser test: hover-only tools, the corner, suggestions, a new name, joining a known person; guide updated

## Completion report

- **Outcome:** Tiles are clean until hovered; naming an unrecognized number offers the people already in the box.
- **Files:** tools/chattr/src/chattr/templates/{index.js,index.html}, web/tests/e2e-categories.test.ts, docs/Documentation/Collector.md
- **Errors:** The field is hidden from screen readers until hovered, so the test finds it by element, not role. The tile's information pop-up covered the page while typing; hidden while the field has focus.
- **Verify:** python -m pytest -q (1281 passed); vitest run (225 passed)

## Review

Clean.

## Notes

- NEEDS MAINTAINER CONFIRMATION: Unassigned shows the open-page button (no close box: it is not in a category); All shows no buttons (a click opens the page).
