"""What Caixa remembers between runs, kept in Caixa's own per-user folder (never inside a box).

- the boxes opened lately, newest first, so the next start can offer the last one again;
- for each box, which part of the interface was open and the import wizard's unfinished draft, so
  stopping and starting Caixa picks up where you left off.

It is a convenience, never a requirement: a file that is missing, damaged or cannot be written is
quietly set aside or skipped, and nothing here ever stops Caixa working. The file holds folder paths
and the draft's choices (not messages), and is readable only by its owner. It is separate from the
`serve.json` that `caixa serve` keeps about the running harness.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

RECENT = 10  # boxes kept
DRAFT_LIMIT = 20_000  # bytes of JSON a draft may take


def caixa_home(
    environ: Optional[Mapping[str, str]] = None,
    platform_name: Optional[str] = None,
    home: Optional[Path] = None,
) -> Path:
    """Caixa's per-user folder for the harness and its state (`$CAIXA_HOME` overrides)."""
    env = os.environ if environ is None else environ
    platform = platform_name or sys.platform
    user = home or Path.home()
    if env.get("CAIXA_HOME"):
        return Path(env["CAIXA_HOME"])
    if platform == "darwin":
        return user / "Library" / "Application Support" / "Caixa"
    if platform.startswith("win"):
        return Path(env.get("LOCALAPPDATA") or user / "AppData" / "Local") / "Caixa"
    return Path(env.get("XDG_DATA_HOME") or user / ".local" / "share") / "caixa"


class State:
    """The remembered state in `<home>/state.json`."""

    def __init__(self, home: Path) -> None:
        self.path = Path(home) / "state.json"
        self._lock = threading.Lock()

    @classmethod
    def default(cls) -> "State":
        return cls(caixa_home())

    # --- Reading and writing ----------------------------------------------------------------

    def _read(self) -> dict[str, Any]:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            self._set_aside()
            return {}
        return document if isinstance(document, dict) else {}

    def _set_aside(self) -> None:
        try:
            os.replace(self.path, self.path.with_name(self.path.name + ".damaged"))
        except OSError:
            pass

    def _write(self, document: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(self.path.name + ".part")
            temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            temporary.chmod(0o600)
            os.replace(temporary, self.path)
        except OSError:
            pass  # nothing to save into; remembering is a convenience

    # --- Boxes ------------------------------------------------------------------------------

    def remember_box(self, path: str, name: str) -> None:
        """Note that `path` was opened just now."""
        with self._lock:
            document = self._read()
            recent = [r for r in document.get("recent", []) if r.get("path") != path]
            recent.insert(
                0,
                {
                    "path": path,
                    "name": name,
                    "opened": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
            )
            document["recent"] = recent[:RECENT]
            self._write(document)

    def recent_boxes(self, check: bool = True) -> list[dict[str, Any]]:
        """The boxes opened lately, newest first. With `check`, each says whether it is still there."""
        with self._lock:
            found = [r for r in self._read().get("recent", []) if isinstance(r, dict)]
        listed = [
            {"path": r.get("path", ""), "name": r.get("name", ""), "opened": r.get("opened")}
            for r in found
            if r.get("path")
        ]
        if check:
            for entry in listed:
                entry["exists"] = (Path(entry["path"]) / ".caixa").is_dir()
        return listed

    def last_box(self) -> Optional[str]:
        """The box to reopen: the newest one that is still there."""
        for entry in self.recent_boxes()[:1]:
            if entry["exists"]:
                return str(entry["path"])
        return None

    def forget_box(self, path: str) -> None:
        with self._lock:
            document = self._read()
            document["recent"] = [r for r in document.get("recent", []) if r.get("path") != path]
            document.get("boxes", {}).pop(path, None)
            self._write(document)

    # --- Where you were in a box ------------------------------------------------------------

    def view(self, path: str) -> tuple[Optional[str], Optional[dict[str, Any]]]:
        """The section that was open in the box at `path`, and the unfinished import draft."""
        with self._lock:
            kept = self._read().get("boxes", {}).get(path, {})
        view = kept.get("view")
        draft = kept.get("draft")
        return (view if isinstance(view, str) else None, draft if isinstance(draft, dict) else None)

    _UNSET: Any = object()

    def set_view(self, path: str, view: Any = _UNSET, draft: Any = _UNSET) -> None:
        """Keep the section and/or the draft for a box; `draft=None` clears the draft."""
        if isinstance(draft, dict) and len(json.dumps(draft)) > DRAFT_LIMIT:
            raise ValueError("The draft is too large to keep.")
        with self._lock:
            document = self._read()
            kept = document.setdefault("boxes", {}).setdefault(path, {})
            if view is not State._UNSET:
                kept["view"] = view
            if draft is not State._UNSET:
                if draft is None:
                    kept.pop("draft", None)
                else:
                    kept["draft"] = draft
            self._write(document)
