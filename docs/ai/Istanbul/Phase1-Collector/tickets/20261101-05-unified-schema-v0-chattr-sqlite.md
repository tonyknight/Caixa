---
id: 20261101-05-unified-schema-v0-chattr-sqlite
title: Unified schema v0 (chattr.sqlite)
type: feature
priority: high
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 5.
parent:
depends_on:
- 20261101-04-chattr-stabilization
subtasks: []
plan_status: in-progress
current_task: T03
---
## Description

Chattr's own next milestone: one unified schema and one `DatabaseManager` for all services.

## Acceptance criteria

- [ ] Tables per the Requirements data model: conversations, handles, participants, messages, attachments, reactions, imports, schema_version
- [ ] Ordered migrations; stable IDs; upserts make re-imports idempotent
- [ ] `imports` and `Services/*.json` `state` updated on every run
- [ ] Native per-service JSON export still available

## Context

Phase1-Collector Tasks Breakdown item 5. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Data model — Chattr unified schema v0; Stable IDs; F2; N3; N5.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T03

Scope is the data layer. Wiring each source parser into it is tickets 07–12; this ticket adapts
today's WhatsApp/Messenger parser output so the existing CLI and HTML keep working.

**Time handling:** `timestamp_utc` + `tz_offset_minutes` + `time_precision`. Exports that give
local wall time without a zone (for example WhatsApp) store the offset as unknown (`NULL`) with
`tz_assumed = 1`; per-source time-zone handling arrives with each parser ticket.

### T01: Schema v0 with ordered migrations

- `src/chattr/schema.py`: an ordered migration list.
- Version 1 creates `conversations`, `handles`, `participants`, `messages`, `attachments`,
  `reactions`, `imports` and `schema_version`, with keys and indexes. It also creates a
  `messages_view` with the legacy column names (`timestamp`, `message_author`,
  `message_sender`, `body`, `type`, `service`) for the existing HTML and CLI code.
- `apply_migrations(conn)` is idempotent.
- Tests: fresh database is at version 1 with every table; a second run changes nothing; view
  columns are present.
- Verify: `python -m pytest -q`
- [x] done

### T02: Normalized records and stable IDs

- `src/chattr/records.py`: dataclasses `ConversationRecord`, `MessageRecord`,
  `AttachmentRecord`, `ReactionRecord`.
- **Stable IDs:**
  - conversation: `<service>:<hash of the source conversation id>`;
  - message: the source message id when there is one, else a hash of (service, conversation,
    time, sender, body, occurrence). Occurrence numbers identical messages within one
    conversation, so genuine repeats stay distinct.
- `content_hash` detects changed messages.
- Tests: deterministic IDs; repeats get distinct IDs; an overlapping list gets the same IDs for
  the overlap.
- Verify: `python -m pytest -q`
- [x] done

### T03: One `DatabaseManager`: imports and upserts

- `DatabaseManager` runs the migrations when opened (`create_tables` stays as an alias).
- `start_import(service, source)` records the source path and hash; `finish_import(...)` records
  the counts and the source cursor.
- `upsert(conversation, records, import_id)` upserts conversations, handles, participants,
  messages, attachments (by sha256) and reactions. It returns inserted / updated / unchanged
  counts.
- `get_all_messages()` reads `messages_view`.
- Tests: importing the synthetic WhatsApp export twice adds nothing the second time; an
  overlapping subset adds nothing; a changed body counts as one update; the HTML test still
  passes.
- Verify: `python -m pytest -q`
- [ ] done

### T04: Parser adapter, import runs and service state

- `records_from_parser(messages, service, conversation)` maps today's WhatsApp/Messenger parser
  dicts to records.
- `chattr.importing.import_messages(store, settings, service, source, messages)` runs a whole
  import and saves `Services/<Service>.json` state (`last_import_date`,
  `total_messages_imported`, `last_export_file`).
- The CLI's import path uses it; `insert_messages` stays as a compatibility wrapper.
- Tests: state and the `imports` row are updated after an import; a re-import leaves the total
  unchanged.
- Verify: `python -m pytest -q`
- [ ] done

### T05: JSON export stays available

- iMessage's native JSON export is unchanged.
- Add `DatabaseManager.export_json(service, path)`, a per-service export of the stored records,
  so every service can still produce JSON.
- Test: exporting the imported WhatsApp records gives valid JSON with every message.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
