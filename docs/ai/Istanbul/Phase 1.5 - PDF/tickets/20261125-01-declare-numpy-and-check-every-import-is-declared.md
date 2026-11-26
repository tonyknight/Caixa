---
id: 20261125-01-declare-numpy-and-check-every-import-is-declared
title: Declare numpy, and check every import is declared
type: bug
priority: high
status: done
created: 2026-11-25
updated: 2026-11-25
closed: 2026-11-25
notes: numpy and jinja2 declared; imports checked; doctor and the import check packages
parent:
depends_on: []
subtasks:
- id: T01
  title: numpy declared, imports checked, doctor and the import check packages first
  status: done
plan_status: done
---
## Description

The maintainer's first real PDF import on the Mac stopped at once with
`ModuleNotFoundError: No module named 'numpy'`. After `pip install numpy` it ran for about an
hour, filed about 150 PDFs, and stopped again with the same error.

**Cause:** Caixa uses numpy in four places but never declares it, so neither `pip install -e .`
nor `tools/install.sh` installs it. The development container had numpy from other packages, so
no test noticed. A scan of every import in `caixa/` (including imports inside functions) found:

| Module | Used in | Declared |
| --- | --- | --- |
| `numpy` | `documents/pdf/validate.py` (comparing renders), `documents/embeddings.py`, `documents/search.py`, `documents/ask.py` | **no** |
| `jinja2` | `documents/pages.py` | only through Chattr |
| `pymupdf` | collector, inspection, OCR, validation | yes |
| `ocrmypdf`, `pikepdf` | OCR, validation | optional (`[ocr]`); their absence is handled |

**The two failures:**

1. The first was numpy: validation (its first use) runs in the worker processes as soon as a
   scanned page has been OCR'd.
2. The second, an hour in, was **not** numpy. The job log shows a `TypeError` in
   `enrich.verify_quote`: a model answered an author's `evidence` with a list. That is
   `20261125-03`.

**This ticket:** declare what Caixa imports, prove it with a test, and say plainly (in
`caixa doctor` and before an import reads its first file) when a package is missing from the
Python that Caixa actually runs. That turns a failure an hour in into one at second zero.

Surviving a failure partway through a long run is `20261125-03`.

## Acceptance criteria

- [x] `numpy` and `jinja2` are in `[project] dependencies`; `pikepdf` is in the `[ocr]` extra
      beside `ocrmypdf`.
- [x] A test scans every import in `caixa/` (including those inside functions) and fails on a
      third-party module that is not declared, or that is optional but not imported under
      `except ImportError`.
- [x] `caixa doctor` lists the Python packages Caixa needs, each with its version, or *missing*
      with the exact command for this Python (`<sys.executable> -m pip install …`). It lists the
      optional ones separately.
- [x] A PDF import (window and command line) checks that the packages it needs load in this
      Python before it reads any file, and otherwise stops at once with the same message.
- [x] The completion's testing guide says to run `tools/install.sh` again after pulling, so the
      new dependencies are installed.

## Context

- `pyproject.toml`; `caixa/diagnostics.py` (`report`, which already prints
  `python … at {sys.executable}`); `caixa/collectors/pdfImport.py` (`preview`, `run`);
  `caixa/documents/pdf/validate.py`, `embeddings.py`, `search.py`, `ask.py`.
- `tools/install.sh` installs from `pyproject.toml`, so it needs no change of its own.
- Requirements: D17 (OCR optional), D27 (doctor reports the PDF tools).
- Found in the maintainer's first real import (2026-11-25).

## Subtasks

- [x] T01 numpy declared, imports checked, doctor and the import check packages first

## Implementation plan

Status: done
Current task: 

### T01: numpy declared, imports checked, doctor and the import check packages first

- **Files:** `pyproject.toml`; `caixa/diagnostics.py`; `caixa/collectors/pdfImport.py`; a small
  `caixa/requirements.py` (`REQUIRED = {"numpy": "numpy", "pymupdf": "pymupdf", "jinja2":
  "jinja2"}`, `OPTIONAL = {"ocrmypdf": "ocrmypdf", "pikepdf": "pikepdf"}` mapping import names to
  distributions, and `missing(names) -> list[str]` using `importlib.util.find_spec`);
  `tests/test_dependencies.py` (new); `tests/test_diagnostics.py`; `tests/test_pdf_collector.py`.
