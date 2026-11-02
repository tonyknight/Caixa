---
id: 20261101-17-rebuild-chattr-sqlite-from-html-data-islands
title: Rebuild chattr.sqlite from HTML data islands
type: feature
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: rebuild chattr.sqlite from HTML data islands, identical ids and counts.'
parent:
depends_on:
- 20261101-15-html-rendering-from-the-database
subtasks: []
plan_status: done
---
## Description

Re-create the domain store from rendered pages.

## Acceptance criteria

- [x] Deleting `chattr.sqlite` and rebuilding from HTML gives identical IDs and counts

## Context

Phase1-Collector Tasks Breakdown item 17. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Rebuild chain; F10.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

### T02: `chattr-cli rebuild` and robustness

- `chattr-cli rebuild [--from DIR] [--db FILE]` (default: the pages under `Output/Chattr` into the
  central database); refuses an existing database that holds messages.
- Damaged islands, other HTML, and unknown schema versions are skipped with a warning, never
  half-applied.
- Tests: the command; refusal; skipped files reported; a partial failure leaves no partial data.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `chattr-cli rebuild [--from DIR] [--db FILE]` recreates `chattr.sqlite` from the data
  islands in the rendered pages. On the whole fixture archive the rebuilt database equals the
  original: the same conversation and message ids, content hashes and versions, and the same
  attachments, reactions, handles and participants (`compare_databases` finds no difference), the
  legacy view gives the same rows, and rendering the rebuilt database gives byte-identical pages. It
  writes in one transaction, refuses a database that already holds messages, and reports pages it
  skipped (damaged islands, unknown schema versions).
- **Files:**
  - New: `rebuild.py` (`rebuild_database`, `compare_databases`, `read_islands`).
  - Changed: `render.py` (islands now include reaction senders' handles and the raw archival file
    name), `commands.py` (`rebuild`), `cli.py` (`rebuild` command).
  - Tests: `test_rebuild`, `test_rebuild_command`.
- **Errors:** found while writing the oracle and fixed in the island: handles that only sent a
  reaction were missing, and `archival_filename` was filled with a value derived from the storage
  path where the database holds none, so a rebuild would not have been identical.
- **Verify:** `python -m pytest -q` → 541 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean.

## Review

### 2026-11-02: 87fce3b..HEAD (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** the `imports` log can't be rebuilt (pages don't hold it); a rebuild records one `Rebuild`
  row instead. The change log and per-run counts are Caixa's concern (ticket 18).
- **Minor:** conversations with no messages have no page and are not rebuilt. None occur in the
  fixtures; a conversation exists in the database only because messages were imported into it.
- **Minor:** handle row numbers differ after a rebuild (they are autoincrement); nothing refers to them
  outside the database, and every comparison is by service and identifier.
- **Minor:** HTML mail bodies, kept in `service_specific`, are in the island and so survive; but
  anything not rendered on a page and not in the island (nothing today) would be lost.
- **Minor:** the `Services/<Service>.json` state files are not rebuilt (they mirror `imports`).
- **Minor:** large archives mean large pages (the island repeats every message's data); acceptable
  for a family archive.
- **Spec:** the one acceptance criterion is met, tested on the whole fixture archive.
- **TDD:** RED then GREEN for both tasks (collection error then 13 passing; 6 failing, then passing).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
T01: rebuild.py reads every page's island (schema chattr-page-1) and writes rows with the island's ids, hashes and versions; compare_databases is the oracle (rows by id/content; handles compared by service+identifier, not row number). Fixing the oracle found two island gaps (reaction-only senders' handles; archival_filename must be the raw column). Re-rendering the rebuilt DB is byte-identical.

### 2026-11-02
T02: chattr-cli rebuild [--from DIR] [--db FILE] (defaults: Output/Chattr pages, Database/chattr.sqlite); refuses a database that holds messages; no pages at all fails before any database is created; an island that can't be applied raises RebuildError naming the page, rolls everything back and removes a database the rebuild itself created.
