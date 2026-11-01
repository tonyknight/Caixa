---
id: 20261101-01-caixa-repository-foundations
title: Caixa repository foundations
type: chore
priority: high
status: in-progress
created: 2026-11-01
updated: 2026-11-01
closed:
notes: Breakdown item 1.
parent:
depends_on: []
subtasks: []
plan_status: in-progress
current_task: T02
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

Status: in-progress
Current task: T02

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
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
