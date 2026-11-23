---
id: 20261123-02-calendar-at-the-top-of-person-pages
title: Calendar at the top of person pages
type: chore
priority: high
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Calendar moved to the top of person pages (a fold per year)
parent:
depends_on: []
subtasks: []
---
## Description

A calendar before each year's messages made long person pages hard to use. The maintainer asked
to drop it there and use the top of the page as the calendar navigation, until person pages are
redesigned in the next project.

## Acceptance criteria

- [x] No calendar among the messages; each year keeps only its heading.
- [x] One calendar block at the top, under the year bar: a fold per year, newest first and open.
- [x] A day with messages still links to its date; a date still leads back to the top.

## Context

- `tools/chattr/src/chattr/templates/page.html`, `base.html` (styles)
- `tools/chattr/tests/test_render_pages.py`

## Subtasks

- [x] T01 Move the year calendars to the top of the page.

## Implementation plan

Status: done
Current task: T01

### T01: Calendars at the top

- `page.html`: take the calendar out of each `year-block`; add `<section class="calendars">`
  after the year bar with a `<details class="calendar" id="cal-YYYY">` per year, newest first,
  the newest open (no script needed).
- `base.html`: styles for the folds.
- Tests: the test helper reads a year's calendar from the top; a new test checks the block's
  place, order and open fold, and that `<main>` has no calendar.
- Verify: Chattr, Caixa and web suites; a screenshot of a person page.

## Completion report

- **Outcome:** Person and group pages show the calendar at the top, one fold per year (newest open);
  the messages run on without calendars between years.
- **Files:** `tools/chattr/src/chattr/templates/page.html`, `base.html`;
  `tools/chattr/tests/test_render_pages.py`.
- **Errors:** None.
- **Verify:** Chattr `pytest -q`: 891 passed. Caixa `pytest -q`: 1496 passed, 1 skipped. Web: 273
  passed. Screenshot checked (fold open, a day jumping to its messages).

### Review

Clean. The template change alters the pages' fingerprint, so boxes are redrawn when next opened.

## Notes

Append-only running log. Each entry dated.
