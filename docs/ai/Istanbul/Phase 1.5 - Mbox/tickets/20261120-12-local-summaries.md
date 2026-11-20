---
id: 20261120-12-local-summaries
title: "Local summaries"
type: feature
priority: medium
status: todo
created: 2026-11-20
updated: 2026-11-20
closed:
notes: ""
parent:
depends_on:
- 20261120-09-import-the-chosen-conversations
- 20261120-11-the-person-page-s-entry-and-the-overlay
subtasks: []
---

## Description

Local summaries of each conversation (30–50 words, in its own language), written after the
import by an OpenAI-compatible endpoint.

## Acceptance criteria

- [ ] Settings → Summaries: on/off, endpoint (translation's by default), model, allow a service on the internet, Test with a fixed synthetic conversation
- [ ] Quoted history and signatures removed; long conversations within a size budget
- [ ] Answers checked for 30–50 words (one retry, then cut at a sentence); stored in `mail_threads` with model and date; the entry says it was written by a model
- [ ] A job stage with progress that resumes after a cancel and redoes only conversations that gained mails
- [ ] Without an endpoint the import completes and entries show the opening words; summaries are added later
- [ ] Tests use a stand-in endpoint only

## Context

Phase 1.5 - Mbox Tasks Breakdown item 12. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Key flows* (Summaries), *Components* (Summaries); M12, N1. Reuse `caixa/translation.py` and `chattr/translation.py` client code and the allow-remote rule.

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
