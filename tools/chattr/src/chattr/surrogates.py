"""Text a source's declared encoding could not explain, made safe to store.

Python's mail parser (and `errors="surrogateescape"` decoding generally) keeps each byte it could
not decode as a stand-in character between U+DC80 and U+DCFF. SQLite and UTF-8 refuse those, so
one such byte would stop an import. Each run of them is turned back into its bytes and decoded as
UTF-8, else Windows-1252 (an old client's undeclared "ñ" is 0xF1); a byte neither explains becomes
"�" (U+FFFD).
"""

from __future__ import annotations

import dataclasses
import re
from typing import TypeVar

_STAND_INS = re.compile("[\udc80-\udcff]+")
_SURROGATES = re.compile("[\ud800-\udfff]")

T = TypeVar("T")


def _recover(match: re.Match[str]) -> str:
    data = bytes(ord(c) - 0xDC00 for c in match.group())
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def repair_text(value: str) -> str:
    """`value` with every stand-in character recovered or replaced by "�"."""
    if not _SURROGATES.search(value):
        return value
    # Any other lone surrogate (not a stand-in for a byte) cannot be stored either.
    return _SURROGATES.sub("\ufffd", _STAND_INS.sub(_recover, value))


def repair(value: T) -> T:
    """`value` with `repair_text` applied to every string in it.

    Reaches through dicts, lists, tuples and dataclass instances (a new instance when something
    changed); anything else is returned as it is.
    """
    if isinstance(value, str):
        return repair_text(value)  # type: ignore[return-value]
    if isinstance(value, dict):
        return {repair(k): repair(v) for k, v in value.items()}  # type: ignore[return-value]
    if isinstance(value, list):
        return [repair(v) for v in value]  # type: ignore[return-value]
    if isinstance(value, tuple) and not hasattr(value, "_fields"):
        return tuple(repair(v) for v in value)  # type: ignore[return-value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        changes = {}
        for field in dataclasses.fields(value):
            if not field.init:
                continue
            current = getattr(value, field.name)
            fixed = repair(current)
            if fixed is not current and fixed != current:
                changes[field.name] = fixed
        return dataclasses.replace(value, **changes) if changes else value  # type: ignore
    return value
