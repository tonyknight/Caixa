---
id: 20261128-04-author-knowledge-in-the-import
title: Author knowledge in the import
type: feature
priority: high
status: in-progress
created: 2026-11-28
updated: 2026-11-28
closed:
notes: ''
parent:
depends_on:
- 20261128-03-what-the-model-reads-and-is-told
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

The third part of folding `prepare` into the import (D31). The owner's author lessons
(`.caixa/author-knowledge.json`, D29), so far read only by `prepare`, guide the import's reading
and reconciliation.

## Acceptance criteria

- [ ] The model is told the accepted authors named in the document's text, and the rejected
      names.
- [ ] An `instead` lesson replaces the model's author (one for the document's kind first).
- [ ] A rejected name with no lesson leaves the document without an author; it goes to review
      as `rejected_author` and waits in `Unrecognized/`.
- [ ] An author the owner verified is never changed by a lesson.
- [ ] Reconciliation after a correction applies the same lessons.

## Context

Requirements: D31 (*Author knowledge in the import*), D29; Tasks Breakdown 29.

## Subtasks

## Implementation plan

Status: in-progress
Current task: T02

**Design:**

- **Told to the model** (`enrich.py`): `DocumentInput` gains `accepted` and `rejected`. The header
  adds two lines:
  - "Accepted authors named in the text: …", for the accepted names the text holds (as the box's
    known authors are filtered now);
  - "Never give these as the author: …", for the rejected names, at most 30 (the latest).

  `enrich_documents` loads the box's knowledge once and passes it to `_input`.
- **Applied in reconciliation** (`reconcile.py`): `decide(…, knowledge=None)`. The model's author
  goes through `author_knowledge.apply(knowledge, said, decision.type)`, after the type is
  decided:
  - an `instead` makes the lesson's author the author, counted as verified (the owner's lesson),
    with a trail line;
  - a rejected name with no lesson gives no author and the reason `rejected_author` (not
    `no_author`), with a trail line;
  - the owner's own author (`user_verified`) is never put through it.

  `reconcile_document` and `corrections.correct` load the box's knowledge and pass it.
- **Words:** `REASONS` gains `rejected_author`, and `pages.REASONS` its sentence: "The model
  named someone you rejected as an author".

### T01: Lessons in reconciliation

- `caixa/documents/reconcile.py`, `caixa/documents/corrections.py`, `caixa/documents/pages.py`,
  `tests/test_documents_reconcile.py`.
- Tests:
  - an instead replaces the model's author and is verified;
  - an instead for the kind wins over one for every kind;
  - a rejected name gives `rejected_author`, not confident;
  - the owner's author ignores lessons;
  - with no knowledge, `decide` is as before.
- Verify: `python -m pytest -q tests/test_documents_reconcile.py tests/test_documents_corrections.py tests/test_author_knowledge.py`
- [x] done

### T02: Told to the model, and the import end to end

- `caixa/documents/enrich.py`, `tests/test_documents_enrich.py`.
- Tests:
  - the header names the accepted authors in the text and the rejected names;
  - a box with no knowledge sends neither line;
  - an import where the stand-in names a rejected author leaves that document in
    `Unrecognized/` for review as `rejected_author`, and one with an instead files it under the
    lesson's author;
  - a later correction of the date keeps the lesson.
- Verify: `python -m pytest -q tests/test_documents_enrich.py tests/test_documents_reconcile.py tests/test_documents_corrections.py && python -m mypy --python-version 3.12 caixa`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
