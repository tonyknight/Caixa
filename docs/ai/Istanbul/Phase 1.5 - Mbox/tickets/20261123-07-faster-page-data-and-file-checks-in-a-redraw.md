---
id: 20261123-07-faster-page-data-and-file-checks-in-a-redraw
title: Faster page data and file checks in a redraw
type: chore
priority: medium
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Redraw 12.8 → 7.4 s on the synthetic box
parent:
depends_on: []
subtasks: []
---
## Description

A redraw (after any change on the people page) took 12.8 s on a synthetic box of 3,000 mails
with a picture each: filing 3.4 s, pages 9.2 s. About a third of the pages' time was escaping each
page's data island one character at a time; about 60% of filing was resolving every stored path
(`Path.resolve`, `is_relative_to`). The maintainer asked for these to be made fast.

## Acceptance criteria

- [x] The data island is escaped exactly as before, in one pass (`str.translate`).
- [x] A stored path is found under its root exactly as before (a symlink or `..` leading out is
      refused), each folder resolved once per run.
- [x] The redraw of the synthetic box is measurably faster.

## Context

- `tools/chattr/src/chattr/pages.py` (`island_json`, `_Site._file`)
- `tools/chattr/src/chattr/filing.py` (`_locate`), `tools/chattr/src/chattr/blobs.py` (`Finder`)

## Subtasks

- [x] T01 One-pass escaping; a folder-caching finder for stored paths.

## Implementation plan

Status: done
Current task: T01

### T01: Escape once, resolve folders once

- `island_json`: `text.translate(_ISLAND_TABLE)`.
- `blobs.Finder.find(storage_path, roots)`: join, resolve the folder once (cached), resolve the
  name only if it is a link, keep it only if it is a file inside the root (string prefix on the
  resolved root). Used by `filing._locate` (one finder per run) and `pages._Site._file`.
- Tests: `tools/chattr/tests/test_fast_paths.py` (the escaping against the old one on awkward
  text; the finder on a file, a missing file, `..`, a symlink out, a symlinked folder out).
- Verify: Chattr and Caixa suites; the benchmark before and after.

## Completion report

- **Outcome:** The synthetic redraw (3,000 mails, a picture each) fell from 12.8 s to 7.4 s:
  filing 3.4 → 1.5 s, pages 9.2 → 5.7 s. Same pages, same files.
- **Files:** `tools/chattr/src/chattr/blobs.py` (`Finder`), `pages.py` (`island_json`, `_file`,
  `_link`), `filing.py` (`_locate`, `_inside`); `tools/chattr/tests/test_fast_paths.py` (new).
- **Errors:** None. `relative_to` in filing was also replaced by a string version (small gain).
- **Verify:** Chattr 905 passed; Caixa 1519 passed, 1 skipped. The finder's answers match the old
  check for a file, a missing file, `..`, a link out, a folder link out and a link inside.

### Review

Clean. A finder lives for one run: folders moved meanwhile are not seen again (none are, within
one run, other than the ones filing creates, which resolve on first use).

## Notes

Append-only running log. Each entry dated.
