---
id: 20261101-01-caixa-repository-foundations
title: Caixa repository foundations
type: chore
priority: high
status: todo
created: 2026-11-01
updated: 2026-11-01
closed: null
notes: Breakdown item 1.
parent: null
depends_on: []
subtasks: []
---

## Description

Create the Python project skeleton for `caixa/` with packaging, and set up the project's test, format and type-check tooling.

## Acceptance criteria

- [ ] `pyproject.toml` defines the `caixa` package (Python >= 3.10) with a `caixa` console script
- [ ] `python -m pytest -q` runs and passes (at least one smoke test)
- [ ] `python -m black --check .` and `python -m mypy caixa` are clean
- [ ] `.gitignore` covers Python build/test artifacts, generated boxes and databases

## Context

Phase1-Collector Tasks Breakdown item 1. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Testing requirements; Components (`caixa/`).

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
