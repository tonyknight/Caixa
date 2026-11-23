---
id: 20261123-09-only-changed-pages-are-rewritten
title: Only changed pages are rewritten
type: chore
priority: medium
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Unchanged pages are not written again (redraw ~2 s when little changed)
parent:
depends_on: []
subtasks: []
---
## Description

Every redraw drew every page again, though sorting or merging a few people changes few of them.
The maintainer asked that only pages whose content changed be rewritten.

## Acceptance criteria

- [x] A page is drawn from its template and the data given to it; when both are as they were
      the last time it was written, and the file is still as written then (same size and time),
      it is left alone: not drawn, not written.
- [x] A changed page, one missing or changed on disk, or every page after the templates change, is
      written again; the pages are the same as a full redraw would write.
- [x] Works with workers too; the index is always written.

## Context

- `tools/chattr/src/chattr/pages.py` (`_draw`, the page functions' `render` calls,
  `render_pages`), `caixa/reset.py` (the files a reset removes)

## Subtasks

- [x] T01 Skip unchanged pages.

## Implementation plan

Status: done
Current task: T01

### T01: Skip unchanged pages

- `_Site.draw(template, **context)` instead of `env.get_template(...).render(...)` in the three
  page functions: the fingerprint is the SHA-256 of the templates' fingerprint, the template name
  and the context as JSON (sets sorted, anything else as text); when it and the file's size and
  modification time match what was recorded, `_Unchanged` is raised and `_draw` leaves the file.
- What was recorded: `<pages list>.fingerprints.json` beside the pages list
  (`.caixa/pages.fingerprints.json` for a box): `{path: [fingerprint, size, mtime_ns]}`; written
  after each run; workers get their share's records and return theirs. Removed by a reset.
- Tests: `tools/chattr/tests/test_render_unchanged.py` (a second run rewrites nothing but the
  index and leaves the same bytes; one changed message rewrites its page only; a deleted or
  edited page is rewritten; new templates rewrite all; the same with workers).
- Verify: Chattr, Caixa and web suites; the benchmark's second redraw.

## Completion report

- **Outcome:** A redraw writes only the pages whose data or templates changed (or whose file was
  touched). Synthetic box: a redraw with nothing changed 2.2 s, after renaming one person 2.2–2.5 s,
  against 12.8 s before tickets 07–09.
- **Files:** `tools/chattr/src/chattr/pages.py` (`_Site.draw`, `_Unchanged`, `_plain`, `_draw`,
  `_known`, `_keep_known`, workers carry the records), `caixa/reset.py` (removes
  `pages.fingerprints.json`); `tools/chattr/tests/test_render_unchanged.py` (new); Requirements.
- **Errors:** The first version kept the records beside Chattr's own default list, in the output
  folder, where they showed among the output files (40 tests): records are kept only beside a
  list given apart from the pages, as Caixa gives it.
- **Verify:** Chattr 912 passed; Caixa 1526 passed, 1 skipped; web 276 passed.

### Review

Clean. Exact by construction: a page's HTML is its template applied to its data; both are in the
fingerprint, and the file must be as written. Minor: building each page's data still runs for
every page (about 1.4 s on the synthetic box); only drawing and writing are skipped.

## Notes

Append-only running log. Each entry dated.
