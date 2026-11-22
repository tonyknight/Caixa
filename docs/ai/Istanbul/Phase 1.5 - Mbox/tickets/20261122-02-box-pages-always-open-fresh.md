---
id: 20261122-02-box-pages-always-open-fresh
title: Box pages always open fresh
type: bug
priority: high
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: box pages open with a fresh address every time.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

After the pages were redrawn, the maintainer's index page still showed its old drawing until a hard refresh: Caixa reuses one window for the box's pages, and opening a page into it again could show the copy the browser already had.

## Acceptance criteria

- [x] Each time Caixa opens a box page in the box window, the address carries a query no earlier opening used, so the browser fetches the page again
- [x] The page works as before with it: the index page's script still knows it is in Caixa, and relative links still resolve

## Context

Found by the maintainer after `20261122-01`. `web/src/client/pages/BrowsePage.tsx` (`openBoxWindow`); the server already ignores a query on `/box/` addresses. Requirements: *Hot fixes*, M20.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `openBoxWindow` adds `?fresh=<a number that grows with each opening>` to the page's
address. Caixa's server reads only the path of a `/box/` address (and still sends `no-store`), the
index script tests the path, and a query does not change how relative links resolve, so nothing
else changes.

### T01: A fresh address for each opening

- `web/src/client/pages/BrowsePage.tsx`, the built window.
- Tests (`web/tests/browse-page.test.tsx`): two openings of the index use two different addresses,
  both `/box/index.html?fresh=…`; end to end (`web/tests/e2e-browse.test.ts`), the box window's
  address has the query and the page works (its path is `/box/index.html`).
- Verify: `cd web && pnpm exec vitest run tests/browse-page.test.tsx tests/e2e-browse.test.ts tests/e2e-categories.test.ts && pnpm exec tsc --noEmit`
- [x] done

## Completion report

- **Outcome:** Every box page Caixa opens in its box window (the index page included) has an address no earlier opening used, so the browser always fetches the page as it is now.
- **Files:** `web/src/client/pages/BrowsePage.tsx`, `caixa/data/web/*`; tests `web/tests/{browse-page.test.tsx,e2e-browse.test.ts}`.
- **Errors:** none.
- **Verify:** web `tsc` clean, vitest (whole suite) passed; `tests/test_web_server.py` passed.

## Review

2026-11-22, in-session. **Verdict: clean (minors only).**

- Minor: links followed inside the box window (from the index to a person's page) use the pages' own relative addresses; those pages are sent with `no-store`, and a page reopened from Caixa is fresh.

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: openBoxWindow adds ?fresh=<ms×1000 + a counter> to every box page it opens in the reused box window; the server reads only the path, the index script tests the path. RED: 2 browse tests, then GREEN; the e2e checks the window's address has the query and the page works. Window rebuilt.
