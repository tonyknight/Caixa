---
id: 20261101-01-caixa-repository-foundations
title: Caixa repository foundations
type: chore
priority: high
status: done
created: 2026-11-01
updated: 2026-11-01
closed: 2026-11-01
notes: 'Done: package skeleton, caixa CLI, pytest/black/mypy, .gitignore.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

Create the Python project skeleton for `caixa/` with packaging, and set up the project's test, format and type-check tooling.

## Acceptance criteria

- [x] `pyproject.toml` defines the `caixa` package (Python >= 3.10) with a `caixa` console script
- [x] `python -m pytest -q` runs and passes (at least one smoke test)
- [x] `python -m black --check .` and `python -m mypy caixa` are clean
- [x] `.gitignore` covers Python build/test artifacts, generated boxes and databases

## Context

Phase1-Collector Tasks Breakdown item 1. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Testing requirements; Components (`caixa/`).

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

Minimum Python follows the Requirements proposal (3.10). The development environment runs 3.13.

### T01: Package skeleton with a `caixa` console script

- Files: `pyproject.toml`, `caixa/__init__.py` (`__version__`), `caixa/__main__.py`,
  `caixa/cli.py` (argparse `main()` with `--version`), `tests/test_cli.py`.
- RED: `tests/test_cli.py` asserts `caixa.__version__` exists and that
  `python -m caixa --version` prints it and exits 0; fails before the package exists.
- GREEN: setuptools project `caixa`, `requires-python = ">=3.10"`, console script
  `caixa = "caixa.cli:main"`, dev extra (`pytest`, `black`, `mypy`); `pip install -e '.[dev]'`.
- Verify: `python -m pytest -q`
- [x] done

### T02: Format, type-check and ignore rules

- Files: `pyproject.toml` (`[tool.black]`, `[tool.mypy]` strict for `caixa`,
  `[tool.pytest.ini_options]`), `.gitignore`.
- `.gitignore`: Python artifacts (`__pycache__/`, `*.egg-info/`, `.mypy_cache/`,
  `.pytest_cache/`, `build/`, `dist/`, `.venv/`), generated boxes and databases (`*.db`,
  `*.sqlite`, `*.sqlite3`), secrets (`.env`).
- Verify: `python -m black --check . && python -m mypy caixa && python -m pytest -q`
- [x] done

## Review

2026-11-01. Commits `66b3681` (T01) and `aeabfbf` (T02). **Verdict: clean, minors only.**
- Spec: all four acceptance criteria met. The files touched match the plan.
- TDD: T01 went RED (`ModuleNotFoundError: caixa`), then GREEN (2 passed). T02 is a config task
  (exception noted).
- Commits use `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.
- **Minor:** the version is declared in both `pyproject.toml` and `caixa/__init__.py`. Consider a
  single source (dynamic version) when packaging matures.
- **Minor:** box folders have no fixed name, so `.gitignore` can't match generated boxes by
  pattern. Their databases (`*.db`, `*.sqlite*`) are covered.

## Completion report

- **Outcome:** `caixa` package skeleton with a `caixa` console script (`--version`); dev tooling
  (pytest, black, strict mypy) configured; `.gitignore` added.
- **Files:** `pyproject.toml`, `caixa/__init__.py`, `caixa/__main__.py`, `caixa/cli.py`,
  `tests/test_cli.py`, `.gitignore`.
- **Errors:** none.
- **Verify:** `python -m pytest -q` → 2 passed; `python -m black --check .` → clean;
  `python -m mypy caixa` → no issues.

## Notes

Append-only running log. Each entry dated.

### 2026-11-01
T02 is pure configuration (black, mypy, pytest settings, .gitignore); per bora-tdd the config exception applies, so the Verify command was the gate: black --check clean, mypy strict clean, 2 tests pass.
