---
id: 20261122-01-pages-drawn-by-an-older-caixa-are-redrawn
title: Pages drawn by an older Caixa are redrawn
type: bug
priority: high
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: pages drawn by an older Caixa are redrawn once on opening.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

The maintainer opened a box after ticket 21 and found no subcategories on its index page: the box's pages are drawn at import, and Caixa updates only the scripts of a page drawn by an older version, not its contents (the chevrons and + are in the page). Nothing redraws the pages until an import or a change to people.

## Acceptance criteria

- [x] Every drawing of the pages records which page templates drew them (a fingerprint of Chattr's templates, in `box.yaml`)
- [x] Opening a box (not read-only) whose pages were drawn by other templates starts one Pages redrawn job; opening it again starts nothing
- [x] A box with nothing imported, or one already being moved into Attachments folders, starts no extra job

## Context

Bug found by the maintainer after ticket 21 (`20261121-06`). Same mechanism as ticket 14's layout move (`Box.layout`, the refresh job on opening). Requirements: *Hot fixes*, M20.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `chattr.pages.templates_fingerprint()` is a short hash of every file in Chattr's
`templates/` folder. Caixa's collector records it in `box.yaml` (`pages`) after each drawing.
When a box is opened (not read-only) and it has a Chattr store, its `pages` differs from the
current fingerprint, and no layout move is starting, Caixa starts one refresh job ("Drawing the
pages again with this version of Caixa"), which records the new fingerprint when it draws.

### T01: Record what drew the pages, and redraw when it changed

- `tools/chattr/src/chattr/pages.py`, `caixa/box.py` (`pages`, `mark_pages`),
  `caixa/collectors/chattr.py`, `caixa/service.py`.
- Tests (`tests/test_pages_redrawn.py`): an import records the fingerprint; a box whose pages were
  drawn by other templates is redrawn by one job on opening (its index then has the chevrons), and
  opening it again starts nothing; an empty box starts nothing.
- Verify: `python -m pytest -q tests/test_pages_redrawn.py tests/test_attachments_move.py && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** Every drawing of the pages records which templates drew them, and opening a box whose pages were drawn by an older Caixa redraws them once (a Pages redrawn job), so new parts of a page (such as the subcategories on the index) appear without an import.
- **Files:** `tools/chattr/src/chattr/pages.py`, `caixa/box.py`, `caixa/collectors/chattr.py`, `caixa/service.py`; tests `tests/test_pages_redrawn.py`.
- **Errors:** none.
- **Verify:** `python -m pytest -q` 1469 passed, 1 skipped; black and mypy clean; vitest 265 passed.

## Review

2026-11-22, in-session. **Verdict: clean (minors only).**

- Minor: any change to a template (even a style) redraws every box once when it is next opened; on a large box that takes as long as a redraw after naming someone.

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: chattr.pages.templates_fingerprint() hashes Chattr's templates folder; Caixa's _publish records it in box.yaml (Box.pages / mark_pages). Opening a box (not read-only, layout current) with a Chattr store and a different fingerprint enqueues one refresh job; its drawing records the new fingerprint, so the next opening starts nothing. RED (import error), then GREEN; full verify: pytest 1469 passed, vitest 265 passed.
