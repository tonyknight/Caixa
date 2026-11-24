---
id: 20261124-08-page-text-and-full-text-index
title: Page text and full-text index
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-04-the-pdf-collector
- 20261124-06-selective-ocr
subtasks: []
plan_status: done
---
## Description

Each page's text (PDF or OCR) stored and indexed in FTS5; `documents.search` and `caixa documents search` with snippets, pages and filters.

## Acceptance criteria

- [ ] A word printed only on a scanned page finds that document and page
- [ ] Phrases, prefixes, a cheque number, an amount and an account suffix are found
- [ ] Filters by type, category, author, date range, tag, status
- [ ] Accents are ignored in matching

## Context

Phase 1.5 - PDF Tasks Breakdown item 8. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Search and Ask* (Full text); D10, D21.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** page text and its FTS5 index already exist (tickets 03, 05, 06: `document_pages`
rows from the PDF or from OCR, kept in `documents_fts` by triggers, accents ignored). This ticket
adds searching them, in `caixa/documents/search.py`:

- `fts_query(text)` turns what a person types into a safe FTS5 query:
  - "quoted phrases" stay phrases;
  - every other word becomes a quoted term, so `450.00`, `FT 2024/118` and `HZ-55120` match as
    the index splits them, and FTS5's operators and punctuation cannot break the query;
  - a trailing `*` makes a prefix;
  - every term must match.
- `search(master, query, …filters, limit)`:
  - the matching pages, best first (BM25);
  - each with its document (title, author, date, type, file path), the page number, where its
    text came from (PDF or OCR) and a snippet with the words marked;
  - filters: type, category, author, date from and to (naming date, any precision), tag,
    processing status, OCR status;
  - an empty query with filters lists their documents' first pages.
- `documents.search` service method; `caixa documents search QUERY [--type …] [--json]`.

### T01: The query and the search

- `caixa/documents/search.py` (`fts_query`, `search`).
- Tests (`tests/test_documents_search.py`, on an import of the family with OCR; the OCR cases
  are skipped without the tools):
  - a word printed only on a scanned page finds that document and page (`77812`, `55031`);
  - phrases;
  - prefixes;
  - a cheque number, an amount (`450.00`) and an account suffix (`4821`);
  - accents ignored (`atlantico`);
  - every filter narrows;
  - snippets mark the words;
  - operators and stray quotes in what was typed do no harm;
  - an empty query without filters finds nothing.
- Verify: `python -m pytest -q tests/test_documents_search.py`
- [x] done

### T02: Searching from the service and the command line

- `caixa/service.py`: `documents.search`.
- `caixa/cli.py`: `caixa documents search`.
- `tests/test_worker_protocol.py`: the method is listed.
- Tests: the service returns hits and filters; the command prints title, page and snippet, and
  `--json`.
- Verify: `python -m pytest -q tests/test_documents_search.py tests/test_worker_protocol.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
