---
id: 20261124-11-type-schemas
title: Type schemas
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-10-ai-classification
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

The eight type schemas (statement, cheque, bill, invoice or receipt, insurance, tax, legal agreement, correspondence), asked for after classification, with amounts parsed by Caixa.

## Acceptance criteria

- [ ] Each typed fixture gets its type's fields with evidence and page
- [ ] Amounts are stored as found and as a number parsed by Caixa

## Context

Phase 1.5 - PDF Tasks Breakdown item 11. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Enrichment* (Type schemas); D12.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

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
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
