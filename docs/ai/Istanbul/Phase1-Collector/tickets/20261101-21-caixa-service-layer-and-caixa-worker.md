---
id: 20261101-21-caixa-service-layer-and-caixa-worker
title: Caixa service layer and caixa worker
type: feature
priority: high
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: Breakdown item 21.
parent:
depends_on:
- 20261101-20-collector-contract-and-registry
subtasks: []
plan_status: done
---
## Description

The Python service layer behind the browser and the CLI.

## Acceptance criteria

- [x] stdio JSON-RPC methods for box, collectors, import, jobs, people, browse, settings
- [x] SQLite jobs table with progress notifications; inbox folder watching
- [x] `--read-only` rejects every write method
- [x] CLI uses the same layer; worker-protocol pytest suite

## Context

Phase1-Collector Tasks Breakdown item 21. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Caixa worker; F17; F21.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** one `Service` (`caixa/service.py`) holds everything the interface and the command line
can do. `caixa worker` is a thin shell around it (newline-delimited JSON-RPC 2.0 over stdio), and
`caixa import …` etc. call the same methods, so anything the browser does can be scripted.

- **Methods:** `box.create/open/status`, `collectors.list`, `import.preview/start/cancel`,
  `jobs.list/get`, `people.unresolved/link/merge/rename`, `browse.list/file`,
  `settings.get/set`, plus `files.list` (the wizard's file picker, limited to the user's folders)
  and `inbox.list`.
