---
id: 20261101-17-rebuild-chattr-sqlite-from-html-data-islands
title: Rebuild chattr.sqlite from HTML data islands
type: feature
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 17.
parent:
depends_on:
- 20261101-15-html-rendering-from-the-database
subtasks: []
current_task: T01
---
## Description

Re-create the domain store from rendered pages.

## Acceptance criteria

- [ ] Deleting `chattr.sqlite` and rebuilding from HTML gives identical IDs and counts

## Context

Phase1-Collector Tasks Breakdown item 17. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Rebuild chain; F10.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T01

**Design:** the rendered pages are the durable copy of the domain store (rebuild chain: top-level
files → domain stores → master). `rebuild.rebuild_database(site, db_path)` reads every page's
`#chattr-data` island (schema `chattr-page-1`) and writes the rows back with the ids, content
hashes and versions the island carries, so nothing is re-derived: a rebuilt database has the same
conversation and message ids, and the same attachments, reactions, handles, participants. Provenance
the pages don't hold (the `imports` log) is replaced by one `imports` row describing the rebuild.
It refuses to write into a database that already has data.

### T01: Rebuild from the islands

- Complete the island: handles of reaction senders are included (otherwise they were lost).
- `rebuild_database(site, db_path) -> RebuildResult(pages, conversations, messages, attachments,
  reactions, handles)`: reads islands, upserts conversations/handles/participants, then messages with
  their attachments and reactions, in one transaction.
- `compare_databases(a, b)`: differences in ids, columns and counts (the test oracle, also useful
  after a real rebuild).
- Tests: render the whole fixture archive, rebuild into a new database, and compare: identical
  conversation and message rows (all columns except the import link), handles, participants,
  attachments, reactions; re-rendering the rebuilt database gives byte-identical pages.
- Verify: `python -m pytest -q tools/chattr/tests/test_rebuild.py`
- [ ] done

### T02: `chattr-cli rebuild` and robustness

- `chattr-cli rebuild [--from DIR] [--db FILE]` (default: the pages under `Output/Chattr` into the
  central database); refuses an existing database that holds messages.
- Damaged islands, other HTML, and unknown schema versions are skipped with a warning, never
  half-applied.
- Tests: the command; refusal; skipped files reported; a partial failure leaves no partial data.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
