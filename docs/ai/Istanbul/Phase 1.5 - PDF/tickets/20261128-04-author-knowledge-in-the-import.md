---
id: 20261128-04-author-knowledge-in-the-import
title: Author knowledge in the import
type: feature
priority: high
status: done
created: 2026-11-28
updated: 2026-11-28
closed: 2026-11-28
notes: Lessons told to the model and applied at filing and reconciliation
parent:
depends_on:
- 20261128-03-what-the-model-reads-and-is-told
subtasks: []
plan_status: done
current_task: T02
---
## Description

The third part of folding `prepare` into the import (D31). The owner's author lessons
(`.caixa/author-knowledge.json`, D29), so far read only by `prepare`, guide the import's reading
and reconciliation.

## Acceptance criteria

- [x] The model is told the accepted authors named in the document's text, and the rejected
      names.
- [x] An `instead` lesson replaces the model's author (one for the document's kind first).
- [x] A rejected name with no lesson leaves the document without an author; it goes to review
      as `rejected_author` and waits in `Unrecognized/`.
- [x] An author the owner verified is never changed by a lesson.
- [x] Reconciliation after a correction applies the same lessons.

## Context

Requirements: D31 (*Author knowledge in the import*), D29; Tasks Breakdown 29.

## Subtasks

## Implementation plan

Status: done
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
- [x] done

## Completion report

- **Outcome:**
  - **Told:** the model's header names the accepted authors the document's text holds ("Accepted
    authors named in the text: …") and the rejected names, the latest 30 ("Never give these as
    the author: …"). A box without lessons sends neither line.
  - **Applied in reconciliation:** `decide(…, knowledge=…)` puts the model's author through
    `author_knowledge.apply`, for the document's kind. An `instead` replaces it and counts as
    verified. A rejected name with no lesson gives no author and the new reason
    `rejected_author`, "The model named someone you rejected as an author". The owner's author
    is never put through it. `reconcile_document` and `corrections.correct` pass the box's
    lessons, so a later correction keeps them.
  - **Applied at filing:** a file's provisional author, from its name or properties, goes through
    the same lessons. A rejected name never gives a document its folder before the model reads
    it.
- **Files:** `caixa/documents/reconcile.py` (`_lesson`, `decide`), `caixa/documents/enrich.py`
  (`DocumentInput.accepted`/`rejected`, the header, `MOST_REJECTED`),
  `caixa/documents/importing.py` (`_taught`), `caixa/documents/corrections.py`,
  `caixa/documents/pages.py`, `tests/test_documents_reconcile.py`,
  `tests/test_documents_enrich.py`.
- **Errors:**
  - Added to the plan: the lessons apply at provisional filing too (`importing.py`). Without
    that, a statement filed by its PDF properties under a rejected name stayed there, because a
    decision that is not confident does not move a document.
  - The first import tests used `2022 Car Insurance.pdf`, which always waits in `Unrecognized/`
    for its own conflicts. That made one folder check meaningless; they now use the November
    statement, which files with confidence.
  - An instead to "Banco Atlântico SA" normalized back to the known "Banco Atlântico"; the test
    uses a distinct name. That behaviour (an instead close to a known author is matched to it) is
    as designed.
  - A variable name clashed with one already in `import_examined`; renamed `lessons`.
- **Verify:**
  - `python -m pytest -q` (with `PYTHONUNBUFFERED=1`): 2,182 passed.
  - mypy: the 8 baseline errors.

## Review

### 2026-11-28: 5bc39e8..HEAD (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** a rejected model author leaves the model's field unapplied, but it stays among the
  card's candidates, so the authoring tool still offers it. The owner can pick another.
- **Minor:** the lessons are loaded once per reading run, so a correction made while a long run
  reads is applied from the next run.
- **Spec:** D31's *Author knowledge in the import* met; every acceptance criterion met.
- **TDD:** RED (no `knowledge` in `decide`; no header lines; a rejected name filed by its
  properties) before each GREEN.
- **Commits:** `20261128-04 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
