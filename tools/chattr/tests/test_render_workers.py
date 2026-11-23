"""Pages written by several worker processes are the pages one process writes, byte for byte."""

from __future__ import annotations

from pathlib import Path

import pytest

from chattr import pages
from chattr.database_manager import DatabaseManager
from chattr.render import Renderer


def _roots(archive) -> list[Path]:
    outputs = archive.root / "Output"
    return [archive.media, outputs / "Voicemail" / "Attachments",
            outputs / "GoogleVoice" / "Attachments", outputs / "Mail" / "Attachments"]  # fmt: skip


def _files(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*.html")}


def test_several_workers_write_the_same_pages(full_archive, tmp_path: Path) -> None:
    one, three = tmp_path / "one", tmp_path / "three"
    seen: list[tuple[int, int]] = []
    with DatabaseManager(full_archive.database) as db:
        renderer = Renderer(db)
        assert len(renderer.pages) > 3
        pages.render_pages(renderer, one, _roots(full_archive))
        pages.render_pages(
            renderer, three, _roots(full_archive), workers=3, database=full_archive.database,
            progress=lambda done, total: seen.append((done, total)), parallel_from=0,
        )  # fmt: skip
    assert _files(one) == _files(three) and _files(one)
    total = len(renderer.pages)
    assert seen and seen[-1] == (total, total)
    assert [d for d, _ in seen] == sorted(d for d, _ in seen)


def test_a_failing_worker_leaves_the_pages_to_the_process(
    full_archive, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object) -> object:
        raise RuntimeError("a worker fell over")

    monkeypatch.setattr(pages, "_draw_share", broken)
    with DatabaseManager(full_archive.database) as db:
        renderer = Renderer(db)
        written = pages.render_pages(
            renderer, tmp_path / "out", _roots(full_archive), workers=2,
            database=full_archive.database, parallel_from=0,
        )  # fmt: skip
    assert len(written) == len(renderer.pages) + 1 and all(p.is_file() for p in written)
