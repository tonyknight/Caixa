---
id: 20261125-01-declare-numpy-and-check-every-import-is-declared
title: "Declare numpy, and check every import is declared"
type: bug
priority: high
status: todo
created: 2026-11-25
updated: 2026-11-25
closed:
notes: "Hot fix: numpy is used by validation, embeddings, search and Ask but not declared"
parent:
depends_on: []
subtasks:
- id: T01
  title: numpy declared, imports checked, doctor and the import check packages first
  status: todo
plan_status: draft
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

**Why it failed twice:**

1. The first failure was validation, the first numpy use, which runs in the worker processes as
   soon as a scanned page has been OCR'd.
2. The second came after filing (files were in the box), so the reading stages had begun. The
   next numpy use in that order is `embed_documents`, which imports numpy before anything else.
   It runs in the long-lived `caixa serve` process, and only when an embedding model is set.
   This also explains the other symptoms: drawing the document pages comes after embedding and
   never ran, so the window showed nothing finished.

   Why numpy was still missing there needs the traceback from `.caixa/logs/job-<N>.log` and
   `caixa doctor`'s output. The likeliest explanation is that `caixa serve` runs under a
   different Python from the `pip` that installed numpy, or was started before it was installed.

**This ticket:** declare what Caixa imports, prove it with a test, and say plainly (in
`caixa doctor` and before an import reads its first file) when a package is missing from the
Python that Caixa actually runs. That turns a failure an hour in into one at second zero.

Surviving a failure partway through a long run is a separate ticket (to plan).

## Acceptance criteria

- [ ] `numpy` and `jinja2` are in `[project] dependencies`; `pikepdf` is in the `[ocr]` extra
      beside `ocrmypdf`.
- [ ] A test scans every import in `caixa/` (including those inside functions) and fails on a
      third-party module that is not declared, or that is optional but not imported under
      `except ImportError`.
- [ ] `caixa doctor` lists the Python packages Caixa needs, each with its version, or *missing*
      with the exact command for this Python (`<sys.executable> -m pip install …`). It lists the
      optional ones separately.
- [ ] A PDF import (window and command line) checks that the packages it needs load in this
      Python before it reads any file, and otherwise stops at once with the same message.
- [ ] The completion's testing guide says to run `tools/install.sh` again after pulling, so the
      new dependencies are installed.

## Context

- `pyproject.toml`; `caixa/diagnostics.py` (`report`, which already prints
  `python … at {sys.executable}`); `caixa/collectors/pdfImport.py` (`preview`, `run`);
  `caixa/documents/pdf/validate.py`, `embeddings.py`, `search.py`, `ask.py`.
- `tools/install.sh` installs from `pyproject.toml`, so it needs no change of its own.
- Requirements: D17 (OCR optional), D27 (doctor reports the PDF tools).
- Found in the maintainer's first real import (2026-11-25).

## Subtasks

- [ ] T01 numpy declared, imports checked, doctor and the import check packages first

## Implementation plan

Status: draft
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

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

- 2026-11-25: Planned from the maintainer's first real import. Waiting for the maintainer's yes
  on the plan.
