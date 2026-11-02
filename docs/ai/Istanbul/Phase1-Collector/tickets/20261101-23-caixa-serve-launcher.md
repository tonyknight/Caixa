---
id: 20261101-23-caixa-serve-launcher
title: caixa serve launcher
type: feature
priority: high
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: Breakdown item 23.
parent:
depends_on:
- 20261101-22-harness-plugin-skeleton
subtasks: []
plan_status: done
---
## Description

One command that starts everything and opens the browser.

## Acceptance criteria

- [x] Node 24.9+ check with a clear message
- [x] Caixa's own DSH home; plugin installed; privacy patch disables session-log upload and telemetry
- [x] Sele's launch rules; reattach after a crash; token never logged

## Context

Phase1-Collector Tasks Breakdown item 23. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Launcher; F20; N7; N9.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa serve` is the one command: check Node, prepare Caixa's own DeepSeek Harness, start
`dsh web` safely, open the browser. Python (`caixa/serve.py`), no new dependency.

- **Node 24.9+ first**, with a plain message saying what is wrong and how to install it.
- **Caixa's own DSH home**, never `~/.dsh`: `$CAIXA_HOME/dsh-home` (per user: `~/.local/share/caixa`,
  `~/Library/Application Support/Caixa` on a Mac, `%LOCALAPPDATA%\Caixa` on Windows). The pinned
  `@deepseek-ai/dsh@0.2.2-alpha.2` is installed once into `$CAIXA_HOME/dsh`; the Caixa plugin (the
  `harness/` folder of a checkout) is added to the profile with `dsh plugin`.
- **Privacy patch** (`caixa.patch.yml`, passed with `--patch`): session-log and telemetry rows
  disabled, a local OpenAI-compatible provider placeholder, ask-before-acting permission default,
  and the plugin row configured with the box, read-only flag and this Python (`python -m caixa
  worker`). The process also gets `DSH_TELEMETRY_DISABLED=1`.
- **Launch rules:** own process group, ended as a group; `127.0.0.1` only; OS-assigned port or 3082+
  (never 3080/3081); read the link line from stdout, then check it answers; save `{pid, port, url}`
  (mode 0600) so a later `caixa serve` reattaches after a crash; the token link is never printed by
  default and is redacted from the log (`--no-browser` prints it, because that is what it is for).
- **Names to confirm with the maintainer:** the harness home location (per user, not inside the box:
  boxes may live on shared or read-only media and a harness per box would repeat a large install);
  `--stop`; `CAIXA_HOME`, `CAIXA_DSH`, `CAIXA_NODE` overrides.

### T01: Checks and preparation

- `caixa/serve.py`: Node check, home, plugin location, install of the pinned dsh, profile and plugin,
  the privacy patch.
- Tests: `tests/test_serve.py`: version parsing and messages, home locations, the patch contents, the
  pin matches `harness/package.json`.
- Verify: `python -m pytest -q tests/test_serve.py`
- [x] done

### T02: Launch, supervise, reattach

- Start `dsh web` in its own group, read the link, check readiness, save the state, redact the log,
  stop as a group, reattach, refuse mismatched options, `--stop`; `caixa serve` in the CLI.
- Tests: with a fake `dsh`: the rules above, including killing the launcher and reattaching.
- Verify: `python -m pytest -q tests/test_serve_launch.py`
- [x] done

### T03: The real thing

- `tests/test_serve_real.py`: the real pinned dsh and plugin (skipped without Node 24.9+ and an
  installed harness): the patch applies without warnings, telemetry rows are off, the plugin loads,
  routes answer, nothing is logged with the token, stop ends the whole group.
- Verify: `python -m pytest -q tests/test_serve_real.py` with Node 24 on the path.
- [x] done

## Completion report

- **Outcome:** `caixa serve [--box PATH] [--read-only] [--port N] [--no-browser] [--stop] [--node PATH]`
  checks Node 24.9+ (plain messages for missing, too old, not Node), prepares Caixa's own per-user
  DeepSeek Harness home (the pinned 0.2.2-alpha.2 installed once, the Caixa plugin added once), writes
  the privacy patch (session log and telemetry rows disabled, a local model placeholder, the plugin
  configured with box, read-only and this Python), starts `dsh web` on 127.0.0.1 in a session of its
  own, reads its link, checks it answers, saves `{pid, port, url}` (0600), opens the browser, and on
  Control-C ends the whole group. A later `caixa serve` finds a still-running harness (after the
  launcher was killed) and reattaches; different options are refused with `--stop` as the way out.
  The token is never printed (except with `--no-browser`) and is redacted from the log.
- **Files:** `caixa/serve.py`, `caixa/cli.py`, `README.md`, `tests/{test_serve,test_serve_launch,test_serve_real}.py`,
  `tests/fake_dsh.py`.
- **Errors:** running the real `dsh` found two things the fake could not: `--patch` must precede the
  profile and app options, and the sign-in link answers with a redirect and a cookie, so readiness
  follows redirects with a cookie jar. Stopping first waited out its grace period on zombie processes;
  it now ends the group once its leader is gone. The fake `dsh` now refuses `--patch` after the app
  options, as the real one does.
- **Verify:** `python -m pytest -q` (the real-harness tests run when Node 24.9+, pnpm and a built
  harness are present: they passed here with Node 24.22; the commit gate runs without Node 24 and
  skips them); black and mypy clean.

## Review

Reviewed in-session. Accepted: Windows is refused with a message (process groups differ; the
Requirements left Windows open); the pinned dsh is installed with npm into Caixa's folder on first
run (network needed once, said in the error if it fails); the plugin comes from the checkout's
`harness/` folder, so a `pipx` install of the Python package alone has no plugin to add (shipping the
built plugin inside the wheel is a packaging task this project does not include; `CAIXA_PLUGIN` names
another location); permission defaults are the harness's own ask-before-acting default, set
explicitly in the environment. No blockers.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01-T03 done. NEEDS MAINTAINER CONFIRMATION: Caixa's harness home is per user (`~/.local/share/caixa`, `~/Library/Application Support/Caixa`, `%LOCALAPPDATA%\Caixa`; `CAIXA_HOME` overrides), not inside the box (Requirements left it open; a harness per box would repeat a large install and boxes may live on shared or read-only media); flags `--stop` and `--node`; env overrides `CAIXA_HOME`, `CAIXA_NODE`, `CAIXA_DSH`, `CAIXA_PLUGIN`; the local-model placeholder (`http://localhost:11434/v1`, provider id `local`); Windows unsupported for now. Known gap: the built plugin is not yet shipped inside the Python wheel.
