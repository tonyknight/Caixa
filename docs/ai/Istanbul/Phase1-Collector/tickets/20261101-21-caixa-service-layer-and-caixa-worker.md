---
id: 20261101-21-caixa-service-layer-and-caixa-worker
title: Caixa service layer and caixa worker
type: feature
priority: high
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 21.
parent:
depends_on:
- 20261101-20-collector-contract-and-registry
subtasks: []
current_task: T02
plan_status: in-progress
---
## Description

The Python service layer behind the browser and the CLI.

## Acceptance criteria

- [ ] stdio JSON-RPC methods for box, collectors, import, jobs, people, browse, settings
- [ ] SQLite jobs table with progress notifications; inbox folder watching
- [ ] `--read-only` rejects every write method
- [ ] CLI uses the same layer; worker-protocol pytest suite

## Context

Phase1-Collector Tasks Breakdown item 21. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Caixa worker; F17; F21.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

### T03: People

- `Master.rename_person/merge_people`, the optional `PeopleAware` capability on collectors,
  Chattr's `unresolved` and `refresh` (stale pages removed), `people.*` on the service.
- Tests: `tests/test_service_people.py`: unresolved lists the busiest handle first; linking moves
  the pages under the person and the change log records it; rename moves the pages; merge combines
  two people; conflicts are explained; owner can't be merged away.
- Verify: `python -m pytest -q tests/test_service_people.py`
- [ ] done

### T04: The worker

- `caixa/worker.py`: JSON-RPC 2.0 over stdio (one JSON object per line), requests handled
  concurrently, `job.progress` / `job.finished` / `inbox.changed` notifications, stdout kept for
  the protocol (everything else goes to stderr), `--read-only`.
- Tests: `tests/test_worker_protocol.py` drives a real `caixa worker` subprocess: every method, an
  import with progress notifications, error codes, `--read-only`, malformed input.
- Verify: `python -m pytest -q tests/test_worker_protocol.py`
- [ ] done

### T05: The command line on the same layer

- `caixa box create|status`, `caixa collectors`, `caixa import <collector> <source>` (`--preview`,
  `--option k=v`, `--json`), `caixa jobs`, `caixa people unresolved|link|merge|rename`,
  `caixa worker [--box] [--read-only]`.
- Tests: `tests/test_cli.py`: a CLI import gives the same rows and files as the worker's.
- Verify: `python -m pytest -q`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
