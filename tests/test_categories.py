"""People sorted into categories (Family, Friends, Business, Acquaintance, Unrecognized), kept in
the box's master database and drawn on the box's index page."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family

from caixa.master import CATEGORIES, Master
from caixa.service import ReadOnlyError, Service, ServiceError


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Service]:
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    yield made
    made.close()


def _import(service: Service, fixture_family) -> None:
    source = fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt"
    job = service.import_start("whatsapp", str(source))
    assert service.wait(job["id"], 120)["status"] == "done"


def test_the_categories_are_the_five_asked_for() -> None:
    assert CATEGORIES == ("family", "friends", "business", "acquaintance", "unrecognized")


def test_a_category_is_kept_follows_a_rename_and_survives_a_merge(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        ana, other = master.add_person("Ana"), master.add_person("Ana C.")
        assert master.category(ana) is None  # unassigned until someone says
        master.set_category([ana], "family")
        master.rename_person(ana, "Ana Costa")
        assert master.category(ana) == "family"
        master.merge_people(ana, other)  # the one who stays had none: it takes hers
        assert master.category(other) == "family"
        with pytest.raises(ValueError, match="category"):
            master.set_category([other], "enemies")
        master.set_category([other], None)
        assert master.category(other) is None


def test_people_are_sorted_through_the_service_and_the_pages_follow(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    _import(service, fixture_family)
    listed = {p["name"]: p for p in service.people_list()["people"]}
    assert listed[family.ANA.name]["category"] is None
    done = service.people_categorize([family.ANA.name], "family")
    assert done["changed"] == 1 and done["job"]["kind"] == "refresh"
    service.wait(done["job"]["id"], 120)
    assert {p["name"]: p for p in service.people_list()["people"]}[family.ANA.name][
        "category"
    ] == "family"
    index = (tmp_path / "Box" / "index.html").read_text(encoding="utf-8")
    assert 'data-category="family"' in index
    # sorting several times quickly never piles up redraws: at most one waits
    for category in ("friends", "business", "acquaintance", "family"):
        service.people_categorize([family.ANA.name], category)
        waiting = [
            j for j in service.jobs_list() if j["kind"] == "refresh" and j["status"] == "queued"
        ]
        assert len(waiting) <= 1


def test_sorting_needs_people_who_exist_and_a_known_category(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    _import(service, fixture_family)
    with pytest.raises(ServiceError) as unknown:
        service.people_categorize(["Nobody At All"], "family")
    assert unknown.value.kind == "not_found"
    with pytest.raises(ServiceError) as wrong:
        service.people_categorize([family.ANA.name], "enemies")
    assert wrong.value.kind == "invalid_params"
    viewer = Service(read_only=True, roots=[tmp_path])
    viewer.box_open(str(tmp_path / "Box"))
    with pytest.raises(ReadOnlyError):
        viewer.call("people.categorize", {"people": [family.ANA.name], "category": "family"})


def test_a_reset_keeps_the_categories(service: Service, fixture_family) -> None:
    _import(service, fixture_family)
    service.wait(service.people_categorize([family.ANA.name], "family")["job"]["id"], 120)
    service.box_reset()
    _import(service, fixture_family)
    listed = {p["name"]: p for p in service.people_list()["people"]}
    assert listed[family.ANA.name]["category"] == "family"
    service.box_reset(forget_names=True)
    _import(service, fixture_family)
    assert {p["name"]: p for p in service.people_list()["people"]}[family.ANA.name][
        "category"
    ] is None
