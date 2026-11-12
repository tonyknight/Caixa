"""The service layer: the box, its settings, browsing, the file picker and the inbox."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from caixa.service import ReadOnlyError, Service, ServiceError


@pytest.fixture
def service(tmp_path: Path) -> Service:
    return Service(roots=[tmp_path])


@pytest.fixture
def made(service: Service, tmp_path: Path) -> Service:
    service.box_create(str(tmp_path / "Box"), name="Our box", owner="Maria Costa")
    return service


def _snapshot(folder: Path) -> dict[str, bytes]:
    """Every file and its bytes, except SQLite's `-wal`/`-shm` coordination files, which reading a
    WAL database may create and which never hold data."""
    return {
        str(p.relative_to(folder)): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and not p.name.endswith(("-wal", "-shm"))
    }


# --- The box --------------------------------------------------------------------------------


def test_creating_a_box_returns_its_status(service: Service, tmp_path: Path) -> None:
    status = service.box_create(str(tmp_path / "Box"), name="Our box", owner="Maria Costa")
    assert status["name"] == "Our box" and status["items"] == 0
    assert status["owner"] == "Maria Costa" and status["people"] == 1
    assert (tmp_path / "Box" / "Inbox").is_dir()


def test_a_box_can_be_opened_by_a_new_service(made: Service, tmp_path: Path) -> None:
    other = Service(roots=[tmp_path])
    assert other.box_open(str(tmp_path / "Box"))["name"] == "Our box"
    assert other.box_status()["owner"] == "Maria Costa"


def test_methods_that_need_a_box_say_so(service: Service) -> None:
    with pytest.raises(ServiceError, match="open a box") as stop:
        service.box_status()
    assert stop.value.kind == "no_box"


def test_opening_a_folder_that_is_not_a_box_is_explained(service: Service, tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    with pytest.raises(ServiceError, match="not a Caixa box") as stop:
        service.box_open(str(tmp_path / "plain"))
    assert stop.value.kind == "not_found"


def test_creating_over_an_existing_box_is_refused(made: Service, tmp_path: Path) -> None:
    with pytest.raises(ServiceError, match="already") as stop:
        made.box_create(str(tmp_path / "Box"))
    assert stop.value.kind == "conflict"


def test_the_collectors_come_with_what_the_interface_needs(made: Service) -> None:
    described = {c["id"]: c for c in made.collectors_list()}
    assert {"imessage", "whatsapp", "messenger", "mail", "googlevoice", "voicemail"} <= set(
        described
    )
    json.dumps(described)  # plain data all the way down


# --- Settings -------------------------------------------------------------------------------


def _voicemail_defaults(service: Service) -> dict[str, object]:
    (voicemail,) = [c for c in service.collectors_list() if c["id"] == "voicemail"]
    properties = voicemail["options_schema"]["properties"]
    return {name: properties[name]["default"] for name in ("model", "language")}


def test_the_wizard_starts_from_the_speech_settings(made: Service) -> None:
    assert _voicemail_defaults(made) == {"model": "", "language": ""}
    made.settings_set({"speech.model": "/models/ggml-large-v3-turbo.bin", "speech.language": "en"})
    assert _voicemail_defaults(made) == {
        "model": "/models/ggml-large-v3-turbo.bin",
        "language": "en",
    }
    # the answer is a copy: asking again after a change is not stuck on the first values
    made.settings_set({"speech.model": ""})
    assert _voicemail_defaults(made)["model"] == ""


def test_without_a_box_the_options_have_their_plain_defaults(service: Service) -> None:
    assert _voicemail_defaults(service) == {"model": "", "language": ""}


def test_settings_have_defaults_and_a_schema(made: Service) -> None:
    result = made.settings_get()
    assert result["values"]["privacy.default"] == "private"
    assert result["values"]["translation.enabled"] is False
    assert result["schema"]["type"] == "object"
    assert result["box"]["root"].endswith("Box")


def test_settings_are_saved_in_the_box(made: Service, tmp_path: Path) -> None:
    made.settings_set(
        {"translation.enabled": True, "translation.endpoint": "http://localhost:1/v1"}
    )
    again = Service(roots=[tmp_path])
    again.box_open(str(tmp_path / "Box"))
    values = again.settings_get()["values"]
    assert values["translation.enabled"] is True
    assert values["translation.endpoint"] == "http://localhost:1/v1"
    saved = json.loads((tmp_path / "Box" / ".caixa" / "box.yaml").read_text())
    assert saved["name"] == "Our box"  # the rest of box.yaml is kept


def test_bad_settings_are_all_reported_and_nothing_is_saved(made: Service) -> None:
    with pytest.raises(ServiceError) as stop:
        made.settings_set({"privacy.default": "secret", "colour": "red"})
    assert stop.value.kind == "invalid_params"
    assert len(stop.value.data["errors"]) == 2
    assert made.settings_get()["values"]["privacy.default"] == "private"


# --- Browsing the box -----------------------------------------------------------------------


def _page(tmp_path: Path, relative: str, text: str = "<p>hello</p>") -> None:
    path = tmp_path / "Box" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_browse_lists_the_generated_files_and_hides_caixas_own(
    made: Service, tmp_path: Path
) -> None:
    _page(tmp_path, "People/Ana Costa/(2024) Ana Costa.html")
    top = {e["name"]: e for e in made.browse_list("")["entries"]}
    assert "People" in top and ".caixa" not in top
    assert top["People"]["kind"] == "directory"
    inner = made.browse_list("People/Ana Costa")["entries"]
    assert [e["name"] for e in inner] == ["(2024) Ana Costa.html"]
    assert inner[0]["path"] == "People/Ana Costa/(2024) Ana Costa.html"
    assert inner[0]["kind"] == "file" and inner[0]["size"] > 0


def test_browse_file_gives_a_page_and_where_it_is(made: Service, tmp_path: Path) -> None:
    _page(tmp_path, "People/Ana Costa/(2024) Ana Costa.html", "<p>olá</p>")
    info = made.browse_file("People/Ana Costa/(2024) Ana Costa.html")
    assert info["mime"] == "text/html" and info["content"] == "<p>olá</p>"
    assert info["absolute"].endswith("(2024) Ana Costa.html")


def test_binary_files_are_described_not_embedded(made: Service, tmp_path: Path) -> None:
    path = tmp_path / "Box" / "People" / "photo.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    info = made.browse_file("People/photo.png")
    assert info["mime"] == "image/png" and "content" not in info and info["size"] == 58


@pytest.mark.parametrize(
    "bad", ["../outside.txt", "People/../../outside.txt", "/etc/passwd", ".caixa/caixa.sqlite"]
)
def test_browse_refuses_anything_outside_the_visible_box(
    made: Service, tmp_path: Path, bad: str
) -> None:
    (tmp_path / "outside.txt").write_text("secret")
    with pytest.raises(ServiceError) as stop:
        made.browse_file(bad)
    assert stop.value.kind in ("outside_roots", "not_found")
    with pytest.raises(ServiceError):
        made.browse_list(bad)


def test_a_link_that_leaves_the_box_is_refused(made: Service, tmp_path: Path) -> None:
    (tmp_path / "outside.txt").write_text("secret")
    os.symlink(tmp_path / "outside.txt", tmp_path / "Box" / "People" / "link.txt")
    with pytest.raises(ServiceError) as stop:
        made.browse_file("People/link.txt")
    assert stop.value.kind == "outside_roots"


def test_a_missing_file_is_not_found(made: Service) -> None:
    with pytest.raises(ServiceError) as stop:
        made.browse_file("People/nothing.html")
    assert stop.value.kind == "not_found"


# --- The file picker ------------------------------------------------------------------------


def test_the_picker_lists_folders_first_and_hides_dotfiles(made: Service, tmp_path: Path) -> None:
    folder = tmp_path / "Downloads"
    folder.mkdir()
    (folder / "b.zip").write_bytes(b"zip")
    (folder / "a-folder").mkdir()
    (folder / ".hidden").write_text("x")
    listing = made.files_list(str(folder))
    assert [e["name"] for e in listing["entries"]] == ["a-folder", "b.zip"]
    assert listing["entries"][0]["kind"] == "directory" and listing["parent"] == str(tmp_path)
    shown = made.files_list(str(folder), show_hidden=True)
    assert ".hidden" in [e["name"] for e in shown["entries"]]


def test_the_picker_stays_inside_the_users_folders(made: Service, tmp_path: Path) -> None:
    with pytest.raises(ServiceError) as stop:
        made.files_list("/etc")
    assert stop.value.kind == "outside_roots"
    assert made.files_list(None)["path"] == str(tmp_path)  # starts at the first root
    assert made.files_list(str(tmp_path))["parent"] is None  # and cannot climb out of it


# --- The inbox ------------------------------------------------------------------------------


def test_the_inbox_lists_what_was_dropped_in_it(made: Service, tmp_path: Path) -> None:
    assert made.inbox_list()["entries"] == []
    (tmp_path / "Box" / "Inbox" / "chat.zip").write_bytes(b"zip")
    entries = made.inbox_list()["entries"]
    assert [e["name"] for e in entries] == ["chat.zip"]
    assert entries[0]["absolute"].endswith("chat.zip")


def test_an_older_box_gets_its_inbox_when_asked(made: Service, tmp_path: Path) -> None:
    (tmp_path / "Box" / "Inbox").rmdir()
    assert made.inbox_list()["entries"] == []
    assert (tmp_path / "Box" / "Inbox").is_dir()


# --- Read-only ------------------------------------------------------------------------------


def test_read_only_reads_everything_and_changes_nothing(made: Service, tmp_path: Path) -> None:
    _page(tmp_path, "People/Ana Costa/(2024) Ana Costa.html")
    before = _snapshot(tmp_path / "Box")
    viewer = Service(read_only=True, roots=[tmp_path])
    assert viewer.box_open(str(tmp_path / "Box"))["owner"] == "Maria Costa"
    viewer.box_status()
    viewer.settings_get()
    viewer.browse_list("")
    viewer.files_list(str(tmp_path))
    viewer.inbox_list()
    assert viewer.collectors_list()
    assert _snapshot(tmp_path / "Box") == before


def test_read_only_refuses_every_write(made: Service, tmp_path: Path) -> None:
    viewer = Service(read_only=True, roots=[tmp_path])
    viewer.box_open(str(tmp_path / "Box"))
    with pytest.raises(ReadOnlyError) as stop:
        viewer.box_create(str(tmp_path / "Other"))
    assert stop.value.kind == "read_only"
    with pytest.raises(ReadOnlyError):
        viewer.settings_set({"privacy.default": "family"})
    assert not (tmp_path / "Other").exists()
    assert made.settings_get()["values"]["privacy.default"] == "private"


def test_every_write_method_is_known_to_the_service() -> None:
    writes = {name for name, method in Service.METHODS.items() if method.write}
    assert writes >= {"box.create", "settings.set"}
    assert not writes & {"box.status", "browse.list", "browse.file", "files.list", "inbox.list"}
