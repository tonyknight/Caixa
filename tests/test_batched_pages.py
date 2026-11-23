"""In Caixa's window, changes to people wait and are drawn together, in one pass, on Update; a
pass for sorting alone writes the people page and nothing else."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family

from caixa.box import Box
from caixa.service import Service

ANA = family.ANA.name


def _whatsapp(fixture_family) -> str:  # type: ignore[no-untyped-def]
    return str(fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt")


@pytest.fixture
def root(tmp_path: Path, fixture_family) -> Path:  # type: ignore[no-untyped-def]
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Box", owner=family.OWNER.name)
    assert (
        made.wait(made.import_start("whatsapp", _whatsapp(fixture_family))["id"], 60)["status"]
        == "done"
    )
    made.close()
    return tmp_path / "Box"


@pytest.fixture
def window(root: Path) -> Iterator[Service]:
    opened = Service(roots=[root.parent], batch_pages=True)
    opened.box_open(str(root))
    yield opened
    opened.close()


def _refreshes(service: Service) -> list[dict]:  # type: ignore[type-arg]
    return [j for j in service.call("jobs.list") if j["kind"] == "refresh"]


def _times(root: Path) -> dict[str, int]:
    return {str(p.relative_to(root)): p.stat().st_mtime_ns for p in root.rglob("*.html")}


def test_changes_wait_and_one_update_draws_them_all(window: Service, root: Path) -> None:
    sorted_ = window.people_categorize([ANA], "family")
    assert sorted_["job"] is None and sorted_["pending"] == {"changes": 1, "scope": "index"}
    ana = next(p["id"] for p in window.people_list()["people"] if p["name"] == ANA)
    named = window.people_rename(ana, "Ana (daughter)")
    assert named["job"] is None and named["pending"] == {"changes": 2, "scope": "pages"}
    assert _refreshes(window) == []  # nothing drawn yet
    assert "Ana (daughter)" not in (root / "index.html").read_text(encoding="utf-8")

    update = window.people_update()
    assert window.wait(update["job"]["id"], 120)["status"] == "done"
    assert len(_refreshes(window)) == 1  # one pass for both
    assert window.pages_pending() == {"changes": 0, "scope": None}
    index = (root / "index.html").read_text(encoding="utf-8")
    assert 'data-name="Ana (daughter)"' in index
    assert window.people_update()["job"] is None  # nothing left to draw


def test_sorting_alone_writes_the_people_page_and_nothing_else(window: Service, root: Path) -> None:
    before = _times(root)
    window.people_categorize([ANA], "friends")
    update = window.people_update()
    assert update["job"]["options"] == {"scope": "index"}
    assert window.wait(update["job"]["id"], 120)["status"] == "done"
    after = _times(root)
    assert {p for p in after if after[p] != before.get(p)} == {"index.html"}
    assert 'data-category="friends"' in (root / "index.html").read_text(encoding="utf-8")


def test_changes_left_waiting_are_drawn_when_the_box_is_opened_again(
    window: Service, root: Path
) -> None:
    window.people_categorize([ANA], "business")
    window.close()
    assert Box.open(root).pending() == {"changes": 1, "scope": "index"}
    again = Service(roots=[root.parent], batch_pages=True)
    again.box_open(str(root))
    (job,) = _refreshes(again)
    assert again.wait(job["id"], 120)["status"] == "done"
    assert Box.open(root).pending()["changes"] == 0
    assert 'data-category="business"' in (root / "index.html").read_text(encoding="utf-8")
    again.close()


def test_without_the_window_a_change_is_drawn_at_once(root: Path) -> None:
    service = Service(roots=[root.parent])
    service.box_open(str(root))
    done = service.people_categorize([ANA], "family")
    assert done["job"]["options"] == {"scope": "index"} and done["pending"]["changes"] == 0
    assert service.wait(done["job"]["id"], 120)["status"] == "done"
    assert 'data-category="family"' in (root / "index.html").read_text(encoding="utf-8")
    service.close()
