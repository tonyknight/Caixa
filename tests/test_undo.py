"""Undo the last import, and run an import again.

Before each import Caixa keeps a copy of its databases and a list of the box's files. Undoing puts
the databases back, removes the files the import added, puts back any it moved, and redraws the
pages: the box is as it was before. Undo works from the newest import backwards.
"""

from __future__ import annotations

import hashlib
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fixtures import family

from caixa import undo
from caixa.service import ReadOnlyError, Service, ServiceError


def _whatsapp(fixture_family) -> str:
    return str(fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt")


def _voicemail(tmp_path: Path) -> str:
    archive = tmp_path / "iPhone Voicemail.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for stamp, who in (
            ("(2018-12-21) 15 02 31", family.ANA.name),
            ("(2019-01-03) 09 05 00", family.JOAO.name),
        ):
            z.writestr(f"vm/{stamp} - {who}.amr", f"audio of {stamp}")
    return str(archive)


@pytest.fixture
def service(tmp_path: Path) -> Service:
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    yield made
    made.close()


def _import(service: Service, collector: str, source: str) -> dict[str, Any]:
    job = service.import_start(collector, source)
    done = service.wait(job["id"], 120)
    assert done["status"] == "done", done["error"]
    return done


def _settle(service: Service) -> None:
    """Wait for whatever is queued (pages are redrawn after people change)."""
    for job in service.jobs_list(limit=50):
        if job["status"] in ("queued", "running"):
            service.wait(job["id"], 120)


def _state(tmp_path: Path) -> dict[str, Any]:
    """Everything that makes the box what it is: its visible files and what its database holds."""
    box = tmp_path / "Box"
    files = {
        p.relative_to(box).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(box.rglob("*"))
        if p.is_file() and ".caixa" not in p.relative_to(box).parts
    }
    with sqlite3.connect(box / ".caixa" / "caixa.sqlite") as db:
        tables = {
            name: db.execute(f"SELECT * FROM {name} ORDER BY 1, 2").fetchall()
            for name in ("items", "people", "aliases", "item_people", "imports", "change_log")
        }
    return {"files": files, **tables}


# --- Undo ---------------------------------------------------------------------------------------


def test_there_is_nothing_to_undo_in_a_new_box(service: Service) -> None:
    info = service.import_undo_info()
    assert info["job"] is None and "no import" in info["reason"].lower()
    with pytest.raises(ServiceError) as stop:
        service.import_undo()
    assert stop.value.kind == "conflict"


