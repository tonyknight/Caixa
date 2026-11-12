"""People through the service: unnamed handles, linking, renaming and merging, with pages kept right."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest
from fixtures import family

from caixa.master import Master
from caixa.service import ReadOnlyError, Service, ServiceError


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Service]:
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    yield made
    made.close()


def _import(service: Service, fixture_family, collector: str, source: Path) -> dict[str, Any]:
    job = service.import_start(collector, str(source))
    done = service.wait(job["id"], 60)
    assert done["status"] == "done", done["error"]
    return done


def _whatsapp(service: Service, fixture_family) -> None:
    _import(
        service,
        fixture_family,
        "whatsapp",
        fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt",
    )


def _imessage(service: Service, fixture_family) -> None:
    _import(service, fixture_family, "imessage", fixture_family.paths["imessage"])


def _pages(tmp_path: Path, person: str) -> list[str]:
    folder = tmp_path / "Box" / "People" / person
    return sorted(p.name for p in folder.glob("(*) *.html")) if folder.is_dir() else []


def _links(service: Service, person: str) -> int:
    with service._require_box().master() as master:
        pid = master.person_id(person)
        return int(
            master.connection.execute(
                "SELECT COUNT(*) FROM item_people WHERE person_id = ?", (pid,)
            ).fetchone()[0]
        )


def _change_count(service: Service, operation: str) -> int:
    with service._require_box().master() as master:
        return len([c for c in master.changes() if c.operation == operation])


# --- Who is unnamed -------------------------------------------------------------------------


def test_unresolved_handles_are_listed_busiest_first(service: Service, fixture_family) -> None:
    _imessage(service, fixture_family)
    handles = service.people_unresolved()["handles"]
    assert handles and handles == sorted(
        handles, key=lambda h: (-h["messages"], h["service"], h["identifier"])
    )
    assert {"service", "identifier", "display_name", "messages", "collector"} <= set(handles[0])
    assert family.UNKNOWN_HANDLE in {h["identifier"] for h in handles}


def test_nothing_is_unresolved_before_anything_is_imported(service: Service) -> None:
    assert service.people_unresolved() == {"handles": []}


def test_people_are_listed_with_what_they_have(service: Service, fixture_family) -> None:
    _whatsapp(service, fixture_family)
    service.people_link("WhatsApp", "Ana Costa", "Ana (daughter)")
    service.wait(service.jobs_list()[0]["id"], 60)
    people = {p["name"]: p for p in service.people_list()["people"]}
    assert people[family.OWNER.name]["is_owner"] is True
    assert people["Ana (daughter)"]["aliases"] >= 1 and people["Ana (daughter)"]["items"] > 0


# --- Linking --------------------------------------------------------------------------------


def test_linking_a_handle_names_it_and_moves_its_pages(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    _whatsapp(service, fixture_family)
    assert _pages(tmp_path, "Ana Costa") == ["(2024) Ana Costa.html"]
    before = _change_count(service, "link")
    linked = service.people_link("WhatsApp", "Ana Costa", "Ana (daughter)")
    assert linked["person"]["name"] == "Ana (daughter)" and linked["job"]["kind"] == "refresh"
    assert service.wait(linked["job"]["id"], 60)["status"] == "done"
    assert _pages(tmp_path, "Ana (daughter)") == ["(2024) Ana (daughter).html"]
    assert _pages(tmp_path, "Ana Costa") == []  # the stale page is gone
    assert _links(service, "Ana (daughter)") > 0
    assert _change_count(service, "link") > before
    assert service.people_unresolved()["handles"] == []
    page = (
        tmp_path / "Box" / "People" / "Ana (daughter)" / "(2024) Ana (daughter).html"
    ).read_text(encoding="utf-8")
    assert "Que lindo! Buy two." in page


def test_the_pages_still_link_their_photos_after_a_move(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    _whatsapp(service, fixture_family)
    service.wait(service.people_link("WhatsApp", "Ana Costa", "Ana (daughter)")["job"]["id"], 60)
    page = (
        tmp_path / "Box" / "People" / "Ana (daughter)" / "(2024) Ana (daughter).html"
    ).read_text(encoding="utf-8")
    assert "file not in this archive" not in page


def test_a_phone_number_is_linked_for_every_service(service: Service, fixture_family) -> None:
    _imessage(service, fixture_family)
    job = service.people_link("iMessage", family.ANA.phones[0], "Ana Costa")["job"]
    service.wait(job["id"], 60)
    with service._require_box().master() as master:
        assert master.find_person(family.ANA.phones[0], service="WhatsApp") == master.person_id(
            "Ana Costa"
        )
    assert family.ANA.phones[0] not in {
        h["identifier"] for h in service.people_unresolved()["handles"]
    }


def test_an_alias_that_names_someone_else_is_explained_and_can_be_moved(
    service: Service, fixture_family
) -> None:
    _imessage(service, fixture_family)
    service.people_link("iMessage", family.ANA.phones[0], "Ana A")
    with pytest.raises(ServiceError, match="already names Ana A") as stop:
        service.people_link("iMessage", family.ANA.phones[0], "Ana B")
    assert stop.value.kind == "conflict"
    moved = service.people_link("iMessage", family.ANA.phones[0], "Ana B", move=True)
    service.wait(moved["job"]["id"], 60)
    with service._require_box().master() as master:
        assert master.find_person(family.ANA.phones[0]) == master.person_id("Ana B")


def test_linking_to_a_person_by_id(service: Service, fixture_family) -> None:
    _imessage(service, fixture_family)
    owner = next(p for p in service.people_list()["people"] if p["is_owner"])
    linked = service.people_link("iMessage", family.UNKNOWN_HANDLE, owner["id"])
    assert linked["person"]["id"] == owner["id"]
    with pytest.raises(ServiceError) as stop:
        service.people_link("iMessage", "x", 9999)
    assert stop.value.kind == "not_found"
    with pytest.raises(ServiceError) as empty:
        service.people_link("iMessage", "x", "   ")
    assert empty.value.kind == "invalid_params"


# --- Renaming -------------------------------------------------------------------------------


def test_renaming_moves_the_pages_and_keeps_the_aliases(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    _whatsapp(service, fixture_family)
    first = service.people_link("WhatsApp", "Ana Costa", "Ana (daughter)")
    service.wait(first["job"]["id"], 60)
    renamed = service.people_rename(first["person"]["id"], "Ana Cruz")
    assert renamed["person"]["name"] == "Ana Cruz"
    service.wait(renamed["job"]["id"], 60)
    assert _pages(tmp_path, "Ana Cruz") == ["(2024) Ana Cruz.html"]
    assert _pages(tmp_path, "Ana (daughter)") == []
    assert _links(service, "Ana Cruz") > 0
    with service._require_box().master() as master:
        assert master.person_id("Ana (daughter)") is None
        assert master.find_person("Ana Costa", service="WhatsApp") == master.person_id("Ana Cruz")


def test_renaming_to_a_name_in_use_suggests_merging(service: Service) -> None:
    with service._require_box().master() as master:
        one, two = master.add_person("Ana A"), master.add_person("Ana B")
    with pytest.raises(ServiceError, match="merge") as stop:
        service.people_rename(one, "ana b")
    assert stop.value.kind == "conflict"
    with pytest.raises(ServiceError) as empty:
        service.people_rename(two, "  ")
    assert empty.value.kind == "invalid_params"
    with pytest.raises(ServiceError) as missing:
        service.people_rename(9999, "Someone")
    assert missing.value.kind == "not_found"


def test_the_owner_can_be_renamed(service: Service) -> None:
    owner = next(p for p in service.people_list()["people"] if p["is_owner"])
    result = service.people_rename(owner["id"], "Maria C. Costa")
    assert result["person"]["is_owner"] is True and result["person"]["name"] == "Maria C. Costa"


# --- Merging --------------------------------------------------------------------------------


def test_merging_joins_two_people_and_their_pages(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    _whatsapp(service, fixture_family)
    _imessage(service, fixture_family)
    a = service.people_link("WhatsApp", "Ana Costa", "Ana A")
    b = service.people_link("iMessage", family.ANA.phones[0], "Ana B")
    service.wait(b["job"]["id"], 60)
    service.wait(a["job"]["id"], 60)
    assert _links(service, "Ana A") > 0 and _links(service, "Ana B") > 0
    both = _links(service, "Ana A") + _links(service, "Ana B")
    merged = service.people_merge(source=b["person"]["id"], target=a["person"]["id"])
    assert merged["person"]["name"] == "Ana A"
    service.wait(merged["job"]["id"], 60)
    with service._require_box().master() as master:
        assert master.person_id("Ana B") is None
        assert master.find_person(family.ANA.phones[0]) == master.person_id("Ana A")
    assert _links(service, "Ana A") >= both - 1  # nothing was lost (a shared item is counted once)
    assert _pages(tmp_path, "Ana B") == []
    assert len(_pages(tmp_path, "Ana A")) >= 2  # WhatsApp 2024 and iMessage's years together


def test_the_owner_cannot_be_merged_away(service: Service) -> None:
    with service._require_box().master() as master:
        other = master.add_person("Ana A")
    owner = next(p for p in service.people_list()["people"] if p["is_owner"])
    with pytest.raises(ServiceError, match="owner") as stop:
        service.people_merge(source=owner["id"], target=other)
    assert stop.value.kind == "conflict"
    merged = service.people_merge(source=other, target=owner["id"])  # into the owner is fine
    assert merged["person"]["is_owner"] is True


def test_merging_someone_into_themselves_or_a_missing_person_is_explained(
    service: Service,
) -> None:
    with service._require_box().master() as master:
        one = master.add_person("Ana A")
    with pytest.raises(ServiceError, match="themselves") as same:
        service.people_merge(source=one, target=one)
    assert same.value.kind == "invalid_params"
    with pytest.raises(ServiceError) as stop:
        service.people_merge(source=one, target=9999)
    assert stop.value.kind == "not_found"


def test_master_rename_and_merge_keep_the_change_log_honest(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        a, b = master.add_person("A"), master.add_person("B")
        for item in ("m1", "m2"):
            master.connection.execute(
                "INSERT INTO items (id, type, collector, timestamp_utc, content_hash) "
                "VALUES (?, 'text', 'chattr', '2024-01-01T00:00:00+00:00', 'h')",
                (item,),
            )
            master.connection.execute("INSERT INTO item_people VALUES (?, ?, 'sender')", (item, b))
        master.connection.execute("INSERT INTO item_people VALUES ('m1', ?, 'sender')", (a,))
        assert master.merge_people(b, a) == 2
        rows = master.connection.execute(
            "SELECT item_id, person_id FROM item_people ORDER BY 1"
        ).fetchall()
        assert [tuple(r) for r in rows] == [("m1", a), ("m2", a)]
        assert [(c.item_id, c.operation) for c in master.changes()] == [
            ("m1", "link"),
            ("m2", "link"),
        ]
        assert master.person_id("B") is None


# --- Read-only and the rest -----------------------------------------------------------------


def test_read_only_can_see_who_is_unnamed_but_not_change_anyone(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    _imessage(service, fixture_family)
    viewer = Service(read_only=True, roots=[tmp_path])
    viewer.box_open(str(tmp_path / "Box"))
    assert viewer.people_unresolved()["handles"] and viewer.people_list()["people"]
    for call in (
        lambda: viewer.people_link("iMessage", "x", "Someone"),
        lambda: viewer.people_rename(1, "New"),
        lambda: viewer.people_merge(1, 2),
    ):
        with pytest.raises(ReadOnlyError):
            call()
    viewer.close()