- **Jobs:** a SQLite table in `.caixa/jobs.sqlite` (queued, running, done, failed, cancelled,
  interrupted). One import at a time (they share Chattr's working root); a job left running by a
  crash is marked interrupted on the next start, and re-running it is safe (imports are
  idempotent). Each job's output is kept in `.caixa/logs/job-<id>.log`, so nothing a collector
  prints can reach the protocol stream. Progress is stored and sent as notifications.
- **People:** `unresolved` comes from the collectors that can tell (Chattr's handles with no
  person). `link`, `merge` and `rename` change the master's people and aliases at once, then queue a
  `refresh` job that re-resolves, re-renders the affected pages (stale ones removed) and syncs.
- **Read-only:** `--read-only` opens the master read-only, never writes the jobs table, and refuses
  every write method (`box.create`, `import.start/cancel`, `people.link/merge/rename`,
  `settings.set`) with a distinct error.
- **Safety:** `browse.*` and `files.list` refuse paths outside their roots (including `..` and
  symlinks that escape) and never show `.caixa/`.
- **Names to confirm with the maintainer:** the inbox folder (`Inbox/` at the box root), the jobs
  file (`.caixa/jobs.sqlite`), the settings keys, the extra methods `files.list`, `inbox.list`,
  `jobs.get`.

### T01: Box, settings, browsing, picker and inbox

- `caixa/settings.py` (box settings in `box.yaml`, validated against a schema), `caixa/service.py`
  (`Service`: box.create/open/status, collectors.list, settings.get/set, browse.list/file,
  files.list, inbox.list, read-only), `Box.master(read_only=True)`, `Inbox/` in new boxes.
- Tests: `tests/test_service_box.py`: each method; path escapes refused; read-only refuses writes
  and writes nothing.
- Verify: `python -m pytest -q tests/test_service_box.py`
- [x] done

### T02: Jobs and imports

- `caixa/jobs.py` (the table), the runner thread, `import.preview/start/cancel`, `jobs.list/get`,
  progress listeners, job logs, interrupted marking.
- Tests: `tests/test_service_jobs.py`: a job runs to done with progress stored; cancel (queued and
  running); a failure is recorded with a plain message; restart marks running jobs interrupted;
  option errors are listed; the CLI-less wait; the log holds the collector's chatter.
- Verify: `python -m pytest -q tests/test_service_jobs.py`
- [x] done

### T03: People

- `Master.rename_person/merge_people`, the optional `PeopleAware` capability on collectors,
  Chattr's `unresolved` and `refresh` (stale pages removed), `people.*` on the service.
- Tests: `tests/test_service_people.py`: unresolved lists the busiest handle first; linking moves
  the pages under the person and the change log records it; rename moves the pages; merge combines
  two people; conflicts are explained; owner can't be merged away.
- Verify: `python -m pytest -q tests/test_service_people.py`
- [x] done

### T04: The worker

- `caixa/worker.py`: JSON-RPC 2.0 over stdio (one JSON object per line), requests handled
  concurrently, `job.progress` / `job.finished` / `inbox.changed` notifications, stdout kept for
  the protocol (everything else goes to stderr), `--read-only`.
- Tests: `tests/test_worker_protocol.py` drives a real `caixa worker` subprocess: every method, an
  import with progress notifications, error codes, `--read-only`, malformed input.
- Verify: `python -m pytest -q tests/test_worker_protocol.py`
- [x] done

### T05: The command line on the same layer

- `caixa box create|status`, `caixa collectors`, `caixa import <collector> <source>` (`--preview`,
  `--option k=v`, `--json`), `caixa jobs`, `caixa people unresolved|link|merge|rename`,
  `caixa worker [--box] [--read-only]`.
- Tests: `tests/test_cli.py`: a CLI import gives the same rows and files as the worker's.
- Verify: `python -m pytest -q`
- [x] done

## Completion report

- **Outcome:** One `Service` holds everything the interface and the command line can do; `caixa
  worker` serves it as JSON-RPC 2.0 over stdio (box, collectors, import, jobs, people, browse,
  settings, plus `files.list`, `inbox.list`, `jobs.get`, `people.list`) with `job.progress`,
  `job.finished` and `inbox.changed` notifications. Imports are jobs in `.caixa/jobs.sqlite`, one
  at a time, with per-job logs; people changes queue a refresh job that moves the pages with the
  person. `--read-only` refuses every write method and writes nothing. `caixa box|collectors|
  import|jobs|people|worker` call the same layer, and a CLI import gives the same rows and files as
  the service.
- **Files:** `caixa/{service,worker,jobs,settings,cli,box,master}.py`,
  `caixa/collectors/{base,chattr,messages,options}.py`, `README.md`,
  `tests/test_service_{box,jobs,people}.py`, `tests/test_worker_protocol.py`,
  `tests/test_cli_commands.py`.
- **Errors:** two of my own test expectations (the renamed person's trailing dot is dropped by
  Chattr's folder names; a mail import prints nothing for the log test) were corrected; the
  `--box` progress printed nowhere because a running job redirects `sys.stderr` to its log (the
  command line now keeps the real stream); mypy flagged a reused name.
- **Verify:** `python -m pytest -q` 831 passed; `black --check .` and `mypy caixa
  tools/chattr/src` clean; the worker suite drives a real subprocess (including `--read-only` and
  malformed input) and the fixture fails if any line other than JSON-RPC reaches stdout.

## Review

Reviewed in-session. Findings, accepted: cancelling a running import takes effect at its next
progress step, so it can't interrupt a single long parse or the final sync; the read-only master
connection can create SQLite's `-wal`/`-shm` coordination files (no data) and cannot open a box on
read-only media in WAL mode, which heir mode will need to revisit; the file picker is limited to
the home folder by default (`--root` adds more); settings are stored and shown but only the
Settings page reads them (the privacy default is not applied to new items yet). No blockers.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01–T05 done. NEEDS MAINTAINER CONFIRMATION: the inbox folder is `Inbox/` at the box root (the Requirements left its name open); jobs live in `.caixa/jobs.sqlite` beside the master; settings keys (`privacy.default`, `translation.enabled|endpoint|model`, `speech.model|language`); extra methods `files.list`, `inbox.list`, `jobs.get`, `people.list`; the worker's error code -32000 with `data.kind` (`read_only`, `not_found`, `input`, `conflict`, `no_box`, `outside_roots`, `invalid_params`, `busy`); `CAIXA_BOX` as the environment variable naming the box. Known gap: the `privacy.default` setting is stored but not yet applied when items are first imported.
