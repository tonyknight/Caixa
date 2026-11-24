---
id: 20261124-20-passages-embeddings-and-hybrid-search
title: "Passages, embeddings and hybrid search"
type: feature
priority: medium
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-08-page-text-and-full-text-index
subtasks: []
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

Status: draft
Current task:

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
