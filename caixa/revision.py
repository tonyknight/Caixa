"""Which code is running: the commit of the checkout, and whether the code on disk has changed
since a process started.

Caixa is run from a checkout while it is being developed, and a running `caixa serve` goes on using
the code it loaded. After a `git pull` the files are newer than the process, and until Caixa is
stopped and started again the old behaviour stays. These two facts let Caixa say so plainly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
#: The Python that makes up Caixa and Chattr, relative to the checkout.
SOURCES = ("caixa", "tools/chattr/src/chattr")


def commit(root: Optional[Path] = None) -> str:
    """The short commit of the checkout (`a855910`), or "" when this is not a git checkout."""
    git = (root or ROOT) / ".git"
    try:
        if git.is_file():  # a worktree: `.git` names the real folder
            git = Path(git.read_text(encoding="utf-8").split(":", 1)[1].strip())
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head[:7]
        ref = head.split(":", 1)[1].strip()
        common = git
        if (git / "commondir").is_file():
            common = (git / (git / "commondir").read_text(encoding="utf-8").strip()).resolve()
        for folder in (git, common):
            if (folder / ref).is_file():
                return (folder / ref).read_text(encoding="utf-8").strip()[:7]
        for line in (common / "packed-refs").read_text(encoding="utf-8").splitlines():
            if line.endswith(" " + ref):
                return line.split()[0][:7]
    except (OSError, IndexError):
        pass
    return ""


def changed_at(root: Optional[Path] = None) -> float:
    """When the newest source file was last written (seconds since the epoch; 0 if none)."""
    base = root or ROOT
    newest = 0.0
    for name in SOURCES:
        for file in (base / name).rglob("*.py"):
            try:
                newest = max(newest, file.stat().st_mtime)
            except OSError:
                continue
    return newest


def changed_since(started: float, root: Optional[Path] = None) -> bool:
    """Whether the code on disk is newer than a process that started at `started`."""
    return changed_at(root) > started
