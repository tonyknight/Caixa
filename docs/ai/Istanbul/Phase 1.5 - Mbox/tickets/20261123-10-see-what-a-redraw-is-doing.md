---
id: 20261123-10-see-what-a-redraw-is-doing
title: See what a redraw is doing
type: feature
priority: medium
status: done
created: 2026-11-23
updated: 2026-11-23
closed: 2026-11-23
notes: Workers in Settings; each redraw step logs what it did, workers, time
parent:
depends_on: []
subtasks: []
---
## Description

With 48,000 pages, sorting one person was painfully slow and the maintainer could not tell why:
the terminal said which step a redraw was in, not how many workers it used, how much it did or how
long it took. The Workers setting was also missing from Settings (it has no group in its name, and
the page showed only grouped settings).

## Acceptance criteria

- [x] Settings shows Workers (under Performance) and saves it.
- [x] Each step of a redraw ends with a line saying what it did and how long it took: people
      matched; files checked, new and moved; pages written and unchanged, with the workers used;
      the box updated. Those lines always reach the terminal.

## Context

- `web/src/client/pages/SettingsPage.tsx`; `caixa/service.py` (`_Terminal`),
  `caixa/collectors/base.py` (`Progress`), `caixa/collectors/chattr.py` (`refresh`, `_publish`),
  `tools/chattr/src/chattr/pages.py` (`render_pages`), `commands.py` (`publish`)

## Subtasks

- [x] T01 Workers in Settings; a closing line for each step.

## Implementation plan

Status: done
Current task: T01

### T01: Workers in Settings; closing lines

- Settings: a Performance group for settings with no group in their name.
- `Progress.summary`: a step's closing line; `_Terminal` always prints it.
- `render_pages(..., stats)`: pages, written, unchanged, workers used, seconds; `Published.drawn`.
- `refresh`/`_publish`: time each step; closing lines "People matched · 0.3 s", "31,117 files:
  3 new, 12 moved · 41 s", "48,012 pages: 3 written, 48,009 unchanged · 4 workers · 85 s",
  "Box updated · 2 s".
- Tests: web (Workers shown and saved); `tests/test_redraw_log.py` (a redraw's terminal lines).
- Verify: web, Chattr, Caixa suites.

## Completion report

- **Outcome:** Workers is in Settings, under Performance. A redraw's terminal lines now end each
  step with what it did and how long it took, e.g. "linking - People matched · 0.3 s",
  "filing 31,117/31,117 - 31,117 files: 3 new, 12 moved · 41 s", "rendering 48,012/48,012 -
  48,012 pages: 3 written, 48,009 unchanged · 4 workers · 85 s", "syncing - Box updated · 2 s";
  while the pages are written the line names the workers.
- **Files:** `web/src/client/pages/SettingsPage.tsx`, `locales.ts`, built `caixa/data/web/`;
  `caixa/collectors/base.py` (`Progress.summary`), `caixa/service.py` (`_Terminal`),
  `caixa/collectors/chattr.py` (`refresh`, `_publish`, `_took`, `_workers`),
  `tools/chattr/src/chattr/pages.py` (`stats`), `commands.py` (`Published.drawn`, `on_filed`);
  tests `web/tests/settings-page.test.tsx`, `web/tests/fake-api.ts`, `tests/test_redraw_log.py`.
- **Errors:** Two Settings tests expected probes without `workers`; the fake settings now carry it
  as the real ones do.
- **Verify:** Web 277 passed; Chattr 912; Caixa 1528, 1 skipped.

### Review

Clean.

## Notes

Append-only running log. Each entry dated.
