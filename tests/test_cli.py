"""Smoke tests for the `caixa` package and its command-line entry point."""

import subprocess
import sys

import caixa


def test_package_exposes_version() -> None:
    assert isinstance(caixa.__version__, str)
    assert caixa.__version__


def test_module_entry_point_prints_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "caixa", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert caixa.__version__ in result.stdout
