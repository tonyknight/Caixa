---
id: 20261124-10-ai-classification
title: AI classification
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: local-only classification with schema, retry, verified evidence; enrich
  stage, job, command. Apple guided generation left for the Mac.'
parent:
depends_on:
- 20261124-08-page-text-and-full-text-index
- 20261124-09-filename-and-property-evidence
subtasks: []
plan_status: done
---
## Description

Classification by a local model: provider reuse (Automatic, Apple Intelligence, endpoint; never a non-local endpoint), the classification schema, structured output, validation with one retry, evidence checks, history, the enrich stage after an import and `caixa documents enrich`.

## Acceptance criteria

- [x] With the stand-in endpoint and the stand-in Apple helper, fixtures get proposals of the classification schema
- [x] Every evidence quote is checked against its page; unverified fields stay proposals
- [x] A non-local endpoint is refused even with `summaries.allow_remote`
- [x] Model, provider, prompt version, schema version and time are recorded; the stage can stop and continue

## Context

Phase 1.5 - PDF Tasks Breakdown item 10. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Enrichment, confidence and review*; D12, D17.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/documents/enrich.py`.

- **Provider:** the summaries settings (Automatic: Apple Intelligence first; or the
  OpenAI-compatible endpoint and model, translation's when left empty) through
  `summaries.client`. Documents add one rule: an endpoint that is not on this computer is refused
  (`is_local_endpoint`), whatever `summaries.allow_remote` says. A new setting `documents.enrich`
  (on) turns it off.
- **What the model reads** (`prepare`), within 6,000 characters for Apple Intelligence or 12,000
  for an endpoint:
  - the file name and what it says (`caixa.documents.evidence`);
  - the PDF's properties without noise, and the number of pages;
  - the box's authors whose names appear in the text;
  - the type, category and date-kind vocabularies;
  - the first two pages and the last (from the stored page text, OCR's included), cut evenly when
    long.
- **Classification schema** version 1 (a JSON Schema, also used to check answers):
  - `category`, `type` (from the vocabularies), `title`;
  - `author` {name, evidence, page};
  - `date` {value, precision, kind, evidence, page};
  - `other_dates[]`, `people[]`, `organizations[]`, `tags[]` (at most four), `summary`;
  - `filename_conflicts[]`.
- **Structured output:** an endpoint gets `response_format` with the schema (Chattr's client
  `chat` gains a `response_format` argument). Apple Intelligence gets the schema in its
  instructions: guided generation from a schema in the Swift helper needs the maintainer's Mac,
  and is left for then. Every answer is parsed (code fences allowed) and checked by Caixa against
  the schema; one retry names what was wrong.
- **Evidence:** each quote is checked against the text of the page it cites (or any page when
  none is cited), accents, case and spacing aside. It is stored with the result
  (`document_fields.verified`, migration 7).
- **Recording:** every proposal is a `document_fields` row (source `ai_inference`, its
  evidence, page, verified, `proposed`, the run's id). An `enrich` run records model, provider,
  prompt version 1, schema version 1 and the result. `ai_status` becomes `completed`,
  `needs_review` (no valid answer after the retry) or `failed` (the provider failed). Enriching
  again replaces the earlier run's `ai_inference` rows in place; the history keeps both runs.
  Reconciliation and applying come in ticket 12, summaries and tags in ticket 13.
- **When:** a stage after every PDF import, for documents still `pending`, skipped with a reason
  when no model can be used. Also `documents.enrich` (a job: the pending ones, the ones named, or
  all) and `caixa documents enrich [ids] [--all]`. It can stop and continue, committing each
  document.
- **Tests:** a stand-in endpoint (`tests/stand_in_documents.py`) answers from the fixtures'
  known answers, quoting evidence from the pages it was sent.

### T01: Asking the model and checking its answer

- `caixa/documents/enrich.py`: `provider`, `prepare`, `SCHEMA`, `classify`, `parse_answer`,
  `verify_quote`.
- `tools/chattr/src/chattr/translation.py`: `chat(..., response_format=None)`.
- `caixa/apple_intelligence.py`: `chat` takes and ignores it.
- `caixa/schema.py`: migration 7 (`document_fields.verified`).
- `caixa/settings.py`: `documents.enrich`.
- `tests/stand_in_documents.py`.
- Tests (`tests/test_documents_enrich.py`):
  - a non-local endpoint is refused even with `allow_remote`;
  - Apple first under Automatic (stand-in helper);
  - what is sent holds the filename, properties, first and last pages within the budget;
  - the request carries the schema as `response_format`;
  - a valid answer is parsed, and its evidence verified or not;
  - an answer that is not JSON, or breaks the schema, is retried once with the reason, then
    given up;
  - code fences are accepted.
- Verify: `python -m pytest -q tests/test_documents_enrich.py tests/test_summaries.py tools/chattr/tests/test_translation.py`
- [x] done

### T02: The enrich stage, the job and the command

- `caixa/documents/enrich.py`: `enrich_documents`.
- `caixa/collectors/pdfImport.py`: the stage after import.
- `caixa/documents/records.py`: `verified`, and clearing a run's fields.
- `caixa/service.py`: `documents.enrich` and job kind `documents-enrich`.
- `caixa/cli.py`: `caixa documents enrich`.
- `tests/test_worker_protocol.py`.
- Tests:
  - an import with the stand-in endpoint enriches every readable document (`completed`, fields
    from `ai_inference` with verified evidence, an `enrich` run with model, prompt and schema
    versions);
  - without a model the import succeeds, documents stay `pending`, and a warning says why;
  - a failing provider gives `failed`;
  - enriching again creates no duplicate fields and keeps `user_verified` ones;
  - the job and the command enrich the pending and named documents;
  - the locked document is skipped.
- Verify: `python -m pytest -q tests/test_documents_enrich.py tests/test_pdf_collector.py tests/test_worker_protocol.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:** `caixa/documents/enrich.py` reads each document with the summaries' model:
  - **Provider:** Automatic means Apple Intelligence first; any endpoint not on this computer is
    refused even with `allow_remote`; the new `documents.enrich` setting turns it off.
  - **What is sent:** the filename and what it says, properties without noise, the authors named
    in the text, and the first two pages and the last, within 6,000 or 12,000 characters.
  - **The answer:** classification schema v1, sent as `response_format` to an endpoint (Chattr's
    `chat` gained the argument) and in the instructions for Apple. Caixa checks it, retries once
    naming the problem, and verifies every quote against its page (migration 7:
    `document_fields.verified`).
  - **Recording:** proposals as `ai_inference` fields and an `enrich` run with model, provider and
    prompt and schema versions. `ai_status` becomes completed, needs_review or failed. Reading
    again replaces the model's fields and keeps the owner's.
  - **When:** a stage after each import (locked documents skipped); without a model, documents
    wait and the import says why. After two provider failures in a row it stops and the rest
    wait. Also the `documents.enrich` job and `caixa documents enrich [ids] [--all]`.
  - **Tests:** a stand-in model (`tests/fixtures/stand_in_documents.py`) answers from the
    fixtures' known answers.
