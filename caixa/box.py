"""A box: the folder a person's archive lives in.

    <Box name>/
      README.md            plain language: what this is, and how to use it with or without Caixa
      People/  Groups/  Mail/          the generated, durable files
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

from caixa import __version__
from caixa.master import Master

PathLike = Union[str, Path]
INBOX = "Inbox"
FOLDERS = ("People", "Groups", "Mail", INBOX)
README = """# {name}

This folder is a box made with Caixa: a person's messages, mail and other records, kept in plain
files that open without any special software.

- `People/` has one folder per person: `index.html` (everything from them), a page for each year,
  and a folder for each source (iMessage, WhatsApp, Voicemail, …) with the files it brought, named
  by date.
- `Groups/` is the same for group conversations.
- `Mail/` has one page per mail conversation, by year, with its attachments.
- `Inbox/` is where you drop an export (a .zip or a folder) for Caixa to import.
- `.caixa/` is Caixa's own working data. Everything above it is yours to keep, copy and open.

To add more, use Caixa. To read, just open a page in a web browser.
"""


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
