---
id: 20261124-03-migration-6-and-document-records
title: Migration 6 and document records
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: migration 6, records module, documents.list/get and caixa documents
  list|show.'
parent:
depends_on:
- 20261124-01-synthetic-pdf-fixtures
subtasks: []
plan_status: done
---
## Description

Migration 6 of the master database: every table of *Data model* (documents, sources, pages, the FTS5 index, fields, tags, authors and aliases, runs, chunks), a records module to write and read them, and `documents.list` / `documents.get`.

## Acceptance criteria

- [x] Migration 6 applies to a new master and to one at version 5; `schema.CURRENT_VERSION` is 6
- [x] Documents are `items` of type `document`, collector `pdf`, id `pdf:<source sha256>`, with `time_precision` from the naming date
- [x] A records module upserts a document, its sources, pages (keeping the FTS index in step), fields, tags and runs, and reads them back
- [x] `documents.list` and `documents.get` service methods and `caixa documents list|show` commands
- [x] Reset and undo snapshots cover the new tables

## Context

Phase 1.5 - PDF Tasks Breakdown item 3. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Data model*; D3, D7.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

## Completion report

- **Outcome:** Migration 6 adds the document tables:
  - authors and accent-free aliases;
  - documents with the processing, OCR, validation and AI statuses;
  - sources and pages;
  - `documents_fts` (FTS5, external content, trigger-synced, accents ignored);
  - runs, fields with provenance, tags (with the starter set) and chunks.

  `Master.delete_items` clears a document's rows. `caixa/documents/records.py` writes and reads
  them: `save_document` (insert, update or unchanged, with versions in the change log; the naming
  date's precision on the item; undated as `''`/`unknown`), `add_source`, `set_pages`, `add_run`,
  `add_field`, `set_tags` (a model's tags never replace the owner's), `author_id` and aliases,
  `find_by_source`, `list_documents` (filters) and `get_document`. Also the `documents.list` and
  `documents.get` service methods, and `caixa documents list|show`.
- **Files:**
  - new: `caixa/documents/__init__.py`, `caixa/documents/records.py`,
    `tests/test_documents_schema.py`, `tests/test_documents_records.py`;
  - changed: `caixa/schema.py`, `caixa/master.py`, `caixa/service.py`, `caixa/cli.py`,
    `tests/test_worker_protocol.py` (the protocol's method list).
- **Errors:** the full suite caught that the worker protocol's list of methods must name the new
  ones; added.
- **Verify:**
  - `python -m pytest -q`: 1633 passed plus the protocol test (31 passed).
  - mypy (3.12 target): only the 8 baseline errors.
  - black: clean.

## Review

### 2026-11-24: 9e84927..b04ecc6 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** `save_document` compares every column, so a later step that sets only one fact must
  pass the whole record. Tickets 05 and later should read, change and save (or gain a small
  `update_document` helper when they need it).
- **Minor:** `list_documents` filters by the author's alias; an unknown author gives an empty list
  rather than an error (as intended for search filters).
- **Spec:** D3 and D7 met, along with the *Data model*; every acceptance criterion met. Reset
  deletes `caixa.sqlite` whole, and undo copies it whole (tested).
- **TDD:** RED (`6 failed`; then `ModuleNotFoundError: caixa.documents`) before each GREEN.
- **Commits:** `20261124-03 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
