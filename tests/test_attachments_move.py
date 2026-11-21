"""A box built before every source had an Attachments folder is moved once, when it is opened."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote

import pytest
from fixtures import family

from chattr import filing

from caixa.box import LAYOUT, Box
from caixa.service import Service


def _old_folder(spec: Any, service: str) -> str:
    if spec.kind == "mail":
        return f"{spec.folder}/Attachments"
    return f"{spec.folder}/{filing.safe_name(service, 'Other')}"


def _whatsapp(fixture_family: Any, chat: str = "WhatsApp Chat - Ana Costa") -> str:
    return str(fixture_family.paths["whatsapp"] / chat / "_chat.txt")


def _broken_links(root: Path) -> list[str]:
    broken = []
    for page in root.rglob("*.html"):
        if ".caixa" in page.parts:
            continue
        for link in re.findall(r'(?:href|src)="([^"#:]+)"', page.read_text(encoding="utf-8")):
            if not (page.parent / unquote(link)).exists():
                broken.append(f"{page.relative_to(root)} → {link}")
    return broken


def _files(root: Path) -> list[str]:
    return sorted(
        p.relative_to(root).as_posix()
        for p in (root / "People").rglob("*")
        if p.is_file() and p.suffix != ".html"
    )


def _set_layout(box: Path, layout: int | None) -> None:
    path = box / ".caixa" / "box.yaml"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("layout", None)
    if layout is not None:
        data["layout"] = layout
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def old_box(tmp_path: Path, fixture_family: Any, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A box with a WhatsApp chat imported the way Caixa filed files before (no layout mark)."""
    root = tmp_path / "Box"
    first = Service(roots=[tmp_path])
    first.box_create(str(root), name="Old box", owner=family.OWNER.name)
    with monkeypatch.context() as old:
        old.setattr(filing, "_folder", _old_folder)
        done = first.wait(first.import_start("whatsapp", _whatsapp(fixture_family))["id"], 60)
    assert done["status"] == "done", done["error"]
    first.close()
    _set_layout(root, None)
    assert any("/WhatsApp/(" in f for f in _files(root))
    return root


def _open(root: Path, tmp_path: Path) -> tuple[Service, list[dict[str, Any]]]:
    service = Service(roots=[tmp_path])
    service.box_open(str(root))
    moves = [j for j in service.call("jobs.list") if j["kind"] == "refresh"]
    return service, moves


def test_a_new_box_is_made_with_the_current_layout(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="New")
    assert box.layout == LAYOUT == 2


def test_opening_an_old_box_moves_its_files_once(old_box: Path, tmp_path: Path) -> None:
    before = _files(old_box)
    service, moves = _open(old_box, tmp_path)
    try:
        assert len(moves) == 1
        done = service.wait(moves[0]["id"], 60)
        assert done["status"] == "done", done["error"]
        after = _files(old_box)
        assert len(after) == len(before) and all("/WhatsApp/Attachments/" in f for f in after)
        assert _broken_links(old_box) == []
        assert Box.open(old_box).layout == LAYOUT
    finally:
        service.close()
    again, moves = _open(old_box, tmp_path)
    again.close()
    assert moves == [] or all(j["id"] == done["id"] for j in moves)  # nothing new started


def test_a_box_with_nothing_imported_is_marked_at_once(tmp_path: Path) -> None:
    root = tmp_path / "Box"
    Box.create(root, name="Empty")
    _set_layout(root, None)
    service, moves = _open(root, tmp_path)
    service.close()
    assert moves == [] and Box.open(root).layout == LAYOUT


def test_a_stopped_move_starts_again_on_the_next_opening(old_box: Path, tmp_path: Path) -> None:
    service = Service(roots=[tmp_path])
    service.box_open(str(old_box))
    (move,) = [j for j in service.call("jobs.list") if j["kind"] == "refresh"]
    service.call("import.cancel", {"job": move["id"]})
    service.wait(move["id"], 60)
    service.close()
    if Box.open(old_box).layout == LAYOUT:  # it had already finished before the cancel landed
        pytest.skip("the move finished before it could be stopped")
    service, moves = _open(old_box, tmp_path)
    try:
        fresh = [j for j in moves if j["status"] in ("queued", "running")]
        assert len(fresh) == 1
        assert service.wait(fresh[0]["id"], 60)["status"] == "done"
        assert all("/WhatsApp/Attachments/" in f for f in _files(old_box))
        assert _broken_links(old_box) == [] and Box.open(old_box).layout == LAYOUT
    finally:
        service.close()


def test_an_import_from_before_the_move_can_be_undone_and_imports_still_work(
    old_box: Path, tmp_path: Path, fixture_family: Any
) -> None:
    service, moves = _open(old_box, tmp_path)
    try:
        service.wait(moves[0]["id"], 60)
        again = service.wait(service.import_start("whatsapp", _whatsapp(fixture_family))["id"], 60)
        assert again["status"] == "done" and again["result"]["inserted"] == 0
        assert all("/WhatsApp/Attachments/" in f for f in _files(old_box))
        assert _broken_links(old_box) == []
        while service.call("import.undo.info").get("job"):
            undone = service.wait(service.call("import.undo")["id"], 60)
            assert undone["status"] == "done", undone["error"]
        assert _files(old_box) == []  # back to before the first import
        assert _broken_links(old_box) == []
    finally:
        service.close()
