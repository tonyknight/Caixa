---
id: 20261117-04-collector-service-separate-from-the-deepseek
title: Collector service separate from the DeepSeek harness
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

Move the collector out of DeepSeek Harness into a service of its own, served with Python, in the Nord theme, able to open the authoring view. `caixa serve` runs the service layer and a small web server in one process; the existing React pages are kept, mounted on a page of their own and built into the Python package so running Caixa needs no Node.js. Recorded as an amendment in the Phase 1 Requirements.

## Acceptance criteria

- [x] `caixa serve` starts one Python process on 127.0.0.1 and opens a sign-in link; nothing answers without the session cookie
- [x] Host header checked (DNS rebinding); POSTs must be JSON and, when they say where from, from this window
- [x] The same /api/caixa/rpc, /events and /status contract as before, so the pages work unchanged
- [x] The box's pages served at /box/<path> under the pages' Content-Security-Policy, with Range for media; .caixa and anything outside the box refused; /api/caixa/box?path= redirects
- [x] Caixa's window: title Caixa, Nord colours, no DeepSeek name, strict CSP (no inline scripts or styles)
- [x] The built window is committed in caixa/data/web; a Python test fails if sources change without a rebuild
- [x] `caixa serve` run again opens the running window; `--stop` and Control-C stop it
- [x] Every end-to-end browser test runs against the real `caixa serve`

## Context

Maintainer, 2026-11-17: DeepSeek Harness is a poor authoring harness; separate service, Python is fine, Nord theme; three modes (collection/authoring now, presentation and static later). Agreed order: this after the close box, preference file and deletion flows.

## Subtasks

- [x] caixa/web.py: sign-in, cookie, Host/Origin checks, rpc, events, status, box files, app files
- [x] caixa/serve.py rewritten around it; DeepSeek install pin (caixa/data/dsh) removed; diagnostics updated
- [x] src/app (entry, translator, Nord stylesheet) and scripts/build-app.mjs into caixa/data/web
- [x] Index page recognises Caixa's own window; script hashes computed by the server from Chattr's templates
- [x] End-to-end tests moved to `caixa serve`; Python tests for the server and the launcher
- [x] Store keeps the newest job list when answers return out of order
- [x] README, harness/README and the Requirements amendment

## Implementation plan

Status: done
Current task:

### T01: caixa/web.py: sign-in, cookie, Host/Origin checks, rpc, events, status, box files, app files
### T02: caixa/serve.py rewritten around it; DeepSeek install pin (caixa/data/dsh) removed; diagnostics updated
### T03: src/app (entry, translator, Nord stylesheet) and scripts/build-app.mjs into caixa/data/web
### T04: Index page recognises Caixa's own window; script hashes computed by the server from Chattr's templates
### T05: End-to-end tests moved to `caixa serve`; Python tests for the server and the launcher
### T06: Store keeps the newest job list when answers return out of order
### T07: README, harness/README and the Requirements amendment

## Completion report

- **Outcome:** Caixa runs as its own window; all 279 browser and unit tests and the Python suite pass against it.
- **Files:** caixa/web.py, caixa/serve.py, caixa/cli.py, caixa/diagnostics.py, caixa/data/web/*, harness/src/app/*, harness/scripts/build-app.mjs, harness/src/client/{caixa.module.css,store.ts,pages/SettingsPage.tsx}, harness/tests/*, tests/test_web_server.py, tests/test_serve.py, tools/chattr/src/chattr/templates/index.js, README.md, harness/README.md, docs/ai/Istanbul/Phase1-Collector/(2026-11-01) Phase1-Collector Requirements.md
- **Errors:** A refusal that left a request body unread spoiled the next request on the same connection (body now read first). Script hashes were off by the newline Jinja drops. Overlapping job-list refreshes answered out of order and an older answer hid the Undone mark (only the newest now counts). My first test file name clashed with Chattr's test_web.py.
- **Verify:** python -m pytest -q; black; mypy; vitest run (279 passed, including every end-to-end test against `caixa serve`); tsc clean

## Review

Clean. The sign-in link stays valid while Caixa runs (it is kept 0600 in Caixa's folder so `caixa serve` run again can open the window).

## Notes

- NEEDS MAINTAINER CONFIRMATION: remove the DeepSeek Harness plugin (harness/src/host, src/client/index.tsx, its build and tests) now that nothing starts it, and rename `harness/` (for example to `web/`).
- NEEDS MAINTAINER CONFIRMATION: the built window (about 250 KB) is committed in caixa/data/web so running Caixa needs no Node.js.
- NEEDS MAINTAINER CONFIRMATION: the sign-in link is reusable until Caixa stops (not one-time), so a second browser or `caixa serve` run again can open the window.
- NEEDS MAINTAINER CONFIRMATION: box pages are served at /box/<path>; any free port by default (`--port` 1024–65535).
