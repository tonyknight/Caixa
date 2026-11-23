"""A box: the folder a person's archive lives in.

    <Box name>/
      README.md            plain language: what this is, and how to use it with or without Caixa
      People/  Groups/                 the generated, durable files
      Inbox/               drop exports here for Caixa to import
      .caixa/
        caixa.sqlite       the master database
        work/<collector>/  each collector's working files (Chattr's root, …)
        logs/
        box.yaml           the box's own settings (written as JSON, which is valid YAML)

The user's data lives at the top level; Caixa's working files stay inside `.caixa/`, so a box is
useful without Caixa.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Union

from caixa import __version__
from caixa.master import Master

PathLike = Union[str, Path]
INBOX = "Inbox"
FOLDERS = ("People", "Groups", INBOX)
#: How the box's files are laid out. 2: every source keeps its files in an `Attachments` folder
#: (Phase 1.5). A box without the mark is 1, and is moved once when it is opened (see the service).
LAYOUT = 2
README = """# {name}

This folder is a box made with Caixa: a person's messages, mail and other records, kept in plain
files that open without any special software.

- `People/` has one folder per person: a page named after them with everything from them, every
  year and every source, and a folder for each source (iMessage, WhatsApp, Voicemail, …) with the
  files it brought, named by date.
- `Groups/` is the same for group conversations.
- Mail lives with its people: `People/<Person>/Mail/<Account>/`, one page per conversation, with
  its attachments in `Attachments/` beside them.
- `Inbox/` is where you drop an export (a .zip or a folder) for Caixa to import.
- `.caixa/` is Caixa's own working data. Everything above it is yours to keep, copy and open.

