"""Every package Caixa imports is declared (ticket 20261125-04).

numpy was imported by validation, embeddings, search and Ask but declared nowhere, so a fresh
install could not import a scanned PDF. This test reads every import in `caixa/`, including those
inside functions, and checks each third-party one against `pyproject.toml` and
`caixa.requirements`.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

from caixa import requirements

tomllib = pytest.importorskip("tomllib")

ROOT = Path(__file__).resolve().parents[1]
FIRST_PARTY = {"caixa", "chattr", "__future__"}


def _project() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _names(specs: list[str]) -> set[str]:
    return {re.split(r"[<>=!~\[; ]", spec, maxsplit=1)[0].strip().lower() for spec in specs}


def _guarded(node: ast.Try) -> bool:
    for handler in node.handlers:
        caught = handler.type
        names = caught.elts if isinstance(caught, ast.Tuple) else [caught]
        if any(
            isinstance(n, ast.Name) and n.id in ("ImportError", "ModuleNotFoundError")
            for n in names
        ):
            return True
    return False


def _imports() -> dict[str, dict[Path, bool]]:
    """Each third-party module: the files importing it, and whether one import there is guarded
    by `except ImportError`."""
    found: dict[str, dict[Path, bool]] = {}
    for path in sorted((ROOT / "caixa").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        guarded_nodes = {
            id(inner)
            for node in ast.walk(tree)
            if isinstance(node, ast.Try) and _guarded(node)
            for statement in node.body
            for inner in ast.walk(statement)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                top = module.split(".")[0]
                if top in sys.stdlib_module_names or top in FIRST_PARTY:
                    continue
                files = found.setdefault(top, {})
                files[path] = files.get(path, False) or id(node) in guarded_nodes
    return found


def test_numpy_is_a_dependency() -> None:
    assert "numpy" in _names(_project()["dependencies"])


def test_every_third_party_import_is_known_to_caixa() -> None:
    known = set(requirements.REQUIRED) | set(requirements.OPTIONAL)
    unknown = sorted(set(_imports()) - known)
    assert not unknown, f"imported but not in caixa.requirements: {unknown}"


def test_required_packages_are_dependencies() -> None:
    declared = _names(_project()["dependencies"])
    missing = sorted(d for d in requirements.REQUIRED.values() if d.lower() not in declared)
    assert not missing, f"required but not in [project] dependencies: {missing}"


def test_optional_packages_are_in_an_extra_and_imported_with_care() -> None:
    extras = set().union(*(_names(specs) for specs in _project()["optional-dependencies"].values()))
    imports = _imports()
    for module, distribution in requirements.OPTIONAL.items():
        assert distribution.lower() in extras, f"{distribution} is in no extra"
        for path, guarded in imports.get(module, {}).items():
            assert guarded, f"{path.name} never imports {module} under `except ImportError`"