- **RED:**
  - `test_dependencies.py` scans `caixa/**/*.py` with `ast`, keeping imports that are neither
    standard library (`sys.stdlib_module_names`), `caixa` nor `chattr`. Each must be declared in
    `pyproject.toml`'s dependencies, or in an extra *and* inside a `try` that catches
    `ImportError`. It fails today on numpy and jinja2.
  - A doctor test with `find_spec` patched to report numpy missing expects a *missing* line
    naming `sys.executable -m pip install numpy`.
  - A collector test with numpy reported missing expects `run` and `preview` to raise
    `InputError` before `locate` is called.
- **GREEN:**
  - Add `numpy>=1.24` and `jinja2>=3.0` to dependencies and `pikepdf>=8` to `[ocr]`.
  - `caixa/requirements.py` as above.
  - Doctor gets a *Python packages* section (required, then optional, with versions from
    `importlib.metadata`).
  - `PdfCollector.preview` and `run` call `requirements.missing(...)` first.
- **Verify:** `python -m pytest -q tests/test_dependencies.py tests/test_diagnostics.py
  tests/test_pdf_collector.py`, then the project verify command:
  `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`.
- [x] done
## Completion report

- **Outcome:**
  - numpy and jinja2 are declared, and pikepdf is in `[ocr]`.
  - `tests/test_dependencies.py` reads every import in `caixa/` (inside functions too), and
    fails on one that `caixa.requirements` and `pyproject.toml` do not account for.
  - `caixa doctor` has a *Python packages* section, e.g. `numpy 2.5.5`, or
    `numpy: missing (/…/.venv/bin/python -m pip install numpy)`; optional packages are listed
    with what they are for.
  - A PDF preview or import checks the packages before looking for a file, and stops with
    "Caixa cannot read PDFs: numpy is missing from the Python it runs on." and the command.
  - The testing guide now installs with `tools/install.sh` and says to run it after every pull.
- **Files:** `pyproject.toml`; `caixa/requirements.py` (new); `caixa/diagnostics.py`;
  `caixa/collectors/pdfImport.py`; `tests/test_dependencies.py` (new),
  `tests/test_diagnostics.py`, `tests/test_pdf_collector.py`; the completion's testing guide.
- **Errors:**
  - RED as planned: `caixa.requirements` was missing, numpy was not declared, and the doctor
    had no packages section.
  - The suite in a fresh container showed 12 Chattr failures that this ticket does not touch.
    10 fail the same way on the unchanged branch (the attachment pipeline with ExifTool
    installed, and the web convert tests). `test_serve_command` waits for ever when
    `PYTHONUNBUFFERED` is not set: `chattr serve` prints its link without flushing, and it
    passes with the variable set. `test_imessage_attachments` fails only after other tests,
    and passes on its own.
  - black 26.10 (newer than the project's) also flags the untouched
    `tests/test_mail_sent_and_received.py`.
- **Verify:**
  - `python -m pytest -q tests/test_dependencies.py tests/test_diagnostics.py tests/test_pdf_collector.py`:
    37 passed.
  - Full suite: 1988 passed, 12 failed (the Chattr tests above).
  - mypy: the 8 errors of the baseline.
  - black: clean on every changed file.
  - web: `tsc` clean; vitest 285 passed, the end-to-end tests in Chromium included.

### Review

2026-11-25, in session. Clean. The diff matches the plan's files. `requirements.check` runs
before `locate` in both `preview` and `run`. The import scan's optional rule ("one guarded
import per file") fits `ocr.py`, which checks `tools()` before its second import.

## Notes

Append-only running log. Each entry dated.

- 2026-11-25: Planned from the maintainer's first real import. Waiting for the maintainer's yes
  on the plan.
- 2026-11-25: Approved by the maintainer. The job log showed the second failure was a model's
  answer, not numpy (`20261125-03`); the diagnosis above is corrected.
