---
id: 20261124-20-passages-embeddings-and-hybrid-search
title: Passages, embeddings and hybrid search
type: feature
priority: medium
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: Hybrid search by words and meaning; documents.embed
parent:
depends_on:
- 20261124-08-page-text-and-full-text-index
subtasks: []
plan_status: done
current_task: T02
---
## Description

Passages and embeddings (endpoint `/v1/embeddings`; Apple `NLContextualEmbedding` through the helper), a resumable stage, hybrid ranking with full text (reciprocal rank fusion), the `documents.embedding_model` setting.

## Acceptance criteria

- [x] A paraphrase the full text misses finds the fixture (stand-in embeddings)
- [x] Embedding can stop and continue; passages are keyed by `item_id`
- [x] No embedding model: search is full text only

## Context

Phase 1.5 - PDF Tasks Breakdown item 20. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Search and Ask* (Semantic); D23.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: T02

**Design:**

- **Passages:** `caixa/documents/passages.py` splits each page's text into passages of about
  1,000 characters, with 150 characters of overlap, cut at sentence or word ends. They are stored
  in `chunks` (keyed by `item_id`, with page, start and end), so Stage 2 can add mail and
  messages the same way.
- **Embeddings:** `caixa/documents/embeddings.py`.
  - The provider is the summaries' endpoint, asked at `/v1/embeddings` with the new setting
    `documents.embedding_model` (empty: no semantic search). It is on this computer only, as for
    reading.
  - Vectors are normalized and stored as float32 with the model's name.
  - Apple's `NLContextualEmbedding` needs the Swift helper; that is left for the maintainer's Mac,
    and Automatic uses the endpoint's model.
- **The stage:** `embed_documents(box)` embeds every document whose passages have no vector from
  the current model, in batches, committing each document. It can stop and continue, and runs
  after reading in an import. Also the `documents.embed` job and `caixa documents embed`.
- **Hybrid search:** `search.search` gains `semantic`.
  - The query is embedded, and passages are ranked by cosine similarity (numpy, over the model's
    vectors).
  - Full-text pages and semantic passages are joined by reciprocal rank fusion (k = 60) on
    (document, page).
  - A page found only by meaning gets its passage as its snippet and is marked `semantic`.
  - Without a model or vectors, search is full text alone.
  - `documents.search` uses it by default; the window's search follows.
- **Tests:** a deterministic stand-in embedding endpoint maps words to concepts
  (`power` ≈ `electricity` ≈ `energia`), so a paraphrase finds what full text misses.

### T01: Passages, vectors and the stage

- `caixa/documents/passages.py`, `caixa/documents/embeddings.py`, `caixa/settings.py`.
- `tests/fixtures/stand_in_embeddings.py`.
- Tests (`tests/test_documents_semantic.py`):
  - passages overlap, cut at word ends, and cover each page;
  - vectors are stored normalized with their model;
  - a second run embeds nothing;
  - a stopped run carries on;
  - no model means nothing to do;
  - a non-local endpoint is refused.
- Verify: `python -m pytest -q tests/test_documents_semantic.py`
- [x] done

### T02: Hybrid search, the job and the command

- `caixa/documents/search.py`, `caixa/collectors/pdfImport.py` (embedding after reading),
  `caixa/service.py`, `caixa/cli.py`, `tests/test_worker_protocol.py`.
- Tests:
  - "power invoice" finds the electricity bill by meaning when full text finds nothing;
  - a word search still ranks its full-text pages first;
  - without vectors the results equal full text;
  - the job and the command embed;
  - an import with the setting embeds.
- Verify: `python -m pytest -q tests/test_documents_semantic.py tests/test_documents_search.py tests/test_worker_protocol.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:**
  - **Passages:** `caixa/documents/passages.py` cuts each page into passages of about 1,000
    characters with 150 of overlap, at word ends. They are stored in `chunks` by `item_id`, so
    Stage 2 can add mail and messages.
  - **Vectors:** `caixa/documents/embeddings.py` asks the summaries' endpoint, on this computer
    only, at `/v1/embeddings`, using the `documents.embedding_model` setting (empty: no semantic
    search). Vectors are stored normalized, as float32, with the model's name. A document is
    committed as soon as it is embedded, so a stopped run carries on, and the run stops after two
    failures in a row. New page text (reprocess) drops a document's passages, so they are
    embedded again.
  - **Hybrid search:** given an embedder, `search.search` ranks passages by cosine similarity
    (numpy) and joins them with the full-text pages by reciprocal rank fusion (k = 60) on
    (document, page). A page found only by meaning has its passage as its snippet and is marked
    `semantic`. Without a model or vectors, the results are exactly the full-text results.
    `documents.search` uses an embedder by default, waiting at most 10 seconds for the model.
  - **Running it:** the `documents.embed` job, `caixa documents embed`, and embedding after
    reading in an import when a model is set.
- **Files:**
  - new: `caixa/documents/passages.py`, `caixa/documents/embeddings.py`,
    `tests/fixtures/stand_in_embeddings.py`, `tests/test_documents_semantic.py`;
  - changed: `caixa/documents/search.py`, `caixa/documents/records.py`,
    `caixa/collectors/pdfImport.py`, `caixa/service.py`, `caixa/cli.py`, `caixa/settings.py`,
    `tests/test_worker_protocol.py`.
- **Errors:**
  - A patch script stopped on an anchor that didn't match; reapplied.
  - Hybrid ranking rewrote the ranks even with no vectors; it now returns the full-text results
    unchanged.
- **Verify:**
  - `python -m pytest -q`: 1956 passed, 1 skipped (before the review fixes; their tests and the
    ticket's suites pass: 105).
  - mypy (3.12 target): only the 8 baseline errors.
  - Apple's `NLContextualEmbedding` is left for the maintainer's Mac (Swift helper).

## Review

### 2026-11-24: 80f9d13..4d744be (T01–T02), reviewed in-session

**Verdict:** clean after two fixes; Minor items only.

- **Fixed:** reprocessing kept stale passages from the old text. `set_pages` now deletes them.
- **Fixed:** a search waited up to 120 s for a model that hung. It now waits 10 s, then searches
  by words alone.
- **Minor:** vectors are read from the database on each search (no cache); fast enough for a
  family archive, and worth revisiting in Stage 2.
- **Minor:** semantic snippets carry no `[marks]`: nothing in them matched by words.
- **Spec:** D23 met; every acceptance criterion met.
- **TDD:** RED (`TypeError: search() got an unexpected keyword argument 'embed'`; no method
  `documents.embed`) before GREEN.
- **Commits:** `20261124-20 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
