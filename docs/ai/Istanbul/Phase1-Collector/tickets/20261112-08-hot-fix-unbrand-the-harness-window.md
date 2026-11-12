---
id: 20261112-08-hot-fix-unbrand-the-harness-window
title: 'Hot fix: unbrand the harness window'
type: feature
priority: medium
status: done
created: 2026-11-12
updated: 2026-11-12
closed: 2026-11-12
notes: ''
parent:
depends_on: []
subtasks: []
---
## Description

Caixa runs inside DeepSeek Harness. The window carried the harness's name and mark, opened on its chat screen, and listed its Plugins and Automation pages. The maintainer asked for the harness to be unbranded as part of this hot fix.

## Acceptance criteria

- [x] Started by `caixa serve`, the window is called Caixa: the sidebar's brand, and the browser tab's title (tested in the real harness).
- [x] It opens on the Caixa page with nothing to click first.
- [x] The harness's Plugins and Automation tasks entries are gone; no DeepSeek notice, sign-in prompt, name or mark is shown on the first screen.
- [x] Inside someone's own harness (not started by `caixa serve`) Caixa stays a guest: one more panel, nothing renamed.

## Context

`caixa serve` writes `shell: true` into the plugin's configuration; the host reports it on `/api/caixa/status` and the browser half then fills the harness's own brand slots (`sidebar.brand.mark`, `sidebar.brand.name`), rewrites the harness's name in the document title, and selects the Caixa panel through `ctx.layout`. The patch also disables `ui-plugin-manager` and `ui-schedule`. Tried and left: disabling `ui-workspace` (the Workspaces list) stops the harness loading its plugins at all, and New Session is drawn by the sidebar itself, which has no switch for it.

## Subtasks

- [x] Browser test in the real harness with the patch `caixa serve` writes (harness/tests/e2e-shell.test.ts).
- [x] `shell` in the host configuration and the status route; `isShell`, brand slots, title and first panel in the browser half.
- [x] The patch: `shell: true`, `ui-plugin-manager` and `ui-schedule` disabled.
- [x] README: what the window looks like now.

## Implementation plan

Status: done
Current task:

### T01: Browser test in the real harness with the patch `caixa serve` writes (harness/tests/e2e-shell.test.ts).
### T02: `shell` in the host configuration and the status route; `isShell`, brand slots, title and first panel in the browser half.
### T03: The patch: `shell: true`, `ui-plugin-manager` and `ui-schedule` disabled.
### T04: README: what the window looks like now.

## Completion report

- **Outcome:** The window is Caixa's: name, mark, title and first page. Two harness controls remain.
- **Files:** caixa/serve.py, harness/src/host/{index,routes}.ts, harness/src/client/{index.tsx,api.ts}, harness/tests/{e2e-shell,host,build}.test.ts, tests/test_serve.py, tests/test_serve_real.py, README.md
- **Errors:** none
- **Verify:** `python -m pytest -q` 1091 passed, 6 skipped; with Node on PATH the 6 real-launcher tests pass; harness 257 passed; black, mypy, tsc clean. Looked at a screenshot of the first screen.

## Review

Not finished, and said so: **New Session** and the **Workspaces** list (the harness's chat) are still in the left column, and clicking New Session shows the harness's own chat screen with its fish mark. Removing them needs either a harness build without those plugins or hiding them with style rules tied to the harness's internals; neither was done. NEEDS MAINTAINER DECISION: accept this for Phase 1, or spend the time on a harness profile of our own. The Models settings page stays off (it carries the sign-in prompt); Phase 2 will need a replacement to choose a local model.

## Notes

- 2026-11-12: In this test environment the harness also shows 'Unable to create default workspace' (it has no desktop folders); that is the harness's own message and may not appear on a Mac.
