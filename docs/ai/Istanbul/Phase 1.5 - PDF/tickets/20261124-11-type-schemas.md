---
id: 20261124-11-type-schemas
title: Type schemas
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: eight type schemas, amounts parsed by Caixa, type fields recorded.'
parent:
depends_on:
- 20261124-10-ai-classification
subtasks: []
plan_status: done
---
## Description

The eight type schemas (statement, cheque, bill, invoice or receipt, insurance, tax, legal agreement, correspondence), asked for after classification, with amounts parsed by Caixa.

## Acceptance criteria

- [x] Each typed fixture gets its type's fields with evidence and page
- [x] Amounts are stored as found and as a number parsed by Caixa

## Context

Phase 1.5 - PDF Tasks Breakdown item 11. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Enrichment* (Type schemas); D12.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/documents/types.py` holds the eight type schemas (version 1). Each field is
`{value, evidence, page}`, or a list of them for parties:

| Type | Fields |
| --- | --- |
| statement | institution, account_type, account_suffix, period_start, period_end, opening_balance, closing_balance |
| cheque | number, date, payee, amount |
| bill | provider, service_address, period_start, period_end, amount_due, due_date |
| invoice | vendor, number, date, total |
| insurance | insurer, policy_number, coverage_start, coverage_end |
| tax | issuer, tax_year, form |
| agreement | parties, subject, execution_date |
| correspondence | sender, recipient, date, subject |

- `AMOUNTS` names the fields that are money. `parse_amount` reads them the way people write them
  (`2,310.55`, `2.104,33`, `23,40`, `450.00`, `€ 1 200,00`); the model never computes a number.
- `enrich.ask` is the question-and-check loop that classification uses, now shared: one retry
  naming what was wrong.
- `classify_type(client, document, type, budget)` asks for a type's fields after classification,
  with the same pages, verifies each quote, and adds the parsed number for amounts.
- `enrich_documents` asks for them when the type has a schema, and records each field as
  `ai_inference` with evidence, page, verified and the number. A failed second question does not
  undo the classification; the run's report says so.
- The stand-in model answers type questions from the fixtures' fields.

### T01: Type schemas and amounts

- `caixa/documents/types.py` (`TYPE_SCHEMAS`, `AMOUNTS`, `parse_amount`, `type_problems`).
- Tests (`tests/test_documents_types.py`):
  - every type has a schema of its fields;
  - amounts in English and Portuguese writing, with a currency or none;
  - what is not an amount gives None;
  - answers that break a type's schema are named.
- Verify: `python -m pytest -q tests/test_documents_types.py`
- [x] done

### T02: Asking for a type's fields

- `caixa/documents/enrich.py` (`ask`, `classify_type`, the stage).
- `tests/fixtures/stand_in_documents.py` (type answers).
- Tests:
  - the statement's institution, suffix and balances, with numbers 2310.55 and 1987.2;
  - the electricity bill's provider and amount due 88.15;
  - the invoice's number and total;
  - the tax document's tax year;
  - evidence verified;
  - a type without a schema (medical) asks nothing more;
  - a type answer never valid leaves the classification completed and is noted in the run.
- Verify: `python -m pytest -q tests/test_documents_types.py tests/test_documents_enrich.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:** `caixa/documents/types.py` holds the eight type schemas (version 1), the money
  fields, and `parse_amount`, which reads amounts as people write them (`2,310.55`, `2.104,33`,
  `23,40`, `€ 1 200,00`). `enrich.ask` is now the shared question-and-check loop.
  `classify_type` asks for a type's fields after classification, verifies each quote, and gives
  amounts Caixa's number. The stage records them as `ai_inference` fields with evidence, page,
  verified and number. A failed type question leaves the classification completed and is noted
  in the run (`type_error`). The stand-in model answers type questions from the fixtures' fields.
- **Files:**
  - new: `caixa/documents/types.py`, `tests/test_documents_types.py`;
  - changed: `caixa/documents/enrich.py`, `tests/fixtures/stand_in_documents.py`.
- **Errors:** none.
- **Verify:**
  - `python -m pytest -q`: 1841 passed, 1 skipped.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: 2057e80..9a2c89e (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** `parse_amount` reads `1.200` (no cents) as 1200, and `1.20` as 1.20, as the writing
  usually means. A three-decimal currency would be misread; none is expected here.
- **Minor:** a type's fields take a second request per document, which doubles the model's time
  for typed documents.
- **Spec:** D12 (type schemas, amounts by Caixa) met; every acceptance criterion met.
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.types`; four stage tests failing before
  T02) before each GREEN.
- **Commits:** `20261124-11 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
