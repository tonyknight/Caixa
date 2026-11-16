---
id: 20261116-03-one-page-per-person-fast-for-very-long-histories
title: One page per person, fast for very long histories
type: feature
priority: medium
status: done
created: 2026-11-16
updated: 2026-11-16
closed: 2026-11-16
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Maintainer, 2026-11-16: replace the index.html plus one page per year with a single HTML page per person, easier to manage; very long conversations must open without waiting for the whole page. Asked whether old Chattr had code for loading large pages: it had a picture lightbox and a year-by-year calendar switcher only; its 'lazy_loading' and 'chunk_large_conversations' settings were off and never implemented.

## Acceptance criteria

- [x] Each person and each group has one page, People/<Person>/<Person>.html, with every year and source; no index.html or year pages in their folders
- [x] The page starts with a summary (count, first and last date, sources, groups, mail), a year bar that stays at the top, and each year begins with its calendar
- [x] A 100,000-message page shows its first messages in well under a second and has fully arrived in a few seconds (measured in Chromium)
- [x] The page runs no script, so it works inside Caixa's viewer, where scripts are blocked
- [x] The data island leaves out empty fields (schema chattr-page-2); version 1 pages are still read; a database rebuilt from the pages renders identical pages
- [x] The box index links each person's page with their count and years

## Context

Measured with a synthetic 100,000-message history: 84 MB page; first messages on screen 0.19 s; load 2.4 s; jump to the end 0.1 s; 718k DOM nodes. Without content-visibility the same page took 1.6 s to show its first messages and 11.5 s to load. Compacting the island took the page from 112 MB to 84 MB. A calendar switcher script was built first and removed: Caixa's viewer serves pages with scripts forbidden. NEEDS MAINTAINER CONFIRMATION: (1) the page's file name is the person's name (People/Ana Costa/Ana Costa.html) rather than index.html; (2) a date's heading still goes to the top of the page, as asked earlier, not to that year's calendar; (3) no picture lightbox (old Chattr had one).

## Subtasks

- [x] Plan one page per person and group
- [x] Single-page template: summary, year bar, a calendar per year, content-visibility
- [x] Compact data island; rebuild reads both versions
- [x] Tests, harness tests, documentation; measure

## Implementation plan

Status: done
Current task:

### T01: Plan one page per person and group
### T02: Single-page template: summary, year bar, a calendar per year, content-visibility
### T03: Compact data island; rebuild reads both versions
### T04: Tests, harness tests, documentation; measure

## Completion report

- **Outcome:** Done. render.py plans one PageSpec per person/group; pages.py draws it with the relations worked out once; the island is compacted on write and expanded on read.
- **Files:** tools/chattr/src/chattr/{render,pages,rebuild}.py, tools/chattr/src/chattr/templates/{base,page,index}.html (person.html removed), caixa/box.py, many tests under tests/ and tools/chattr/tests/, harness/tests/{e2e-browse,e2e-people}.test.ts, docs/Documentation/Collector.md, README.md
- **Errors:** none
- **Verify:** python -m pytest -q: 1287 passed, 6 skipped; harness vitest: 270 passed (including the browse page opening a person's page and following the year bar inside Caixa's viewer). Performance measured in Chromium only; Safari 18+ and Firefox 125+ support content-visibility, but were not measured.

## Review

Self-review, minors only. Checked: anchors (m-<id>, date-YYYY-MM-DD) are unique on the page; replies across people link to the other page; stale index.html and year pages from older boxes are removed by the existing page list.

## Notes

- 2026-11-16: done; three choices recorded under Context as NEEDS MAINTAINER CONFIRMATION.