- **Files:**
  - new: `caixa/documents/enrich.py`, `tests/test_documents_enrich.py`,
    `tests/fixtures/stand_in_documents.py`;
  - changed: `tools/chattr/src/chattr/translation.py`, `caixa/apple_intelligence.py`,
    `caixa/schema.py`, `caixa/settings.py`, `caixa/documents/records.py` (`verified`,
    `clear_fields`), `caixa/collectors/pdfImport.py`, `caixa/service.py`, `caixa/cli.py`,
    `tests/test_documents_schema.py`, `tests/test_worker_protocol.py`.
- **Errors:** a failing provider made every document wait out its retries (84 s in the test).
  The stage now stops after two failures in a row. Three mypy redefinitions were fixed.
- **Verify:**
  - `python -m pytest -q`: 1818 passed, 1 skipped.
  - vitest: 277 passed; tsc clean.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: 5bbf7a5..694aa2c (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only (one carried to the Mac).

- **Minor (for the Mac):** Apple Intelligence gets the schema in its instructions only. Guided
  generation from a schema in the Swift helper (`DynamicGenerationSchema`) cannot be built or
  tested in this container, and is to be tried on the maintainer's Mac. The benchmark (ticket 14)
  will show whether the prompt-only route is good enough.
- **Minor:** documents are read one at a time, even when the provider could take several at
  once.
- **Minor:** whether a client is an endpoint is told by its `server_name`; a sturdier sign would
  be a type check.
- **Spec:** D12 and D17 met; every acceptance criterion met.
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.enrich`; the stage tests before T02) before
  each GREEN.
- **Commits:** `20261124-10 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
