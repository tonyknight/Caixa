---
id: 20261124-20-passages-embeddings-and-hybrid-search
title: Passages, embeddings and hybrid search
type: feature
priority: medium
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-08-page-text-and-full-text-index
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

Passages and embeddings (endpoint `/v1/embeddings`; Apple `NLContextualEmbedding` through the helper), a resumable stage, hybrid ranking with full text (reciprocal rank fusion), the `documents.embedding_model` setting.

## Acceptance criteria

- [ ] A paraphrase the full text misses finds the fixture (stand-in embeddings)
- [ ] Embedding can stop and continue; passages are keyed by `item_id`
- [ ] No embedding model: search is full text only

## Context

Phase 1.5 - PDF Tasks Breakdown item 20. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Search and Ask* (Semantic); D23.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
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
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