To add more, use Caixa. To read, just open a page in a web browser.
"""


#: How much of the box a change to people needs drawn again, narrowest first.
SCOPES = ("index", "pages")

#: One change to `box.yaml` at a time, across the service's threads.
STATE_LOCK = threading.RLock()


class BoxError(Exception):
    """The folder is not a usable box (or already is one)."""


@dataclass
class Box:
    root: Path
    name: str

    # --- Opening and creating -----------------------------------------------------------

    @classmethod
    def create(cls, root: PathLike, name: str = "") -> "Box":
        folder = Path(root)
        if (folder / ".caixa" / "box.yaml").exists():
            raise BoxError(f"{folder} is already a Caixa box.")
        title = name.strip() or folder.name
        for sub in (*FOLDERS, ".caixa/work", ".caixa/logs"):
            (folder / sub).mkdir(parents=True, exist_ok=True)
        readme = folder / "README.md"
        if not readme.exists():  # never replace a README someone already wrote
            readme.write_text(README.format(name=title), encoding="utf-8")
        settings = {
            "schema": 1,
            "name": title,
            "created": datetime.now(timezone.utc).isoformat(),
            "caixa_version": __version__,
            "layout": LAYOUT,
        }
        (folder / ".caixa" / "box.yaml").write_text(json.dumps(settings, indent=2) + "\n", "utf-8")
        box = cls(folder, title)
        with box.master():  # create the master database now, so a read-only viewer can open it
            pass
        return box

    @classmethod
    def open(cls, root: PathLike) -> "Box":
        folder = Path(root)
        settings_file = folder / ".caixa" / "box.yaml"
        try:
            settings = json.loads(settings_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise BoxError(f"{folder} is not a Caixa box (no readable .caixa/box.yaml).") from error
        return cls(folder, str(settings.get("name") or folder.name))

    # --- How its files are laid out -----------------------------------------------------

    def _settings(self) -> dict[str, Any]:
        data = json.loads((self.caixa_dir / "box.yaml").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    @property
    def layout(self) -> int:
        """How the box's files are laid out (see `LAYOUT`); 1 for a box made before the mark."""
        try:
            return int(self._settings().get("layout") or 1)
        except (OSError, ValueError, TypeError):
            return 1

    def update_state(self, change: Callable[[dict[str, Any]], Any]) -> Any:
        """Change `box.yaml` in place: read, `change(data)`, write; one change at a time (the
        service's job runner and its requests both write it). Returns what `change` returned."""
        with STATE_LOCK:
            data = self._settings()
            result = change(data)
            path = self.caixa_dir / "box.yaml"
            part = path.with_name("box.yaml.part")
            part.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")
            part.replace(path)
            return result

    def mark_layout(self, layout: int) -> None:
        """Record that the box's files are now laid out as `layout`."""
        self.update_state(lambda data: data.__setitem__("layout", layout))

    # --- Changes not yet drawn on the pages ----------------------------------------------

    def pending(self) -> dict[str, Any]:
        """The changes to people waiting to be drawn: `{"changes": n, "scope": "index" | "pages"}`
        (`index`: only the people page needs drawing; `pages`: the person pages too)."""
        try:
            found = self._settings().get("pending") or {}
        except (OSError, ValueError):
            found = {}
        changes = int(found.get("changes") or 0) if isinstance(found, dict) else 0
        scope = found.get("scope") if isinstance(found, dict) else None
        return {"changes": changes, "scope": scope if changes and scope in SCOPES else None}

    def add_pending(self, scope: str) -> dict[str, Any]:
        """One more change waiting to be drawn; returns what is waiting now."""

        def add(data: dict[str, Any]) -> dict[str, Any]:
            was = data.get("pending") if isinstance(data.get("pending"), dict) else {}
            wider = max(scope, str(was.get("scope") or "index"), key=SCOPES.index)
            data["pending"] = {"changes": int(was.get("changes") or 0) + 1, "scope": wider}
            return dict(data["pending"])

        return dict(self.update_state(add))

    def take_pending(self, taken: dict[str, Any]) -> None:
        """What a drawing that started with `taken` waiting has drawn comes off the count (changes
        made while it ran stay waiting)."""

        def take(data: dict[str, Any]) -> None:
            was = data.get("pending") if isinstance(data.get("pending"), dict) else {}
            left = int(was.get("changes") or 0) - int(taken.get("changes") or 0)
            if left > 0:
                data["pending"] = {"changes": left, "scope": was.get("scope") or "pages"}
            else:
                data.pop("pending", None)

        if taken.get("changes"):
            self.update_state(take)

    @property
    def pages(self) -> str:
        """What drew the box's pages last (`chattr.pages.templates_fingerprint`); "" when unknown."""
        try:
            return str(self._settings().get("pages") or "")
        except (OSError, ValueError):
            return ""

    def mark_pages(self, fingerprint: str) -> None:
        """Record what drew the box's pages."""
        if self.pages != fingerprint:
            self.update_state(lambda data: data.__setitem__("pages", fingerprint))

    # --- Where things are ---------------------------------------------------------------

    @property
    def caixa_dir(self) -> Path:
        return self.root / ".caixa"

    @property
    def master_path(self) -> Path:
        return self.caixa_dir / "caixa.sqlite"

    @property
    def logs_dir(self) -> Path:
        return self.caixa_dir / "logs"

    def work_dir(self, collector: str) -> Path:
        path = self.caixa_dir / "work" / collector
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def inbox_dir(self) -> Path:
        """Where exports are dropped; made when asked, so older boxes get one too."""
        path = self.root / INBOX
        path.mkdir(parents=True, exist_ok=True)
        return path

    def master(self, read_only: bool = False) -> Master:
        return Master(self.master_path, read_only=read_only)

    # --- What is in it ------------------------------------------------------------------

    def status(self, read_only: bool = False) -> dict[str, Any]:
        with self.master(read_only=read_only) as master:
            db = master.connection
            by_type = {
                row[0]: row[1]
                for row in db.execute("SELECT type, COUNT(*) FROM items GROUP BY type")
            }
            return {
                "name": self.name,
                "root": str(self.root),
                "items": sum(by_type.values()),
                "by_type": by_type,
                "people": len(master.people()),
                "owner": next((p.name for p in master.people() if p.is_owner), None),
                "imports": [
                    {
                        "id": i.id,
                        "collector": i.collector,
                        "status": i.status,
                        "started_at": i.started_at,
                        "inserted": i.inserted,
                        "updated": i.updated,
                        "unchanged": i.unchanged,
                    }
                    for i in master.imports()[-5:]
                ],
            }
