"""The diagnostic report: what a person can paste when something does not work.

It answers "what is installed, what is set up, what happened" and, given a source that would not
import, "what Caixa sees in it". It never contains a name, a number or message text, and it hides
the home folder's name.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from fixtures import family

from caixa import diagnostics
from caixa.service import Service, ServiceError
from caixa.state import State


@pytest.fixture
def service(tmp_path: Path) -> Service:
    return Service(roots=[tmp_path], state=State(tmp_path / "home"))


@pytest.fixture
def made(service: Service, tmp_path: Path) -> Service:
    service.box_create(str(tmp_path / "Box"), name="Our box", owner="Maria Costa")
    return service


def _bad_zip(tmp_path: Path) -> Path:
    archive = tmp_path / "iPhone Voicemail.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("iPhone Voicemail/Ana Costa.amr", b"a")
    return archive


def test_the_report_names_the_install_and_what_is_missing(service: Service) -> None:
    text = diagnostics.report(service)
    for heading in ("Caixa", "Programs", "Interface", "Box"):
        assert f"\n== {heading} ==" in "\n" + text
    assert "caixa 0.1.0" in text and "python" in text.lower()
    for program in ("node", "ffmpeg", "whisper-cli", "exiftool"):
        assert program in text
    assert "no box is open" in text.lower()


def test_a_program_that_is_not_installed_says_not_found_and_what_it_is_for(
    service: Service, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(diagnostics.shutil, "which", lambda name: None)
    text = diagnostics.report(service)
    assert "whisper-cli: not found" in text and "voicemail transcription" in text
    assert "ffmpeg: not found" in text


def test_an_open_box_is_summarised_without_its_contents(made: Service, tmp_path: Path) -> None:
    text = diagnostics.report(made)
    assert "Our box" in text and "0 items" in text and "read-only: no" in text
    assert "Maria" not in text and "Costa" not in text  # the owner's name is a person's name


def test_the_speech_setup_is_checked_not_just_shown(made: Service, tmp_path: Path) -> None:
    made.settings_set({"speech.model": str(tmp_path / "ggml-small.bin"), "speech.language": "pt"})
    missing = diagnostics.report(made)
    assert "speech model: set, but there is no file at that path" in missing
    (tmp_path / "ggml-small.bin").write_bytes(b"0" * 2048)
    present = diagnostics.report(made)
    assert "speech model: set, file found (2.0 KB)" in present
    assert "speech language: pt" in present


def test_recent_jobs_show_their_state_and_errors(made: Service, tmp_path: Path) -> None:
    job = made.import_start("voicemail", str(_bad_zip(tmp_path)))
    made.wait(job["id"], 30)
    text = diagnostics.report(made)
    assert "Recent imports" in text and "voicemail" in text and "failed" in text
    assert "Nothing to import was found" in text


def test_a_source_that_will_not_import_is_explained_in_the_report(
    made: Service, tmp_path: Path
) -> None:
    text = diagnostics.report(made, collector="voicemail", source=str(_bad_zip(tmp_path)))
    assert "== This source ==" in text
    assert "voicemail" in text and "Cannot be imported" in text
    assert "Nothing to import was found" in text and "Looking for:" in text
    assert "Xxx Xxxxx.amr" in text and "Ana" not in text and "Costa" not in text


def test_a_source_that_will_import_says_what_it_would_bring(made: Service, tmp_path: Path) -> None:
    folder = tmp_path / "vm"
    folder.mkdir()
    (folder / f"(2018-12-21) 15 02 31 - {family.ANA.name}.amr").write_bytes(b"a")
    text = diagnostics.report(made, collector="voicemail", source=str(folder))
    assert "Would import: 1 items in 1 conversations" in text
    assert "Ana" not in text and "Costa" not in text


def test_the_report_hides_the_home_folder_and_never_the_box_paths_wrongly(
    made: Service, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(diagnostics.Path, "home", classmethod(lambda cls: tmp_path))
    text = diagnostics.report(made)
    assert str(tmp_path) not in text and "~/Box" in text


def test_a_source_without_a_collector_or_a_missing_source_is_said_plainly(made: Service) -> None:
    assert "unknown collector 'nope'" in diagnostics.report(made, collector="nope", source="/x")
    assert "Not found" in diagnostics.report(made, collector="voicemail", source="/no/such/place")


def test_the_report_is_a_method_and_never_writes(made: Service, tmp_path: Path) -> None:
    assert "diagnostics.report" in Service.METHODS
    assert not Service.METHODS["diagnostics.report"].write
    before = sorted(p.name for p in (tmp_path / "Box").rglob("*"))
    reply = made.call(
        "diagnostics.report", {"collector": "voicemail", "source": str(_bad_zip(tmp_path))}
    )
    assert reply["text"].startswith("Caixa diagnostic report")
    assert sorted(
        p.name for p in (tmp_path / "Box").rglob("*") if not p.name.endswith(("-wal", "-shm"))
    ) == [n for n in before if not n.endswith(("-wal", "-shm"))]


def test_it_works_in_a_read_only_box_and_with_no_box(made: Service, tmp_path: Path) -> None:
    viewer = Service(read_only=True, roots=[tmp_path])
    viewer.box_open(str(tmp_path / "Box"))
    assert "read-only: yes" in diagnostics.report(viewer)
    with pytest.raises(ServiceError):
        Service().call("diagnostics.nothing", {})