def test_undoing_the_only_import_empties_the_box_again(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    empty = _state(tmp_path)
    done = _import(service, "whatsapp", _whatsapp(fixture_family))
    assert service.box_status()["items"] == 7
    info = service.import_undo_info()
    assert (
        info["job"] == done["id"]
        and info["collector"] == "whatsapp"
        and info["people_changes"] == 0
    )

    undone = service.wait(service.import_undo()["id"], 120)
    assert undone["status"] == "done" and undone["kind"] == "undo"
    assert _state(tmp_path) == empty
    assert service.box_status()["items"] == 0
    assert service.jobs_get(done["id"])["result"]["undone"] is True
    assert service.import_undo_info()["job"] is None  # nothing left to undo


def test_undo_goes_back_one_import_at_a_time(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    empty = _state(tmp_path)
    _import(service, "whatsapp", _whatsapp(fixture_family))
    after_first = _state(tmp_path)
    second = _import(service, "voicemail", _voicemail(tmp_path))
    assert service.box_status()["items"] == 9
    assert service.import_undo_info()["job"] == second["id"]

    service.wait(service.import_undo()["id"], 120)
    assert _state(tmp_path) == after_first
    service.wait(service.import_undo()["id"], 120)
    assert _state(tmp_path) == empty


def test_what_was_done_to_people_since_the_import_is_undone_too_and_said_so(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    _import(service, "whatsapp", _whatsapp(fixture_family))
    after_first = _state(tmp_path)
    _import(service, "voicemail", _voicemail(tmp_path))
    # naming Ana moves her pages and files to a new folder
    service.people_link("WhatsApp", family.ANA.name, "Ana A")
    service.people_link("Voicemail", family.ANA.name, "Ana A")
    _settle(service)
    assert (tmp_path / "Box" / "People" / "Ana A" / "Voicemail").is_dir()
    assert service.import_undo_info()["people_changes"] == 2

    service.wait(service.import_undo()["id"], 120)
    assert _state(tmp_path) == after_first  # her WhatsApp files are back where they were


def test_an_undone_import_can_be_done_again(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    _import(service, "whatsapp", _whatsapp(fixture_family))
    before = _state(tmp_path)
    service.wait(service.import_undo()["id"], 120)
    again = _import(service, "whatsapp", _whatsapp(fixture_family))
    assert again["result"]["inserted"] == 7
    after = _state(tmp_path)
    assert after["files"] == before["files"] and len(after["items"]) == len(before["items"])


def test_undo_waits_its_turn_and_is_refused_read_only(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    _import(service, "whatsapp", _whatsapp(fixture_family))
    viewer = Service(read_only=True, roots=[tmp_path])
    viewer.box_open(str(tmp_path / "Box"))
    assert viewer.import_undo_info()["job"] is not None  # looking is allowed
    with pytest.raises(ReadOnlyError):
        viewer.call("import.undo", {})
    with pytest.raises(ReadOnlyError):
        viewer.call("import.again", {"job": 1})


def test_undo_is_refused_while_an_import_is_still_running(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    _import(service, "whatsapp", _whatsapp(fixture_family))
    service.import_start("voicemail", _voicemail(tmp_path))  # queued or running
    try:
        with pytest.raises(ServiceError) as stop:
            service.import_undo()
        assert stop.value.kind == "busy"
    finally:
        _settle(service)


def test_only_the_last_few_imports_can_be_undone(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    for _ in range(undo.KEEP + 2):
        _import(service, "whatsapp", _whatsapp(fixture_family))
    kept = sorted(p.name for p in (tmp_path / "Box" / ".caixa" / "undo").iterdir())
    assert len(kept) == undo.KEEP


def test_the_snapshot_is_inside_caixas_own_folder_and_nowhere_else(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    _import(service, "whatsapp", _whatsapp(fixture_family))
    snapshot = next((tmp_path / "Box" / ".caixa" / "undo").iterdir())
    assert (snapshot / "meta.json").is_file() and (snapshot / "files" / "caixa.sqlite").is_file()
    assert not [
        p
        for p in (tmp_path / "Box").iterdir()
        if p.name not in {".caixa", "People", "Groups", "Mail", "Inbox", "README.md", "index.html"}
    ]


# --- Run again ----------------------------------------------------------------------------------


def test_an_import_can_be_run_again_with_the_same_source_and_options(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    first = service.import_start(
        "whatsapp", _whatsapp(fixture_family), {"owner": family.OWNER.name}
    )
    service.wait(first["id"], 120)
    again = service.import_again(first["id"])
    assert again["id"] != first["id"] and again["collector"] == "whatsapp"
    assert again["source"] == first["source"] and again["options"] == first["options"]
    done = service.wait(again["id"], 120)
    assert done["result"]["inserted"] == 0 and done["result"]["unchanged"] == 7


def test_only_an_import_can_be_run_again_and_its_source_must_still_be_there(
    service: Service, tmp_path: Path, fixture_family
) -> None:
    source = Path(_voicemail(tmp_path))
    done = _import(service, "voicemail", str(source))
    undo_job = service.wait(service.import_undo()["id"], 120)
    with pytest.raises(ServiceError) as stop:
        service.import_again(undo_job["id"])
    assert stop.value.kind == "conflict"
    source.unlink()
    with pytest.raises(ServiceError) as gone:
        service.import_again(done["id"])
    assert gone.value.kind == "input"


def test_the_methods_are_known() -> None:
    assert Service.METHODS["import.undo"].write and Service.METHODS["import.again"].write
    assert not Service.METHODS["import.undo.info"].write
