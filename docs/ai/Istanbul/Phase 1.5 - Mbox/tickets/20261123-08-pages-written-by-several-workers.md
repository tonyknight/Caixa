---
id: 20261123-08-pages-written-by-several-workers
title: Pages written by several workers
type: chore
priority: medium
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Pages shared out among the box's workers (5.4 → 2.7 s with 4)
parent:
depends_on: []
subtasks: []
---
## Description

Writing the pages is the longest step of a redraw (5.7 s of 7.4 on the synthetic box, about ten
times that on the maintainer's) and ran on one core. The maintainer asked for it to use the
workers setting.

## Acceptance criteria

- [x] With several workers, each writes its share of the pages; the pages are byte for byte the
      ones one process writes. The index and the removal of old pages stay with the main process.
- [x] Few pages (under `PARALLEL_FROM`) or one worker: written as before, in the process.
- [x] If a worker fails, the pages are written in the process instead (nothing half done).
- [x] The redraw reports its progress through the pages (`rendering n/total`), for the work bar.

## Context

- `tools/chattr/src/chattr/pages.py` (`render_pages`), `commands.py` (`publish`)
- `caixa/collectors/chattr.py` (`_publish`: the box's `workers` setting, progress)

## Subtasks

- [x] T01 Workers for the pages.

## Implementation plan

Status: done
Current task: T01

### T01: Workers for the pages

- `render_pages(..., workers, database, progress, parallel_from)`: with workers > 1, a database
  and enough pages, split the pages round-robin into chunks; each chunk runs in a spawned process
  (`_draw_share`) that opens the database, builds its own `Renderer`, checks it plans the same
  pages, and writes its share; results gathered as they finish (progress). Any failure: write
  everything in the process. Index and `_forget_old_pages` after.
- `publish(..., workers, page_progress)`: commits filing first, passes the database.
- Caixa's `_publish`: `workers` from the box's settings; `Progress("rendering", n, total)`.
- Tests: `tools/chattr/tests/test_render_workers.py` (the sample archive written by one process
  and by three workers: the same files, the same bytes; a failing worker falls back; progress
  reaches the total).
- Verify: Chattr and Caixa suites; the benchmark with 1 and 4 workers.

## Completion report

- **Outcome:** With the box's workers (4 here), writing the synthetic box's 3,200 pages fell from
  5.4 s to 2.7 s (the redraw 7.0 → 4.7 s); a box ten times the size gains more, since starting the
  workers and reading the archive in each is a fixed cost. The redraw reports `rendering n/total`.
- **Files:** `tools/chattr/src/chattr/pages.py` (`_draw`, `_draw_share`, `_draw_in_workers`,
  `render_pages`), `commands.py` (`publish`), `caixa/collectors/chattr.py` (`_publish`),
  `caixa/settings.py` (the Workers setting says it covers the pages);
  `tools/chattr/tests/test_render_workers.py` (new).
- **Errors:** None.
- **Verify:** Chattr 907 passed; Caixa 1521 passed, 1 skipped. Three workers write the sample
  archive's pages byte for byte as one process does; a failing worker falls back.

### Review

Clean. Each worker checks it plans the same pages (place and path) before writing; the index and
the removal of old pages stay in the main process.

## Notes

Append-only running log. Each entry dated.
