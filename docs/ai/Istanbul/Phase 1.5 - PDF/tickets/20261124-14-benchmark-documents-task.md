---
id: 20261124-14-benchmark-documents-task
title: Benchmark documents task
type: feature
priority: medium
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: documents task in caixa benchmark, scored against known answers.'
parent:
depends_on:
- 20261124-11-type-schemas
- 20261124-12-reconciliation-confidence-and-apply
subtasks: []
plan_status: done
---
## Description

A documents task in `caixa benchmark`: the fixtures enriched by Apple Intelligence and by an endpoint, timed and scored against the known answers.

## Acceptance criteria

- [x] `caixa benchmark` reports time and accuracy (type, author, date, title) for each provider
- [x] Nothing from a box is sent; the synthetic PDFs only

## Context

Phase 1.5 - PDF Tasks Breakdown item 14. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Benchmark); D18.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

## Completion report

- **Outcome:** `caixa benchmark` gains a `documents` task. Twelve synthetic documents
  (`tools/ai-benchmark/documents.json`, written from the fixtures and checked against them by a
  test) are read exactly as an import reads them: classification, then the type's fields. They
  are timed per worker count and scored for type, author, date and title, with verified quotes
  counted. The report has a documents table, and the verdict names the more accurate side as
  well as the faster. The default `--tasks` runs all three. Also `enrich.ask` now tells an
  endpoint from Apple Intelligence by its client's type, not its name.
- **Files:**
  - new: `tools/ai-benchmark/documents.json`;
  - changed: `caixa/benchmark.py`, `caixa/cli.py`, `caixa/documents/enrich.py`,
    `tools/ai-benchmark/README.md`, `tests/fixtures/pdf_family.py` (`benchmark_documents`),
    `tests/fixtures/stand_in_documents.py`, `tests/test_benchmark.py`.
- **Errors:**
  - The stand-in model crashed on the warm-up request, which has no system message; fixed.
  - The existing run test now names its two tasks.
- **Verify:**
  - `python -m pytest -q`: 1898 passed, 1 skipped.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: d6f0b7e..977fc21 (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only (one for the Mac).

- **Minor (for the Mac):** only the stand-in was scored here. Running `caixa benchmark --tasks
  documents` with Apple Intelligence and with the maintainer's endpoint is the real comparison
  the draft asks for, and its report should be kept with the completion.
- **Minor:** the documents' pages hold their written lines (as OCR would read a clean scan), so
  the benchmark does not measure OCR errors.
- **Spec:** D18 met; every acceptance criterion met.
- **TDD:** RED (5 failing; then 3 run tests failing) before each GREEN.
- **Commits:** `20261124-14 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
