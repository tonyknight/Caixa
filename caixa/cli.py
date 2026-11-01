"""Command-line entry point for Caixa."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from caixa import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caixa",
        description="Collect, preserve and pass on a digital life.",
    )
    parser.add_argument("--version", action="version", version=f"caixa {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
