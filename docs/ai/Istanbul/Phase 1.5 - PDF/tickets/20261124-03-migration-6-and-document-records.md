---
id: 20261124-03-migration-6-and-document-records
title: Migration 6 and document records
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-01-synthetic-pdf-fixtures
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

Migration 6 of the master database: every table of *Data model* (documents, sources, pages, the FTS5 index, fields, tags, authors and aliases, runs, chunks), a records module to write and read them, and `documents.list` / `documents.get`.

## Acceptance criteria

- [ ] Migration 6 applies to a new master and to one at version 5; `schema.CURRENT_VERSION` is 6
- [ ] Documents are `items` of type `document`, collector `pdf`, id `pdf:<source sha256>`, with `time_precision` from the naming date
- [ ] A records module upserts a document, its sources, pages (keeping the FTS index in step), fields, tags and runs, and reads them back
- [ ] `documents.list` and `documents.get` service methods and `caixa documents list|show` commands
- [ ] Reset and undo snapshots cover the new tables

## Context

Phase 1.5 - PDF Tasks Breakdown item 3. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Data model*; D3, D7.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:** Migration 6 in `caixa/schema.py` adds the tables of the Requirements' *Data model*:

- `authors` and `author_aliases`: an alias's normalized form has accents and case removed, so
  "Banco Atlantico" from a scan meets "Banco Atlântico";
- `documents`, `document_sources`, `document_pages`;
- `documents_fts`: FTS5 with external content over `document_pages`, kept in step by triggers,
  `unicode61 remove_diacritics 2`;
- `document_runs`, `document_fields`;
- `tags` (with the starter set) and `document_tags`;
- `chunks`.

`Master.delete_items` also clears a document's rows.

`caixa/documents/records.py` is the one place that writes them:

- `item_id_for(format, sha256)` gives `pdf:<sha256>`.
- `save_document(master, DocumentRecord, import_id)` upserts the `items` row (type `document`,
  collector the format, time from the naming date at its precision, or `''`/`unknown` when
  undated; `text` the summary; `file_path` the archived path; `content_hash` the archived SHA-256)
  and the `documents` row. It logs insert or update with a growing version, and returns
  `inserted` | `updated` | `unchanged`.
- Also: `add_source`, `set_pages`, `add_run`, `add_field`, `set_tags`, `author_id`
  (find-or-create through aliases), `find_by_source`, `get_document`, `list_documents` (filters:
  type, author, year, status, tag).
- `documents.list`/`documents.get` service methods and `caixa documents list|show`.

Reset deletes `caixa.sqlite` whole and undo snapshots copy it whole, so both cover the new tables
(tested).

### T01: Migration 6

- `caixa/schema.py`: `MIGRATION_6`, `CURRENT_VERSION` 6, the module docstring.
- `caixa/master.py`: `delete_items` clears document rows.
- Tests (`tests/test_documents_schema.py`):
  - a new master has every table;
  - a version 5 master migrates;
  - pages are found in `documents_fts`, with accents ignored, and leave it when changed or
    deleted;
  - the starter tags are present;
  - `delete_items` removes a document with its rows;
  - `tests/test_master.py` still passes.
- Verify: `python -m pytest -q tests/test_documents_schema.py tests/test_master.py`
- [x] done

### T02: Document records, list and show

- `caixa/documents/__init__.py`, `caixa/documents/records.py`.
- `caixa/service.py`: `documents.list`, `documents.get`.
- `caixa/cli.py`: `caixa documents list|show`.
- Tests (`tests/test_documents_records.py`):
  - insert, unchanged and update with the change log and versions;
  - undated documents;
  - sources added once per path;
  - pages replaced and searchable;
  - fields with provenance;
  - tags with their source;
  - runs;
  - authors found by alias and accent;
  - list filters and get;
  - the service methods and the commands;
  - an undo snapshot brings document rows back.
- Verify: `python -m pytest -q tests/test_documents_records.py tests/test_documents_schema.py && python -m mypy --python-version 3.12 caixa`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
