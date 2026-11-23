"""Only pages whose content changed are written again; the rest are left as they are."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from chattr import pages
from chattr.database_manager import DatabaseManager
from chattr.render import Renderer


def _roots(archive) -> list[Path]:
    outputs = archive.root / "Output"
    return [archive.media, outputs / "Voicemail" / "Attachments",
            outputs / "GoogleVoice" / "Attachments", outputs / "Mail" / "Attachments"]  # fmt: skip


def _draw(archive, out: Path, **options: object) -> list[Path]:
    with DatabaseManager(archive.database) as db:
        return pages.render_pages(
            Renderer(db), out, _roots(archive), pages_list=out / "pages.json", **options
        )


def _times(out: Path) -> dict[str, int]:
    return {p.relative_to(out).as_posix(): p.stat().st_mtime_ns for p in out.rglob("*.html")}


def _bytes(out: Path) -> dict[str, bytes]:
    return {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*.html")}


@pytest.mark.parametrize(
    "options", [{}, {"workers": 2, "parallel_from": 0}], ids=["here", "workers"]
)
def test_a_second_run_rewrites_only_the_index(full_archive, tmp_path: Path, options: dict) -> None:
    out = tmp_path / "out"
    _draw(full_archive, out, **options)
    before, content = _times(out), _bytes(out)
    time.sleep(0.02)
    written = _draw(full_archive, out, **options)
    after = _times(out)
    assert {p for p in after if after[p] != before[p]} == {"index.html"}
    assert _bytes(out) == content
    assert len(written) == len(before)  # (still every page, for the list of what the box holds)
    assert (out / "pages.fingerprints.json").is_file()


def test_a_changed_message_rewrites_its_page_only(full_archive, tmp_path: Path) -> None:
    out, full = tmp_path / "out", tmp_path / "full"
    _draw(full_archive, out)
    before = _times(out)
    with DatabaseManager(full_archive.database) as db:
        message_id, conversation = db.connection.execute(
            "SELECT m.id, c.id FROM messages m JOIN conversations c ON c.id = m.conversation_id "
            "WHERE c.type != 'group' AND m.body IS NOT NULL AND c.service != 'Mail' LIMIT 1"
        ).fetchone()
        old = db.connection.execute(
            "SELECT body FROM messages WHERE id = ?", (message_id,)
        ).fetchone()[0]
        db.connection.execute(
            "UPDATE messages SET body = ? WHERE id = ?", ("A changed line", message_id)
        )
        db.commit()
    try:
        time.sleep(0.02)
        _draw(full_archive, out)
        after = _times(out)
        changed = {p for p in after if after[p] != before[p]} - {"index.html"}
        assert len(changed) == 1
        assert "A changed line" in (out / changed.pop()).read_text(encoding="utf-8")
        _draw(full_archive, full)  # the same as drawing everything afresh
        assert _bytes(out) == _bytes(full)
    finally:
        with DatabaseManager(full_archive.database) as db:
            db.connection.execute("UPDATE messages SET body = ? WHERE id = ?", (old, message_id))
            db.commit()


def test_a_page_gone_or_changed_on_disk_is_written_again(full_archive, tmp_path: Path) -> None:
    out = tmp_path / "out"
    _draw(full_archive, out)
    content = _bytes(out)
    gone, edited = sorted(p for p in content if p != "index.html")[:2]
    (out / gone).unlink()
    (out / edited).write_text("edited by hand", encoding="utf-8")
    _draw(full_archive, out)
    assert _bytes(out) == content


def test_new_templates_rewrite_every_page(
    full_archive, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    _draw(full_archive, out)
    before = _times(out)
    time.sleep(0.02)
    monkeypatch.setattr(pages, "templates_fingerprint", lambda: "other templates")
    _draw(full_archive, out)
    after = _times(out)
    assert all(after[p] != before[p] for p in before)
