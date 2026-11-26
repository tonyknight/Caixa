"""The Python packages Caixa imports, and whether the Python running it has them.

`REQUIRED` and `OPTIONAL` map each third-party module Caixa imports to the package that brings it
(a test holds them to `pyproject.toml`). `check` stops a task before it starts when a required one
is missing, naming the command that installs it for *this* Python: a package installed with
another Python's `pip` is invisible to Caixa, and an import found missing an hour in loses the
hour.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import sys
from typing import Optional, Sequence

from caixa.collectors.inputs import InputError

#: Module → package, for those Caixa cannot work without.
REQUIRED = {"jinja2": "jinja2", "numpy": "numpy", "pymupdf": "pymupdf"}
#: Module → package, for those Caixa works without, with less (`pip install "caixa[ocr]"`).
OPTIONAL = {"ocrmypdf": "ocrmypdf", "pikepdf": "pikepdf"}
#: What each optional package is for.
PURPOSE = {
    "ocrmypdf": "making scanned PDFs searchable",
    "pikepdf": "a second check of every OCR'd PDF",
}


def _found(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def version(module: str) -> Optional[str]:
    """The installed version of the package bringing `module`, or None when it is missing."""
    if not _found(module):
        return None
    package = REQUIRED.get(module) or OPTIONAL.get(module) or module
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "installed"


def install_command(modules: Sequence[str]) -> str:
    packages = [REQUIRED.get(m) or OPTIONAL.get(m) or m for m in modules]
    return f"{sys.executable} -m pip install {' '.join(packages)}"


def missing(modules: Sequence[str] = tuple(REQUIRED)) -> list[str]:
    return [module for module in modules if not _found(module)]


def check(task: str, modules: Sequence[str] = tuple(REQUIRED)) -> None:
    """Raise `InputError` when a module `task` needs cannot be imported by this Python."""
    absent = missing(modules)
    if not absent:
        return
    raise InputError(
        f"Caixa cannot {task}: {', '.join(absent)} "
        f"{'is' if len(absent) == 1 else 'are'} missing from the Python it runs on.",
        [
            f"Install with: {install_command(absent)}",
            "or run tools/install.sh again from Caixa's folder.",
        ],
    )


def report() -> list[str]:
    """Lines for `caixa doctor`: each required package and its version, then the optional ones."""
    lines = []
    for module in REQUIRED:
        found = version(module)
        lines.append(
            f"{module} {found}" if found else f"{module}: missing ({install_command([module])})"
        )
    for module in OPTIONAL:
        found = version(module)
        state = found if found else "not installed"
        lines.append(f"{module} {state} (optional: {PURPOSE[module]})")
    return lines


__all__ = ["OPTIONAL", "REQUIRED", "check", "install_command", "missing", "report", "version"]
