---
id: 20261101-18-caixa-master-schema-v0-and-messages-adapter
title: Caixa master schema v0 and messages adapter
type: feature
priority: high
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: master schema, messages adapter, aliases.json, change log.'
parent:
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
- 20261101-14-people-roles-contacts-and-aliases
subtasks: []
plan_status: done
---
## Description

Create Caixa's master database and load Chattr's output into it.

## Acceptance criteria

- [x] Migrations; items, people, aliases, item → person links with roles, imports, change log
- [x] Adapter ATTACHes `chattr.sqlite` and upserts by stable ID; appends change-log rows
- [x] `aliases.json` exported from the master
- [x] Re-syncing unchanged data writes zero change-log rows

## Context

Phase1-Collector Tasks Breakdown item 18. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Data model — handoff contract; F13; F14.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa.sqlite` (`<box>/.caixa/caixa.sqlite`) is the master: it sees every domain and
links items to people. It is separate from Chattr's database; the only contract between them is
the **handoff**: the adapter `ATTACH`es `chattr.sqlite` read-only and upserts in SQL by stable id.
Caixa code lives in `caixa/` (strict mypy) and does not import Chattr.

Tables (migration 1): `people`, `aliases` (identifier or name → person, unique per kind, normalized
value and service), `items` (one per message / mail / call / voicemail: stable id, type, time with
offset and precision, text, page path and anchor, privacy, content hash, version), `item_people`
(roles `sender`, `recipient`, `participant`, `depicted`, `mentioned`), `imports` (provenance per
run), and an append-only `change_log` (monotonic change number, item id, operation `insert` |
`update` | `link`, version, import id), enforced by triggers.

**Names to confirm with the maintainer** (not given in the Requirements): the privacy values
(`private` default, `family`, `public`) and the change-log operation names.

### T01: The master database

- `caixa/schema.py`: ordered migrations and the version table; `caixa/master.py`: `Master(path)`
  context manager (WAL, foreign keys): people (get-or-create, case-insensitive), aliases (kind,
  normalized value, service, source), imports, `export_aliases(path)` → `aliases.json`
  (`{identifier or name: person}`, the format Chattr reads).
- The change log can't be edited or deleted; change numbers only grow.
- Tests: migrations are idempotent and ordered; people and aliases rules; aliases.json round-trip;
  the change log's triggers; the item constraints.
- Verify: `python -m pytest -q tests/test_master.py`
- [x] done

### T02: The messages adapter

- `caixa/collectors/messages.py`: `sync_chattr(master, chattr_db, pages=None) -> SyncResult`:
  attach read-only; upsert items by id (insert, update when the content hash or version moved,
  nothing when unchanged), each with a change-log row; derive item → person links (sender,
  recipients, group participants, mail to/cc) and `link` log rows when they change; learn aliases
  from the handles Chattr resolved; record the import; report unresolved handles.
- Re-syncing unchanged data writes no change-log rows; linking a handle later writes `link` rows
  for exactly the affected items.
- Tests: a real `chattr.sqlite` built from the fixture family (shared root fixture), including an
  update, a relink and an overlapping second archive.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** Caixa has a master database (`caixa.sqlite`, ordered migrations) with people,
  aliases, items, item-to-person links by role, imports, and an append-only change log (triggers
  refuse edits and deletes; change numbers only grow). `caixa.collectors.messages.sync_chattr`
  `ATTACH`es `chattr.sqlite` read-only and upserts items by Chattr's stable ids: new → `insert`,
  changed content hash or version → `update`, unchanged → nothing, so re-syncing unchanged data
  writes no change-log rows. People are linked by role (sender, recipient, participant); a handle
  linked later logs a `link` for exactly its items; resolved handles become aliases;
  `Master.export_aliases` writes the `aliases.json` Chattr reads (round trip tested). Unresolved
  handles are reported. A failed sync rolls back and is recorded as a failed import.
- **Files:**
  - New: `caixa/schema.py`, `caixa/master.py`, `caixa/collectors/__init__.py`,
    `caixa/collectors/messages.py`, `tests/conftest.py` (builds a real `chattr.sqlite` from the
    fixture family), `tests/test_master.py`, `tests/test_messages_adapter.py`.
- **Errors:** none in existing code. One slip of mine: a commit went in with a failing test; fixed
  immediately and the commit helper now refuses to commit unless tests, black and mypy pass.
- **Verify:** `python -m pytest -q` → 655 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean (Caixa strict).

## Review

### 2026-11-02: 21fa5bd..HEAD (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only; names for the maintainer to confirm.

- **Minor (decision):** privacy values (`private`, `family`, `public`), change-log operations
  (`insert`, `update`, `link`), alias kinds and the `is_owner` flag are my choices; the Requirements
  name the concepts, not the values.
- **Minor:** the adapter derives people only from the handles Chattr resolved (plus mail recipients
  found through aliases); a recipient who never wrote and whose address no other service knows gets
  no link until someone links them.
- **Minor:** `depicted` and `mentioned` roles exist in the schema but nothing sets them yet (they are
  for photos and text analysis in later projects).
- **Minor:** items are never deleted; if Chattr drops a message the item stays. A tombstone
  operation is a later decision.
- **Minor:** the owner is created from Chattr's owner-resolved handles when the master has none; if
  the master already has an owner with a different name, Chattr's owner handles are not linked to
  them.
- **Minor:** the page path (`file_path`) is only filled when the caller passes `pages`; the worker
  (ticket 21) must pass the rendering plan after each render.
- **Minor:** the adapter reads the whole `chattr.messages` table every sync (a high-water mark on
  `messages.version` or the import id would avoid that for very large archives).
- **Minor:** Caixa's tests need Chattr installed (to build the fixture archive). Caixa's runtime
  does not import Chattr, but `pyproject.toml` does not yet declare it for tests or for the worker
  (ticket 21).
- **Spec:** all four acceptance criteria are met. Files match the plan.
- **TDD:** RED then GREEN for both tasks (collection errors, then 17 and 22 passing; one test in T01
  needed a fix after it had been committed).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
NEEDS MAINTAINER CONFIRMATION: names not in the Requirements: privacy values private (default) / family / public; change-log operations insert / update / link; the people table's is_owner flag; alias kinds phone / email / username / name.

### 2026-11-02
T01: caixa/schema.py (migration 1: people with one owner at most, aliases unique per kind+normalized value+service, items, item_people with roles, imports, change_log with append-only triggers and AUTOINCREMENT so numbers are never reused) and caixa/master.py (Master context manager: people get-or-create case-insensitive; aliases (an alias can't name two people unless move=True); find_person; export_aliases -> aliases.json {value: person} sorted, byte-stable; imports; log_change/changes). Caixa does not import Chattr: the aliases normalisation here is its own, simpler one (Chattr normalises again when it reads aliases.json).

### 2026-11-02
T02: caixa/collectors/messages.py: sync_chattr(master, chattr_db, pages=None). ATTACH ... ?mode=ro (Master opens with uri=True); all work inside a SAVEPOINT: a failure rolls back and leaves a 'failed' import row. Links: sender (handle's person; owner for the owner's own messages), recipients (the counterpart of a 1:1 chat, or a mail's To/Cc via the Mail handles and the master's aliases), participants (group members plus the owner). Existing item fields people may have set (privacy, page path) survive updates. 'link' change rows only for unchanged items whose link set moved.
