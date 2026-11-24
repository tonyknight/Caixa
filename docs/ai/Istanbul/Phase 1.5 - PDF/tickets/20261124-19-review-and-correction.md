---
id: 20261124-19-review-and-correction
title: "Review and correction"
type: feature
priority: high
status: todo
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ""
parent:
depends_on:
- 20261124-12-reconciliation-confidence-and-apply
- 20261124-17-documents-view-on-the-index-page
subtasks: []
---

## Description

Authoring mode for documents: an Unrecognized card has Author and Date fields and Apply; any document's author, title, date, type and tags can be corrected; corrections are `user_verified`, move files, and are batched behind Update the pages; the To review list shows reasons and candidates.

## Acceptance criteria

- [ ] Typing author and date on an Unrecognized card and Apply moves it to `<YYYY>/<Author>/` under its archival name
- [ ] Corrections are `user_verified` and never overwritten by enrichment
- [ ] To review lists reasons and candidates with sources; choosing one applies it
- [ ] Every action is also `documents.update` and a `caixa documents` command

## Context

Phase 1.5 - PDF Tasks Breakdown item 19. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Enrichment, confidence and review* (Corrections), *Key flows* (Review); D14, D22.

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
