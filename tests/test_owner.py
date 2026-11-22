"""The owner's preference file (`.caixa/owner.json`): names given by hand, categories and the
people removed from the box. It outlives a reset and applies again at the next import."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family

from caixa import owner
from caixa.service import Service, ServiceError


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


def _file(service: Service) -> dict:
    assert service.box is not None
    return json.loads(owner.path(service.box).read_text(encoding="utf-8"))


def test_a_missing_file_reads_as_empty_and_a_damaged_one_is_set_aside(service: Service) -> None:
    box = service.box
    assert box is not None
    assert owner.load(box) == {
        "schema": 1,
        "names": [],
        "categories": {},
        "subcategories": [],
        "placed": {},
        "removed": [],
        "mail": {"kept": [], "chosen": [], "ignored": [], "accounts": {}},
    }
    owner.path(box).write_text("{not json", encoding="utf-8")
    assert owner.load(box)["names"] == []
    assert (box.caixa_dir / "owner.json.damaged").read_text(encoding="utf-8") == "{not json"


def test_the_file_lives_in_dot_caixa_and_only_its_owner_can_read_it(
    service: Service, fixture_family
) -> None:
    _import(service, fixture_family)
    service.people_categorize([family.ANA.name], "family")
    box = service.box
    assert box is not None
    assert owner.path(box) == box.root / ".caixa" / "owner.json"
    assert stat.S_IMODE(owner.path(box).stat().st_mode) == 0o600
    assert _file(service)["categories"] == {family.ANA.name: "family"}


def test_a_name_given_by_hand_is_written_and_a_rename_keeps_the_identifiers(
    service: Service, fixture_family
) -> None:
    _import(service, fixture_family)
    done = service.people_link("WhatsApp", "+1 555 010 7777", "Rosa Lima")
    service.wait(done["job"]["id"], 120)
    names = _file(service)["names"]
    assert {"identifier": "+1 555 010 7777", "kind": "phone", "service": None,
            "person": "Rosa Lima"} in names  # fmt: skip
    ana = next(p for p in service.people_list()["people"] if p["name"] == family.ANA.name)
    renamed = service.people_rename(ana["id"], "Ana C. Costa")
    service.wait(renamed["job"]["id"], 120)
    assert "Ana C. Costa" in {n["person"] for n in _file(service)["names"]}


def test_names_and_categories_typed_into_the_file_are_taken_up_when_the_box_opens(
    service: Service, tmp_path: Path
) -> None:
    box = service.box
    assert box is not None
    owner.path(box).write_text(
        json.dumps(
            {
                "names": [{"identifier": "+15550109999", "kind": "phone", "person": "Tia Nena"}],
                "categories": {"Tia Nena": "family"},
            }
        ),
        encoding="utf-8",
    )
    service.box_open(str(box.root))
    people = {p["name"]: p for p in service.people_list()["people"]}
    assert people["Tia Nena"]["category"] == "family"
    with box.master() as master:
        assert [a.source for a in master.aliases() if a.value == "+15550109999"] == ["human"]


def test_a_reset_keeps_the_file_and_forgetting_names_keeps_who_was_removed(
    service: Service, fixture_family
) -> None:
    _import(service, fixture_family)
    service.people_categorize([family.ANA.name], "friends")
    service.wait(service.people_delete(handles=[{"service": "SMS", "identifier": "+15550100000"}])["job"]["id"], 120)  # fmt: skip
    done = service.box_reset()
    assert done["names_kept"] >= 0
    assert _file(service)["categories"] == {family.ANA.name: "friends"}
    assert {p["name"]: p["category"] for p in service.people_list()["people"]}[
        family.ANA.name
    ] == "friends"
    service.box_reset(forget_names=True)
    kept = _file(service)
    assert kept["names"] == [] and kept["categories"] == {}
    assert [r["identifier"] for r in kept["removed"]] == ["+15550100000"]


def test_deleting_a_person_removes_their_conversation_their_files_and_their_page(
    service: Service, fixture_family
) -> None:
    _import(service, fixture_family)
    box = service.box
    assert box is not None
    folder = box.root / "People" / family.ANA.name
    assert (folder / f"{family.ANA.name}.html").is_file()
    before = service.box_status()["items"]
    assert before > 0
    done = service.people_delete(people=[family.ANA.name])
    assert done["removed"] == 1 and done["job"]["kind"] == "refresh"
    assert service.wait(done["job"]["id"], 120)["status"] == "done"
    assert family.ANA.name not in {p["name"] for p in service.people_list()["people"]}
    assert not folder.exists()  # the page, the pictures, the folder
    assert service.box_status()["items"] < before
    assert _file(service)["removed"][0]["person"] == family.ANA.name
    assert family.ANA.name not in (box.root / "index.html").read_text(encoding="utf-8")

    _import(service, fixture_family)  # the same export again: she stays out
    assert family.ANA.name not in {p["name"] for p in service.people_list()["people"]}
    assert not folder.exists()

    service.box_reset()  # and after starting again
    _import(service, fixture_family)
    assert family.ANA.name not in {p["name"] for p in service.people_list()["people"]}
    assert not (folder / f"{family.ANA.name}.html").exists()


def test_a_removed_number_leaves_the_list_to_be_named_at_once(
    service: Service, fixture_family
) -> None:
    job = service.import_start("imessage", str(fixture_family.paths["imessage"]))
    assert service.wait(job["id"], 120)["status"] == "done"
    listed = service.people_unresolved()["handles"]
    assert listed
    first = listed[0]
    service.people_delete(
        handles=[{"service": first["service"], "identifier": first["identifier"]}]
    )
    left = service.people_unresolved()["handles"]  # before the redraw job has run
    assert (first["service"], first["identifier"]) not in {
        (h["service"], h["identifier"]) for h in left
    }


def test_the_owner_cannot_be_deleted_and_nobody_is_an_error(
    service: Service, fixture_family
) -> None:
    _import(service, fixture_family)
    with pytest.raises(ServiceError, match="owner"):
        service.people_delete(people=[family.OWNER.name])
    with pytest.raises(ServiceError, match="Nobody"):
        service.people_delete()
    with pytest.raises(ServiceError, match="no person"):
        service.people_delete(people=["Nobody Atall"])


def test_a_removed_list_matches_numbers_however_they_are_written() -> None:
    match = owner.removed_matcher(
        [{"identifier": "+1 (555) 010-1234"}, {"identifier": "x@y.pt", "service": "Mail"},
         {"person": "Rui Lima"}]
    )  # fmt: skip
    assert match is not None
    assert match("SMS", "+15550101234", None) and match("WhatsApp", "15550101234", None) is not None
    assert match("Mail", "x@y.pt", None) and not match("iMessage", "x@y.pt", None)
    assert match("Messenger", "rui.lima.3", "rui lima")
    assert not match("SMS", "+15550109999", "Ana")
    assert owner.removed_matcher([]) is None


def test_texts_google_voice_forwarded_to_messages_are_kept_once(
    service: Service, fixture_family
) -> None:
    """The copy Messages kept of a text Google Voice forwarded goes when the box is redrawn."""
    from datetime import datetime, timezone

    from chattr.database_manager import DatabaseManager
    from chattr.records import ConversationRecord, MessageRecord

    _import(service, fixture_family)
    box = service.box
    assert box is not None
    database = box.work_dir("chattr") / "Database" / "chattr.sqlite"
    at = datetime(2024, 3, 1, 10, 0, tzinfo=timezone.utc)
    with DatabaseManager(database) as db:
        db.upsert(
            ConversationRecord("Google Voice", "gv-rui", participants=("+15550109876",)),
            [MessageRecord(timestamp=at, sender="+15550109876", body="Dinner at 8?")],
        )
        db.upsert(
            ConversationRecord("iMessage", "no-chat:+15550109876", participants=("+15550109876",)),
            [MessageRecord(timestamp=at, sender="+15550109876", body="Dinner at 8?")],
        )
        db.commit()
    done = service._redraw()
    assert done is not None and service.wait(done["id"], 120)["status"] == "done"
    with DatabaseManager(database) as db:
        services = [
            r[0]
            for r in db.connection.execute(
                "SELECT c.service FROM messages m JOIN conversations c ON c.id = m.conversation_id "
                "WHERE m.body = 'Dinner at 8?'"
            )
        ]
    assert services == ["Google Voice"]


def test_mail_decisions_and_the_owners_addresses_are_kept(service: Service) -> None:
    box = service._require_box()
    owner.set_mail_decision(
        box, ["Beatriz.Lima@example.net", "carlos.mendes@example.net"], "chosen"
    )
    owner.set_mail_decision(box, ["carlos.mendes@example.net"], "ignored")  # moves him
    mail = owner.load(box)["mail"]
    assert mail["chosen"] == ["beatriz.lima@example.net"]
    assert mail["ignored"] == ["carlos.mendes@example.net"]
    owner.set_mail_decision(box, ["carlos.mendes@example.net"], "chosen")
    mail = owner.load(box)["mail"]
    assert mail["chosen"] == ["beatriz.lima@example.net", "carlos.mendes@example.net"]
    assert mail["ignored"] == []
    owner.set_mail_decision(box, ["beatriz.lima@example.net"], "chosen", on=False)
    assert owner.load(box)["mail"]["chosen"] == ["carlos.mendes@example.net"]
    assert owner.mail_owner(box, "Gmail") == []
    owner.set_mail_owner(box, "Gmail", ["Maria.Costa@example.com"])
    assert owner.mail_owner(box, "Gmail") == ["maria.costa@example.com"]
    assert owner.mail_owner(box, "Work") == []
    service.call("box.reset", {})
    assert owner.mail_owner(box, "Gmail") == ["maria.costa@example.com"]
    assert owner.load(box)["mail"]["chosen"] == ["carlos.mendes@example.net"]


def test_a_version_caixa_wrote_itself_never_undoes_a_later_change(tmp_path: Path) -> None:
    """A redraw re-reads the file while people are being sorted: if it reads the version from
    before the latest change (Caixa's own), it must not put the old category back."""
    from caixa.box import Box

    box = Box.create(tmp_path / "Box", name="Box")
    with box.master() as master:
        pedro = master.add_person("Pedro Dias")
        master.set_category([pedro], "business")
        master.commit()
        owner.save(box, master)
        before = owner.path(box).read_bytes()  # (what a redraw has just read)
        master.set_category([pedro], None)
        master.commit()
        owner.save(box, master)
    owner.path(box).write_bytes(before)
    with box.master() as master:
        owner.apply(box, master)
        assert master.category(pedro) is None
    # a version typed by hand still applies
    data = json.loads(before)
    data["categories"] = {"Pedro Dias": "friends"}
    owner.path(box).write_text(json.dumps(data), encoding="utf-8")
    with box.master() as master:
        owner.apply(box, master)
        assert master.category(pedro) == "friends"
