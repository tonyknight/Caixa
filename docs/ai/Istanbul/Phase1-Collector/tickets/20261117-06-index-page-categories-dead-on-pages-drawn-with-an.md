---
id: 20261117-06-index-page-categories-dead-on-pages-drawn-with-an
title: Index page categories dead on pages drawn with an older script
type: bug
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

Maintainer, 2026-11-17: opening the box's page, none of the category links work; Groups seems to. The index script was not running at all (Groups only scrolled to its section, which shows when no script runs). The box's pages are drawn at import, and the index script had changed since; Caixa's Content-Security-Policy lists only the current scripts' hashes, so the browser refused the older copy in the page.

## Acceptance criteria

- [x] A page drawn with an older version of Caixa's index or lightbox script is served with the current one, so it runs
- [x] Only a script that begins as one of Caixa's does is replaced; any other script, and message text, is sent unchanged
- [x] Only the end of a page is held in memory; Content-Length matches what is sent
- [x] No redraw of the box is needed

## Context

Follows 20261117-05, which changed index.js after the maintainer's pages were drawn. Any future change to the scripts would have caused the same.

## Subtasks

- [x] Reproduce: a test serving an index page with an older script
- [x] caixa/web.py: page scripts recognised by how they begin; the end of each served page has them replaced by the current text

## Implementation plan

Status: done
Current task:

### T01: Reproduce: a test serving an index page with an older script
### T02: caixa/web.py: page scripts recognised by how they begin; the end of each served page has them replaced by the current text

## Completion report

- **Outcome:** Index pages drawn by any earlier version work again in Caixa without being redrawn.
- **Files:** caixa/web.py, tests/test_web_server.py
- **Errors:** none
- **Verify:** python -m pytest -q (1281 passed); vitest run (225 passed); black; mypy

## Review

Clean. Messages cannot inject a script: all message text is escaped, and only <script> elements whose text starts as Caixa's own are touched.

## Notes


