---
id: 20261101-27-chattr-serve-web-ui
title: chattr-cli serve web UI
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: Breakdown item 27.
parent:
depends_on:
- 20261101-06-interactive-menu-and-command-line
- 20261101-15-html-rendering-from-the-database
subtasks: []
plan_status: done
---
## Description

Chattr's small Python-only browser UI for standalone users.

## Acceptance criteria

- [x] Jinja2 + htmx; service, export, options, run with progress, open output
- [x] Works without Caixa, Node or DeepSeek Harness

## Context

Phase1-Collector Tasks Breakdown item 27. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Chattr's own web UI; F22.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

### T03: `chattr-cli serve`, packaging and documentation

- The subcommand (`--port`, `--no-browser`), package data (templates, static), Chattr's README and
  NOTICE (htmx), and the "works without Caixa, Node or DeepSeek Harness" check.
- Tests: the real command in a subprocess; `chattr.web` imports nothing from Caixa.
- Verify: `python -m pytest -q`
- [x] done

## Completion report

- **Outcome:** `chattr-cli serve` opens a small local web page (standard-library HTTP server, Jinja2,
  vendored htmx): choose a service, read how to export, point at the export (with a folder browser),
  set options seeded from the settings, convert with live progress, open the pages. The form becomes
  the arguments `chattr-cli convert` takes and runs through `chattr.cli.main`, so the page and the
  command line give the same archive. It listens on 127.0.0.1 only, behind a token cookie with Host
  and Origin checks; `/output/` and the browser are confined to their folders. It imports nothing
  from Caixa and loads nothing from the network.
- **Files:** `tools/chattr/src/chattr/{web,cli}.py`, `templates/web/*.html`, `static/htmx.min.js`
  and its license, `pyproject.toml` (package data), `README.md`, `NOTICE`,
  `tests/{test_web,test_web_convert,test_serve_command,web_helpers}.py`.
- **Errors:** a refused POST left its body unread and the next request on the connection failed
  ("bad request syntax"); the body is now always read (regression test added). The wheel could not
  be built here (the system setuptools is patched and breaks `pip wheel`), so packaging is checked by
  matching `package-data` globs against the files instead. A subprocess test lost the user-site
  packages when HOME was isolated; `PYTHONUSERBASE` fixes that.
- **Verify:** `python -m pytest -q` 873 passed; black and mypy clean.

## Review

Reviewed in-session. Accepted: no real browser was driven here (htmx behaviour is verified at the
HTTP level: the fragments poll and stop); jobs are kept in memory for the session; progress is the
command's printed output, not a percentage; the Chattr README's feature table was refreshed (it
had been stale since ticket 15) and says what was tested. No blockers.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01-T03 done. NEEDS MAINTAINER CONFIRMATION: subcommand `serve` with `--port` (default: any free port) and `--no-browser`; cookie name `chattr_session`; no `--host` option on purpose (loopback only).
