---
id: 20261125-01-hot-fix-the-pdf-collector-missing-from-the-import
title: 'Hot fix: the PDF collector missing from the import wizard'
type: bug
priority: high
status: done
created: 2026-11-25
updated: 2026-11-25
closed: 2026-11-25
notes: Own collectors load from a stale install; doctor tells why
parent:
depends_on: []
subtasks: []
plan_status: done
current_task: T01
---
## Description

The maintainer found no PDF documents card in the import wizard. Collectors are found through
the `caixa.collectors` entry points, which pip writes into the package's metadata when Caixa is
installed; they are not read from `pyproject.toml` at run time. A checkout updated with
`git pull`, but installed before the `pdf` entry point existed, keeps the old list. The six
message collectors show, and PDF documents does not. Nothing says why: a collector that fails to
load is recorded in the registry's `problems`, which nothing shows.

Reproduced: `discover()` given only the `chattr` entry point, as such an install has, lists the
six message collectors and no `pdf`.

## Acceptance criteria

- [x] Caixa's own collectors (`chattr`, `pdf`) are loaded even when the installed metadata does
      not name them; an entry point of the same name still takes precedence, and nothing is
      loaded twice.
- [x] `caixa doctor` lists the collectors found, says when Caixa's own were missing from the
      install (re-run `./tools/install.sh` or `pip install -e`), and names any that failed to load.
- [x] `caixa collectors` says on standard error when a collector failed to load.

## Context

Hot fix after Phase 1.5 - PDF's board (the maintainer's first look). Requirements: *Components*
(the collector), D27 (documentation).

## Subtasks

## Implementation plan

Status: done
Current task: T01

**Design:** `caixa/collectors/registry.py` gains `BUILT_IN = {"chattr": …, "pdf": …}`.
`discover()` (with no `plugins` given) adds an entry point for each built-in name the installed
metadata lacks, and records it in `registry.fallbacks`. `caixa/diagnostics.py` gains a
*Collectors* section: each collector's id and where it came from, the fallbacks with what to run,
and the problems. `caixa collectors` prints the problems to standard error.

### T01: Caixa's own collectors always load, and problems are told

- `caixa/collectors/registry.py`, `caixa/diagnostics.py`, `caixa/cli.py`.
- Tests (`tests/test_collector_contract.py`): a stale install (only `chattr` installed) still
  lists `pdf` and records the fallback; an installed `pdf` entry point is used rather than the
  built-in, and no id comes twice; doctor's report names the fallback and a broken collector;
  `caixa collectors` prints a broken collector's problem to standard error.
- Verify: `python -m pytest -q tests/test_collector_contract.py tests/test_pdf_collector.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:**
  - **Built-in collectors:** `discover()` loads Caixa's own collectors (`chattr`, `pdf`) even when
    the installed metadata lacks them, and notes each such fallback. An installed entry point of
    the same name still comes first, and no collector is loaded twice. An install from before
    this branch now shows **PDF documents** in the wizard.
  - **Problems are told:** `caixa doctor` has a *Collectors* section: the collectors found, any
    fallback with what to run (`./tools/install.sh`, or `pip install -e`), and any collector that
    could not load. `caixa collectors` prints load failures to standard error.
  - **Also fixed:** three Chattr attachment tests failed once ExifTool was installed with apt,
    because their guard kept `/usr/bin` on `PATH`. They now find only an exiftool the test made
    itself. (This showed up after `tools/install.sh` installed ExifTool in the container.)
- **Files:** `caixa/collectors/registry.py`, `caixa/diagnostics.py`, `caixa/cli.py`,
  `tests/test_collector_contract.py`, `tools/chattr/tests/test_attachment_pipeline.py`.
- **Errors:** none in the fix.
- **Verify:**
  - `python -m pytest -q`: 1996 passed, 1 skipped.
  - Chattr: 916 passed.
  - vitest: 285 passed.
  - mypy: the 8 baseline errors.

## Review

### 2026-11-25: reviewed in-session

**Verdict:** clean.

- **Spec:** every acceptance criterion met.
- **TDD:** RED (`discover() got an unexpected keyword argument 'built_in'`; no *Collectors*
  section) before GREEN.
- **Minor:** the window still does not list load failures; `caixa doctor` and `caixa collectors`
  do.

## Notes

Append-only running log. Each entry dated.
