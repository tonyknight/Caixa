---
id: 20261101-18-caixa-master-schema-v0-and-messages-adapter
title: Caixa master schema v0 and messages adapter
type: feature
priority: high
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 18.
parent:
depends_on:
- 20261101-05-unified-schema-v0-chattr-sqlite
- 20261101-14-people-roles-contacts-and-aliases
subtasks: []
current_task: T02
plan_status: in-progress
---
## Description

Create Caixa's master database and load Chattr's output into it.

## Acceptance criteria

- [ ] Migrations; items, people, aliases, item → person links with roles, imports, change log
- [ ] Adapter ATTACHes `chattr.sqlite` and upserts by stable ID; appends change-log rows
- [ ] `aliases.json` exported from the master
- [ ] Re-syncing unchanged data writes zero change-log rows

## Context

Phase1-Collector Tasks Breakdown item 18. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Data model — handoff contract; F13; F14.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
NEEDS MAINTAINER CONFIRMATION: names not in the Requirements: privacy values private (default) / family / public; change-log operations insert / update / link; the people table's is_owner flag; alias kinds phone / email / username / name.

### 2026-11-02
T01: caixa/schema.py (migration 1: people with one owner at most, aliases unique per kind+normalized value+service, items, item_people with roles, imports, change_log with append-only triggers and AUTOINCREMENT so numbers are never reused) and caixa/master.py (Master context manager: people get-or-create case-insensitive; aliases (an alias can't name two people unless move=True); find_person; export_aliases -> aliases.json {value: person} sorted, byte-stable; imports; log_change/changes). Caixa does not import Chattr: the aliases normalisation here is its own, simpler one (Chattr normalises again when it reads aliases.json).
