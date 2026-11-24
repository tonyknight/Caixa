---
id: 20261124-10-ai-classification
title: "AI classification"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-08-page-text-and-full-text-index
- 20261124-09-filename-and-property-evidence
subtasks: []
---

## Description

Classification by a local model: provider reuse (Automatic, Apple Intelligence, endpoint; never a non-local endpoint), the classification schema, structured output, validation with one retry, evidence checks, history, the enrich stage after an import and `caixa documents enrich`.

## Acceptance criteria

- [ ] With the stand-in endpoint and the stand-in Apple helper, fixtures get proposals of the classification schema
- [ ] Every evidence quote is checked against its page; unverified fields stay proposals
- [ ] A non-local endpoint is refused even with `summaries.allow_remote`
- [ ] Model, provider, prompt version, schema version and time are recorded; the stage can stop and continue

## Context

Phase 1.5 - PDF Tasks Breakdown item 10. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Enrichment, confidence and review*; D12, D17.

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
