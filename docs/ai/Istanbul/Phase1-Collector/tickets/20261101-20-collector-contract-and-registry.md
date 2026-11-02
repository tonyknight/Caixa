---
id: 20261101-20-collector-contract-and-registry
title: Collector contract and registry
type: feature
priority: high
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: Breakdown item 20.
parent:
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
- 20261101-18-caixa-master-schema-v0-and-messages-adapter
subtasks: []
current_task: T02
plan_status: in-progress
---
## Description

Let export sources register themselves so the UI needs no per-source code.

## Acceptance criteria

- [ ] `caixa.collectors` entry-point discovery
- [ ] Each collector declares inputs, 'how to export' instructions, an options JSON Schema, `preview` and `run`
- [ ] Chattr's six sources registered

## Context

Phase1-Collector Tasks Breakdown item 20. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Application — Collector contract; F16.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** a *collector* is how one kind of export enters a box. It declares what it is and what it
accepts, and can `preview` (a dry run) and `run` (the real import). The UI is built from those
declarations, so a new source needs no UI code. Collectors are found through the Python entry-point
group `caixa.collectors`; an entry point is a callable returning one collector or a list of them
(Chattr's adapter registers all six this way).

A collector declares: `id`, display `name`, `platform`, accepted `inputs` (`zip`, `folder`, `file`,
`database`), "how to export" instructions, and an options JSON Schema (seeded from Chattr's
`Defaults/Services/*.json` preferences) that the UI renders as a form. `preview(source, options)`
returns counts, date range, participants and unresolved handles without writing anything.
`run(box, source, options, progress)` imports into a **box**.

The box (`caixa/box.py`): a folder with `Messages/`, `Mail/`, `People/`, … and a hidden `.caixa/`
holding `caixa.sqlite`, `work/chattr/` (Chattr's root when Caixa runs it), `box.yaml` (written as
JSON, which is valid YAML) and `logs/`.

**Names to confirm with the maintainer:** collector ids (`imessage`, `whatsapp`, `messenger`
(Messenger and Instagram), `mail`, `googlevoice`, `voicemail`) and the input kind names.

### T01: The contract, option validation and the registry

- `caixa/collectors/base.py`: `CollectorInfo`, `Preview`, `Progress`, `RunResult`, the `Collector`
  protocol; `caixa/collectors/options.py`: defaults from a JSON Schema and validation of a useful
  subset (type, enum, minimum/maximum, required, default, unknown keys refused).
- `caixa/collectors/registry.py`: `discover()` from entry points (plus in-process `register()`),
  clear errors for a broken entry point and for duplicate ids; `get(id)`; `describe()` giving the
  JSON the UI renders.
- `caixa/box.py`: `Box.create/open`, the folder layout, `box.yaml`, `status()`.
- Tests: the schema subset, discovery with fake entry points, duplicates, a broken plugin.
- Verify: `python -m pytest -q tests/test_collector_contract.py`
- [x] done

### T02: Chattr's six collectors

- `caixa/collectors/chattr.py`: one collector per source with its inputs, "how to export" text and
  options schema (defaults read from Chattr's own); `preview` (parse only, writing nothing: counts,
  date range, participants, handles no alias names; it takes the box as an optional extra argument
  to know the aliases) and `run` (Chattr into `.caixa/work/chattr/`, people linked, pages rendered
  into the box, the adapter sync with the page map, progress notifications, a result report).
- A source can be a file, a folder or a zip: zips are unpacked safely into `.caixa/work/imports/`,
  and a folder is searched for what the collector reads (every `_chat.txt`, every Meta thread, …).
- Tests: every collector previews its fixture without writing anything; running imports into a box
  (items, people, pages, change log); running twice changes nothing; progress arrives in order.
- Verify: `python -m pytest -q tests/test_chattr_collectors.py`
- [x] done

### T03: Entry-point registration

- `pyproject.toml`: the `caixa.collectors` entry point and the dependency on Chattr.
- Tests: discovery through the real installed entry points finds the six; the UI description is
  plain JSON.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** Chattr's six sources (iMessage, WhatsApp, Messenger and Instagram, Mail, Google
  Voice, iPhone voicemail) are collectors found through the `caixa.collectors` entry point. Each
  declares its inputs, "how to export" steps and options form; previews count in a scratch Chattr
  root so neither the box nor the source changes; runs import into the box's own Chattr root, draw
  the pages into the box, and sync the master with each item pointing at its page.
- **Files:** `caixa/collectors/{base,options,registry,inputs,chattr}.py`, `caixa/box.py`,
  `pyproject.toml` (entry point, `chattr` dependency), `tests/test_collector_contract.py`,
  `tests/test_chattr_collectors.py`.
- **Errors:** two of my own test expectations were wrong (the WhatsApp fixture chats hold 7 + 4 + 7
  messages; unresolved names are not people until linked) and were corrected; mypy only accepts
  `import chattr.commands as commands` here (the `from chattr import …` form is reported as
  missing when Chattr's sources are checked together with Caixa's).
- **Verify:** `python -m pytest -q` 728 passed; `black --check .` and `mypy caixa tools/chattr/src`
  clean. The six collectors also load through the real installed entry point.

## Review

Reviewed in-session against the Requirements. Findings, all minor and accepted: previews repeat a
full parse in a scratch root (simple and exactly as accurate as a run, at the cost of time on very
large iMessage databases; `limit` helps); `chattr` is declared as a dependency by name only and
there is an unrelated project of that name on PyPI, so Chattr must be installed from `tools/chattr`
first (`pip install -e tools/chattr -e .`); transcription was not run for real here (no model).
No blockers.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
NEEDS MAINTAINER CONFIRMATION: collector ids (imessage, whatsapp, messenger [Messenger and Instagram], mail, googlevoice, voicemail), input kind names (zip, folder, file, database), box.yaml written as JSON (valid YAML; avoids a YAML dependency).

### 2026-11-02
T01: base.py (CollectorInfo validated: at least one input kind from zip/folder/file/database; Preview; Progress; RunResult; runtime-checkable Collector protocol), options.py (JSON-Schema subset: type incl. bool-is-not-integer, enum, minimum/maximum, required, unknown options refused, all errors at once), registry.py (entry points group caixa.collectors; a plugin returns one collector or a list; a broken or duplicate plugin is recorded in registry.problems and never hides the others; describe() = plain JSON for the UI), box.py (Box.create/open/status; box.yaml written as JSON; never overwrites an existing README).

### 2026-11-02
T02/T03 done. NEEDS MAINTAINER CONFIRMATION: Chattr's working root lives in the box at `.caixa/work/chattr/` and unpacked zips in `.caixa/work/imports/`; extracted files go to `Messages/<Person>/Attachments`, `Mail/Attachments`, `Audio/Voicemail`, `Audio/GoogleVoice`; the `chattr` dependency is declared by name only (a different project has that name on PyPI), install Chattr from `tools/chattr` first. Housekeeping: the commit helper had not been staging `.github/`, so ticket 19's workflow was untracked until this commit; it is included now.
