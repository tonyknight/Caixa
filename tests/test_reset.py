"""Starting a box again: everything imported goes, the box's settings (and the names given by hand)
stay, so testing can begin from scratch without setting anything up again."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family

from caixa import settings
from caixa.box import Box
from caixa.service import ReadOnlyError, Service, ServiceError


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Service]:
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    yield made
    made.close()


def _import(service: Service, collector: str, source: Path) -> None:
    job = service.import_start(collector, str(source))
    assert service.wait(job["id"], 120)["status"] == "done"


def _filled(service: Service, fixture_family) -> Box:
    _import(
        service,
        "whatsapp",
        fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt",
    )
    _import(service, "voicemail", fixture_family.paths["iphone_voicemail"])
    return service._require_box()


def _visible(box: Box) -> list[str]:
    return sorted(
        p.relative_to(box.root).as_posix()
        for p in box.root.rglob("*")
        if p.is_file() and not p.relative_to(box.root).as_posix().startswith(".caixa/")
    )


def test_a_reset_removes_what_was_imported_and_keeps_the_settings(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    box = _filled(service, fixture_family)
    service.settings_set(
        {"contacts.file": str(fixture_family.paths["contacts"]), "speech.language": "pt"}
    )
    (box.root / "Inbox" / "export.zip").write_bytes(b"an export waiting to be imported")
    assert box.status()["items"] > 0 and any(p.startswith("People/") for p in _visible(box))

    done = service.box_reset()
    assert done["removed"] > 0 and done["left"] == []
    status = service.box_status()
    assert status["items"] == 0 and status["name"] == "Our box"
    assert status["owner"] == family.OWNER.name  # the owner is still who the box is for
    assert _visible(box) == ["Inbox/export.zip", "README.md"]  # nothing else above .caixa/
    kept = settings.load(box)
    assert kept["contacts.file"] == str(fixture_family.paths["contacts"])
    assert kept["speech.language"] == "pt"
    assert service.jobs_list() == []  # the history of imports went with them
    assert not (box.caixa_dir / "work" / "chattr").exists()
    assert not (box.caixa_dir / "undo").exists()


def test_importing_again_after_a_reset_gives_the_same_box(service: Service, fixture_family) -> None:
    box = _filled(service, fixture_family)
    before = (box.status()["items"], _visible(box))
    service.box_reset()
    _filled(service, fixture_family)
    assert (box.status()["items"], _visible(box)) == before


def test_names_given_by_hand_are_kept_unless_asked(service: Service, fixture_family) -> None:
    box = _filled(service, fixture_family)
    linked = service.people_link("Voicemail", family.ANA.phones[0], "Ana (daughter)", move=True)
    service.wait(linked["job"]["id"], 60)
    service.box_reset()
    with box.master() as master:
        assert master.person_id("Ana (daughter)") is not None
        assert master.find_person(family.ANA.phones[0]) == master.person_id("Ana (daughter)")
    _import(service, "voicemail", fixture_family.paths["iphone_voicemail"])
    assert (box.root / "People" / "Ana (daughter)").is_dir()  # the name applies straight away

    service.box_reset(forget_names=True)
    with box.master() as master:
        assert [p.name for p in master.people()] == [family.OWNER.name]


def test_files_someone_put_in_the_box_are_left_and_said(service: Service, fixture_family) -> None:
    box = _filled(service, fixture_family)
    notes = box.root / "People" / family.ANA.name / "my notes.txt"
    notes.write_text("mine")
    done = service.box_reset()
    assert notes.read_text() == "mine"
    assert done["left"] == [f"People/{family.ANA.name}/my notes.txt"]


def test_a_reset_waits_for_a_running_import_and_is_refused_read_only(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    _filled(service, fixture_family)
    store = service._jobs()
    job = store.create("import", "whatsapp", "x", {})
    store.update(job, status="running")
    with pytest.raises(ServiceError, match="running"):
        service.box_reset()
    store.update(job, status="done")
    viewer = Service(read_only=True, roots=[tmp_path])
    viewer.box_open(str(tmp_path / "Box"))
    with pytest.raises(ReadOnlyError):
        viewer.call("box.reset", {})


def test_the_command_line_asks_first(
    service: Service, fixture_family, tmp_path: Path, monkeypatch, capsys
) -> None:
    from caixa import cli

    _filled(service, fixture_family)
    service.close()
    box = str(tmp_path / "Box")
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert cli.main(["reset", "--box", box]) == 0
    assert "Nothing was changed" in capsys.readouterr().out
    assert Box.open(box).status()["items"] > 0
    assert cli.main(["reset", "--box", box, "--yes"]) == 0
    out = capsys.readouterr().out
    assert "files removed" in out and Box.open(box).status()["items"] == 0
