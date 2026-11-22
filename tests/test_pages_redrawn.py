"""Pages drawn by an older Caixa are drawn again, once, when the box is opened."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fixtures import family

from chattr.pages import templates_fingerprint

from caixa.box import Box
from caixa.service import Service


def _whatsapp(fixture_family: Any) -> str:
    return str(fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt")


def _drawn_by(root: Path, fingerprint: str) -> None:
    path = root / ".caixa" / "box.yaml"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["pages"] = fingerprint
    path.write_text(json.dumps(data), encoding="utf-8")


def _redraws(service: Service) -> list[dict[str, Any]]:
    return [j for j in service.call("jobs.list") if j["kind"] == "refresh"]


def test_an_import_records_what_drew_the_pages(tmp_path: Path, fixture_family: Any) -> None:
    service = Service(roots=[tmp_path])
    service.box_create(str(tmp_path / "Box"), name="Box", owner=family.OWNER.name)
    done = service.wait(service.import_start("whatsapp", _whatsapp(fixture_family))["id"], 60)
    assert done["status"] == "done", done["error"]
    service.close()
    assert Box.open(tmp_path / "Box").pages == templates_fingerprint()


def test_pages_drawn_by_other_templates_are_redrawn_once(
    tmp_path: Path, fixture_family: Any
) -> None:
    root = tmp_path / "Box"
    first = Service(roots=[tmp_path])
    first.box_create(str(root), name="Box", owner=family.OWNER.name)
    first.wait(first.import_start("whatsapp", _whatsapp(fixture_family))["id"], 60)
    first.close()
    _drawn_by(root, "an older Caixa")
    index = root / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8").replace('data-fold="friends"', ""), encoding="utf-8"
    )

    service = Service(roots=[tmp_path])
    service.box_open(str(root))
    (redraw,) = _redraws(service)
    assert service.wait(redraw["id"], 60)["status"] == "done"
    service.close()
    assert 'data-fold="friends"' in index.read_text(encoding="utf-8")
    assert Box.open(root).pages == templates_fingerprint()

    again = Service(roots=[tmp_path])
    again.box_open(str(root))
    assert [j for j in _redraws(again) if j["status"] in ("queued", "running")] == []
    again.close()


def test_an_empty_box_starts_nothing(tmp_path: Path) -> None:
    root = tmp_path / "Box"
    Box.create(root, name="Empty")
    _drawn_by(root, "an older Caixa")
    service = Service(roots=[tmp_path])
    service.box_open(str(root))
    assert _redraws(service) == []
    service.close()
