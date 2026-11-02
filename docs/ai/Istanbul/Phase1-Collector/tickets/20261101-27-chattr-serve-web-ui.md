---
id: 20261101-27-chattr-serve-web-ui
title: chattr-cli serve web UI
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 27.
parent:
depends_on:
- 20261101-06-interactive-menu-and-command-line
- 20261101-15-html-rendering-from-the-database
subtasks: []
current_task: T02
plan_status: in-progress
---
## Description

Chattr's small Python-only browser UI for standalone users.

## Acceptance criteria

- [ ] Jinja2 + htmx; service, export, options, run with progress, open output
- [ ] Works without Caixa, Node or DeepSeek Harness

## Context

Phase1-Collector Tasks Breakdown item 27. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Chattr's own web UI; F22.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** `chattr-cli serve` is a small local web page for people who only want Chattr. It is
Python only (the standard library's HTTP server, Jinja2 for pages, htmx for the few live parts) and
imports nothing from Caixa. The steps are the CLI's: choose a service, point at the export, set
options, run with progress, open the output.

- **One code path:** the form is turned into the same arguments `chattr-cli convert` takes and run
  through `chattr.cli.main`, so the web page and the command line cannot drift apart and report the
  same plain messages. Its output is captured into the job's progress panel.
- **Safe on a shared computer:** it listens on `127.0.0.1` only; the link `serve` prints carries a
  random token that becomes an `HttpOnly`, `SameSite=Strict` cookie; every other request needs that
  cookie, a `Host` of the local address (against DNS rebinding) and, for a POST, a same-origin
  `Origin`. The folder browser is limited to the home folder and the Chattr folder; `/output/` serves
  only files inside `Output/`.
- **Offline:** htmx (0BSD) is vendored in the package; no page loads anything from the network.
- **Names to confirm with the maintainer:** the subcommand `serve` and its flags (`--port`,
  `--no-browser`; the default port is any free one), the cookie name `chattr_session`.

### T01: The server, its safety rules and the pages

- `src/chattr/web.py`, `templates/web/*.html`, vendored `static/htmx.min.js`: token cookie, Host and
  Origin checks, the service chooser, one options form per service (defaults from the settings and
  `Services/*.json`), the folder browser, `/output/` serving, quiet logging.
- Tests: `tests/test_web.py`: the safety rules, every service's form, the browser's limits, output
  confinement, nothing loaded from the network.
- Verify: `python -m pytest -q tools/chattr/tests/test_web.py`
- [x] done

### T02: Convert with progress

- Form → `chattr-cli convert` arguments; a one-at-a-time job runner capturing output; the job page
  that polls its status with htmx and stops when finished; "open the pages"; "make the web pages"
  for an archive converted without them.
- Tests: converting each kind through the page matches the CLI; options reach the command; failures
  are explained in plain words; the JSON route; the progress fragment stops polling when done.
- Verify: `python -m pytest -q tools/chattr/tests/test_web.py`
- [ ] done

### T03: `chattr-cli serve`, packaging and documentation

- The subcommand (`--port`, `--no-browser`), package data (templates, static), Chattr's README and
  NOTICE (htmx), and the "works without Caixa, Node or DeepSeek Harness" check.
- Tests: the real command in a subprocess; `chattr.web` imports nothing from Caixa.
- Verify: `python -m pytest -q`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
