---
id: 20261117-05-remove-the-deepseek-plugin-rename-harness-to-web
title: Remove the DeepSeek plugin, rename harness to web, box pages in their own window
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

Free Caixa from DeepSeek Harness: remove the plugin and the Node code that only it needed, rename `harness/` to `web/`, take out the scrollbar workarounds its centre column needed, and open the box's pages (the index with its authoring tools, and everyone's page) in a window of their own instead of the small frame in Browse.

## Acceptance criteria

- [x] No DeepSeek package, plugin host, plugin build or plugin test remains; `web/package.json` lists none
- [x] `harness/` is now `web/`, and every reference follows
- [x] Caixa's window and the index page scroll as one page: no inner scroll area; on the index the categories stay at the left and the footer at the bottom (sticky)
- [x] Browse opens the index page, and any page of the box, in one reused window named caixa-box, at /box/<path>; nothing is squeezed into a frame
- [x] Plain text still previews in a frame where nothing runs
- [x] The old /api/caixa/box address is gone

## Context

Maintainer, 2026-11-17: "remove the DeepSeek plugin and rename harness to web. OK to remove node related code ... Remove the scrollbar hacks ... spawn this into its own window when the user opens the box contents". Node.js stays a development tool only (building the window and its tests).

## Subtasks

- [x] Delete src/host, the plugin entry and icon, its build (build.mjs, preset), cordis.patch.yml and its tests; drop @deepseek-ai packages and the build-date stamp; regenerate the lockfile
- [x] Rename harness/ to web/; update tests, Python tests, README, Collector guide, Requirements amendment, web/README
- [x] Index template: the window scrolls as a whole, sticky sidebar and footer; Caixa page: no scroll area of its own
- [x] Browse: pages open in the caixa-box window, with a note and a Show it again button; text in a script-less frame
- [x] Chattr tests check each page carries its script template unchanged; Caixa's test checks the policy hashes are those of the templates
- [x] Browser tests follow the box window

## Implementation plan

Status: done
Current task:

### T01: Delete src/host, the plugin entry and icon, its build (build.mjs, preset), cordis.patch.yml and its tests; drop @deepseek-ai packages and the build-date stamp; regenerate the lockfile
### T02: Rename harness/ to web/; update tests, Python tests, README, Collector guide, Requirements amendment, web/README
### T03: Index template: the window scrolls as a whole, sticky sidebar and footer; Caixa page: no scroll area of its own
### T04: Browse: pages open in the caixa-box window, with a note and a Show it again button; text in a script-less frame
### T05: Chattr tests check each page carries its script template unchanged; Caixa's test checks the policy hashes are those of the templates
### T06: Browser tests follow the box window

## Completion report

- **Outcome:** Caixa has nothing of DeepSeek left; the index page has the whole window for sorting, naming and removing.
- **Files:** web/ (was harness/), caixa/web.py, caixa/worker.py, caixa/state.py, tools/chattr/src/chattr/templates/{index.html,index.js}, tools/chattr/tests/test_render_pages.py, tests/test_web_server.py, README.md, docs/Documentation/Collector.md, docs/ai/Istanbul/Phase1-Collector/(2026-11-01) Phase1-Collector Requirements.md
- **Errors:** One run of the categories browser test clicked a person's page while the redraw started by a removal was rewriting it; the test now waits for the redraw.
- **Verify:** python -m pytest -q; black; mypy; vitest run (225 passed, all end-to-end tests against `caixa serve`); tsc clean

## Review

Clean. A browser that blocks pop-ups is told so on the Browse page, with a button to try again.

## Notes

- NEEDS MAINTAINER CONFIRMATION: one reused window (named caixa-box) for every box page opened from Caixa, rather than a new window each time.
