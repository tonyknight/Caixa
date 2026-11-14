"""Which code is running, and whether the files have changed since it started."""

from __future__ import annotations

import io
import os
import subprocess
from pathlib import Path

from caixa import revision
from caixa.service import Service
from caixa.worker import STARTED, Worker


def _source(root: Path, when: float) -> Path:
    file = root / "caixa" / "thing.py"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("x = 1\n")
    os.utime(file, (when, when))
    return file


def test_code_written_after_a_process_started_means_restart(tmp_path: Path) -> None:
    _source(tmp_path, 1_700_000_000)
    assert not revision.changed_since(1_700_000_100, tmp_path)
    assert revision.changed_since(1_699_999_900, tmp_path)  # a pull landed after it started


def test_the_commit_is_read_from_the_checkout(tmp_path: Path) -> None:
    assert revision.commit(tmp_path) == ""  # not a git checkout
    run = lambda *args: subprocess.run(
        ["git", *args], cwd=tmp_path, check=True, capture_output=True
    )
    run("init", "-q")
    (tmp_path / "a.txt").write_text("a")
    run("add", "a.txt")
    run("-c", "user.name=T", "-c", "user.email=t@example.org", "commit", "-q", "-m", "one")
    head = subprocess.run(
        ["git", "rev-parse", "--short=7", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    assert revision.commit(tmp_path) == head
    run("pack-refs", "--all")
    assert revision.commit(tmp_path) == head  # also when git has packed its refs


def test_the_worker_says_which_code_it_is_and_whether_to_restart(tmp_path: Path) -> None:
    info = Worker(Service(roots=[tmp_path]), io.StringIO())._dispatch("worker.info", {})
    assert info["commit"] == revision.commit() and info["started"].startswith("20")
    assert info["restart_needed"] is revision.changed_since(STARTED)
