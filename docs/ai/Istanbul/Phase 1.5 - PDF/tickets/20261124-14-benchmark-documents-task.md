---
id: 20261124-14-benchmark-documents-task
title: Benchmark documents task
type: feature
priority: medium
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-11-type-schemas
- 20261124-12-reconciliation-confidence-and-apply
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

A documents task in `caixa benchmark`: the fixtures enriched by Apple Intelligence and by an endpoint, timed and scored against the known answers.

## Acceptance criteria

- [ ] `caixa benchmark` reports time and accuracy (type, author, date, title) for each provider
- [ ] Nothing from a box is sent; the synthetic PDFs only

## Context

Phase 1.5 - PDF Tasks Breakdown item 14. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Benchmark); D18.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:**

- **The documents:** `tools/ai-benchmark/documents.json`, beside `emails.json`, holds the
  synthetic PDF family's twelve documents as a model is given them: file name, properties, the
  text of each page (a scan's as OCR would read it), and the known answers (type, title, author,
  date). It is written by `pdf_family.benchmark_documents()`; a test checks the committed file
  still matches, so it cannot drift from the fixtures.
- **The task:** `caixa benchmark` gains a `documents` task.
  - Each document is a `DocumentInput`, read with `enrich.classify` and, for a typed document,
    `classify_type`, exactly as an import does, within each side's budget, and timed per worker
    count like the other tasks.
  - Each row adds accuracy against the known answers: type (exact), author (the same name,
    accents and case aside, or one containing the other), date (exact value), title (at least
    half its words in common), and how many quotes were verified.
  - The report gains a documents section, and the verdict names the more accurate side as well
    as the faster.
  - `--tasks` takes `documents`; the default runs all three.
- Nothing from a box is sent: only the synthetic documents.

### T01: The documents and the scoring

- `tests/fixtures/pdf_family.py` (`benchmark_documents`).
- `tools/ai-benchmark/documents.json`, `tools/ai-benchmark/README.md`.
- `caixa/benchmark.py` (`load_documents`, `score`).
- Tests (`tests/test_benchmark.py`):
  - the committed file matches the fixtures;
  - twelve documents with their answers;
  - scoring right, wrong and partial answers.
- Verify: `python -m pytest -q tests/test_benchmark.py`
- [x] done

### T02: The documents task in the run and the report

- `caixa/benchmark.py`, `caixa/cli.py`.
- Tests:
  - a run with the stand-in model times the documents task at each worker count and scores it
    (all right with the stand-in);
  - a model that answers prose scores nothing and counts as failed;
  - the report and the verdict name accuracy;
  - `caixa benchmark --tasks documents --only endpoint` writes the report.
- Verify: `python -m pytest -q tests/test_benchmark.py && python -m mypy --python-version 3.12 caixa`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
