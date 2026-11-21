"""Subcategories of Family, Friends, Business and Acquaintances: two levels, kept through a reset."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family

from caixa import owner as owner_file
from caixa.box import Box
from caixa.reset import reset_box
from caixa.service import Service, ServiceError


@pytest.fixture
def box(tmp_path: Path) -> Box:
    made = Box.create(tmp_path / "Box", name="Box")
    with made.master() as master:
        master.add_person(family.OWNER.name, is_owner=True)
        for person in (family.ANA, family.JOAO, family.RUI):
            master.add_person(person.name)
        master.commit()
    return made


def test_two_levels_under_a_category_and_no_more(box: Box) -> None:
    with box.master() as master:
        school = master.add_subcategory("friends", None, "School")
        year = master.add_subcategory("friends", school, "Class of 98")
        with pytest.raises(ValueError, match="cannot have"):
            master.add_subcategory("friends", year, "Too deep")
        with pytest.raises(ValueError, match="already"):
            master.add_subcategory("friends", None, "school")
        with pytest.raises(ValueError, match="category"):
            master.add_subcategory("unrecognized", None, "Nope")
        with pytest.raises(ValueError, match="Friends"):
            master.add_subcategory("family", school, "Cousins")  # its parent is under Friends
        master.add_subcategory("family", None, "Cousins")
        master.rename_subcategory(year, "Class of '98")
        tree = master.subcategories()
    assert [(s["category"], s["name"], s["parent_id"]) for s in tree] == [
        ("family", "Cousins", None), ("friends", "School", None), ("friends", "Class of '98", school),
    ]  # fmt: skip


def test_people_are_sorted_into_a_subcategory_and_counted_with_its_parents(box: Box) -> None:
    with box.master() as master:
        school = master.add_subcategory("friends", None, "School")
        year = master.add_subcategory("friends", school, "Class of 98")
        ana, joao = master.person_id(family.ANA.name), master.person_id(family.JOAO.name)
        master.set_category([ana], "friends", year)
        master.set_category([joao], "friends", school)
        assert master.category(ana) == "friends" and master.subcategory(ana) == year
        counts = {s["name"]: s["people"] for s in master.subcategories()}
        assert counts == {"School": 2, "Class of 98": 1}
        master.set_category([joao], "friends")  # back to the category itself
        assert master.subcategory(joao) is None
        with pytest.raises(ValueError, match="Friends"):
            master.set_category([joao], "family", school)


def test_deleting_moves_people_up_and_takes_its_children(box: Box) -> None:
    with box.master() as master:
        school = master.add_subcategory("friends", None, "School")
        year = master.add_subcategory("friends", school, "Class of 98")
        ana, joao = master.person_id(family.ANA.name), master.person_id(family.JOAO.name)
        master.set_category([ana], "friends", year)
        master.delete_subcategory(year)
        assert master.subcategory(ana) == school
        master.set_category([joao], "friends", master.add_subcategory("friends", school, "Band"))
        master.delete_subcategory(school)
        assert master.subcategories() == []
        assert master.subcategory(ana) is None and master.category(ana) == "friends"
        assert master.subcategory(joao) is None and master.category(joao) == "friends"


def test_they_are_kept_through_a_reset(box: Box) -> None:
    with box.master() as master:
        school = master.add_subcategory("friends", None, "School")
        year = master.add_subcategory("friends", school, "Class of 98")
        master.set_category([master.person_id(family.ANA.name)], "friends", year)
        master.commit()
        owner_file.save(box, master)
    saved = owner_file.load(box)
    assert {"category": "friends", "path": ["School", "Class of 98"]} in saved["subcategories"]
    assert saved["placed"] == {family.ANA.name: ["School", "Class of 98"]}
    reset_box(box)
    with box.master() as master:
        assert [s["name"] for s in master.subcategories()] == ["School", "Class of 98"]
        ana = master.person_id(family.ANA.name)
        assert ana is not None and master.category(ana) == "friends"
        found = {s["id"]: s["name"] for s in master.subcategories()}
        assert found[master.subcategory(ana)] == "Class of 98"


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Service]:
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Box", owner=family.OWNER.name)
    with Box.open(tmp_path / "Box").master() as master:
        master.add_person(family.ANA.name)
        master.commit()
    yield made
    made.close()


def test_the_service_adds_renames_sorts_and_deletes(service: Service) -> None:
    school = service.call("people.subcategory.add", {"category": "friends", "name": "School"})
    year = service.call(
        "people.subcategory.add",
        {"category": "friends", "parent": school["id"], "name": "Class of 98"},
    )
    with pytest.raises(ServiceError, match="cannot have"):
        service.call(
            "people.subcategory.add", {"category": "friends", "parent": year["id"], "name": "x"}
        )
    service.call("people.subcategory.rename", {"id": year["id"], "name": "Class of '98"})
    sorted_in = service.call(
        "people.categorize",
        {"people": [family.ANA.name], "category": "friends", "subcategory": year["id"]},
    )
    assert sorted_in["changed"] == 1
    tree = service.call("people.subcategories")["subcategories"]
    assert [(s["name"], s["people"]) for s in tree] == [("School", 1), ("Class of '98", 1)]
    gone = service.call("people.subcategory.delete", {"id": school["id"]})
    assert gone["deleted"] == 2 and service.call("people.subcategories")["subcategories"] == []
    (ana,) = [p for p in service.call("people.list")["people"] if p["name"] == family.ANA.name]
    assert ana["category"] == "friends" and ana["subcategory"] is None
