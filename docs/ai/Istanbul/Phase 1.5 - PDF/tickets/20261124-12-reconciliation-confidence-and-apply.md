---
id: 20261124-12-reconciliation-confidence-and-apply
title: "Reconciliation, confidence and apply"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-10-ai-classification
subtasks: []
---

## Description

Reconciliation of every field's candidates, provenance, conflicts, the confidence rule, apply (rename and move recorded for undo) or To review, re-enrichment without duplicates, authors with aliases (rename, merge, folders follow).

## Acceptance criteria

- [ ] Descriptive fixtures are applied: renamed and moved to `<YYYY>/<Author>/`
- [ ] A misleading filename produces a conflict and To review; no filename fact is dropped without contradicting evidence
- [ ] Date kinds stay separate; re-enriching creates no duplicate and keeps `user_verified`
- [ ] Undo puts moved files back; authors can be renamed and merged with folders following

## Context

Phase 1.5 - PDF Tasks Breakdown item 12. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Enrichment, confidence and review*, *Authors*; D13–D15.

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
