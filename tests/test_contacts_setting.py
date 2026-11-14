"""Contacts are set once for a box (this Mac's Contacts, a vCard file, or both) and every import
uses them without asking again."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fixtures import family

from caixa import settings
from caixa.box import Box
from caixa.collectors.inputs import InputError
from caixa.collectors.options import OptionsError, validate
from caixa.collectors.registry import discover
from caixa.service import Service
from caixa.state import State

ADDRESS_BOOK = """
CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER PRIMARY KEY, Z_NAME TEXT);
INSERT INTO Z_PRIMARYKEY VALUES (22, 'ABCDContact');
CREATE TABLE ZABCDRECORD (Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER, ZFIRSTNAME TEXT, ZLASTNAME TEXT,
    ZORGANIZATION TEXT, ZCONTAINERWHERECONTACTISME INTEGER, ZLINKID TEXT);
CREATE TABLE ZABCDPHONENUMBER (Z_PK INTEGER PRIMARY KEY, ZOWNER INTEGER, ZFULLNUMBER TEXT);
CREATE TABLE ZABCDEMAILADDRESS (Z_PK INTEGER PRIMARY KEY, ZOWNER INTEGER, ZADDRESS TEXT,
    ZADDRESSNORMALIZED TEXT);
"""


@pytest.fixture
def mac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A stand-in for this Mac's Contacts that knows the family's daughter by her number."""
    folder = tmp_path / "AddressBook"
    folder.mkdir()
    with sqlite3.connect(folder / "AddressBook-v22.abcddb") as db:
        db.executescript(ADDRESS_BOOK)
        db.execute("INSERT INTO ZABCDRECORD VALUES (1, 22, 'Ana', 'Costa', NULL, NULL, NULL)")
        db.execute("INSERT INTO ZABCDPHONENUMBER VALUES (1, 1, ?)", (family.ANA.phones[0],))
    monkeypatch.setattr("chattr.people.mac_contacts_folder", lambda: folder)
    monkeypatch.setattr("caixa.service.mac_contacts_folder", lambda: folder)
    return folder


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box.create(tmp_path / "Box", "Test box")


def _voicemail(box: Box, fixture_family, options: dict | None = None):
    collector = discover().get("voicemail")
    chosen = validate(collector.info.options_schema, options or {})
    return collector.run(box, fixture_family.paths["iphone_voicemail"], chosen, lambda step: None)


def test_every_source_offers_the_contacts_file_from_settings(box: Box, fixture_family) -> None:
    for collector in discover().all():
        assert (
            collector.info.options_schema["properties"]["contacts"]["x-setting"] == "contacts.file"
        )
    service = Service(roots=[box.root.parent])
    service.box_open(str(box.root))
    service.settings_set({"contacts.file": str(fixture_family.paths["contacts"])})
    for described in service.collectors_list():
        # the wizard starts with the saved file already filled in: nothing to ask
        saved = described["options_schema"]["properties"]["contacts"]["default"]
        assert saved == str(fixture_family.paths["contacts"])


def test_a_saved_contacts_file_names_people_without_being_asked_for(
    box: Box, fixture_family
) -> None:
    before = _voicemail(box, fixture_family)
    assert any(family.ANA.phones[0] in handle for handle in before.unresolved)
    settings.save(
        box, {"contacts.file": str(fixture_family.paths["contacts"]), "contacts.mac": False}
    )
    after = _voicemail(box, fixture_family)  # no contacts option given
    assert not any(family.ANA.phones[0] in handle for handle in after.unresolved)
    assert (box.root / "People" / family.ANA.name / "Voicemail").is_dir()


def test_this_macs_contacts_name_people_in_any_import(box: Box, fixture_family, mac: Path) -> None:
    assert settings.load(box)["contacts.mac"] is True  # on unless turned off
    result = _voicemail(box, fixture_family)
    assert not any(family.ANA.phones[0] in handle for handle in result.unresolved)
    assert (box.root / "People" / family.ANA.name / "Voicemail").is_dir()


def test_turning_the_macs_contacts_off_is_respected(box: Box, fixture_family, mac: Path) -> None:
    settings.save(box, {"contacts.mac": False})
    result = _voicemail(box, fixture_family)
    assert any(family.ANA.phones[0] in handle for handle in result.unresolved)


def test_a_contacts_file_that_is_not_there_is_refused_when_saved(box: Box, tmp_path: Path) -> None:
    with pytest.raises(OptionsError, match="there is no file"):
        settings.save(box, {"contacts.file": str(tmp_path / "missing.vcf")})


def test_a_contacts_file_that_went_missing_later_is_explained(
    box: Box, fixture_family, tmp_path: Path
) -> None:
    copy = tmp_path / "contacts.vcf"
    copy.write_bytes(fixture_family.paths["contacts"].read_bytes())
    settings.save(box, {"contacts.file": str(copy)})
    copy.unlink()
    with pytest.raises(InputError, match="Settings, under Contacts"):
        _voicemail(box, fixture_family)


def test_settings_can_show_that_contacts_work(
    tmp_path: Path, box: Box, fixture_family, mac: Path
) -> None:
    service = Service(roots=[tmp_path], state=State(tmp_path / "home"))
    service.box_open(str(box.root))
    service.settings_set({"contacts.file": str(fixture_family.paths["contacts"])})
    checked = service.call("contacts.check")
    assert checked["mac"] == {"on": True, "people": 1, "problem": ""}
    assert (
        checked["file"]["on"] and checked["file"]["people"] >= 3 and not checked["file"]["problem"]
    )


def test_settings_say_when_this_macs_contacts_cannot_be_read(
    tmp_path: Path, box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "Empty"
    empty.mkdir()
    monkeypatch.setattr("caixa.service.mac_contacts_folder", lambda: empty)
    service = Service(roots=[tmp_path], state=State(tmp_path / "home"))
    service.box_open(str(box.root))
    assert service.call("contacts.check")["mac"] == {"on": True, "people": 0, "problem": "empty"}
    monkeypatch.setattr("caixa.service.mac_contacts_folder", lambda: tmp_path / "nowhere")
    monkeypatch.setattr("caixa.service.sys.platform", "darwin")
    assert service.call("contacts.check")["mac"]["problem"] == "no_access"
    monkeypatch.setattr("caixa.service.sys.platform", "linux")
    assert service.call("contacts.check")["mac"]["problem"] == "not_a_mac"
