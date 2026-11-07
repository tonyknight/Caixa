"""When Caixa finds nothing to import, it says what it saw, what it wanted and what is likely wrong.

The report is shown on the screen and pasted into bug reports, so it never repeats a person's name
or number: letters become x and digits become 9, keeping only the shape of a file name.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from caixa.collectors import inputs
from caixa.collectors.base import Collector
from caixa.collectors.chattr import collectors
from caixa.collectors.inputs import InputError, shape


@pytest.fixture(scope="module")
def six() -> dict[str, Collector]:
    return {c.info.id: c for c in collectors()}


def _zip(path: Path, files: dict[str, bytes | str]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


def _refused(collector: Collector, source: Path) -> InputError:
    with pytest.raises(InputError) as stop:
        collector.preview(source, {})
    return stop.value


# --- Shapes ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("(2018-12-21) 15 02 31 - Diana Belenky.amr", "(9999-99-99) 99 99 99 - Xxxxx Xxxxxxx.amr"),
        ("João Costa.m4a", "Xxxx Xxxxx.m4a"),
        ("+1 555 0101.mp3", "+9 999 9999.mp3"),
        ("notes", "xxxxx"),
        ("a.b.TXT", "x.x.txt"),
    ],
)
def test_a_shape_keeps_the_pattern_and_hides_the_person(name: str, expected: str) -> None:
    assert shape(name) == expected


# --- What the refusal says ------------------------------------------------------------------


def test_the_first_sentence_is_the_one_people_already_know(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    archive = _zip(tmp_path / "iPhone Voicemail.zip", {"notes.txt": "x"})
    error = _refused(six["voicemail"], archive)
    assert str(error).splitlines()[0] == f"Nothing to import was found in {archive}."
    assert error.summary == str(error).splitlines()[0]


def test_it_says_what_kind_of_thing_it_opened_and_what_was_in_it(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    files = {f"iPhone Voicemail/Voicemail {n}.wav": b"a" for n in range(3)} | {"notes.txt": "x"}
    text = str(_refused(six["voicemail"], _zip(tmp_path / "v.zip", files)))
    assert "a zip with 4 files" in text
    assert "3 .wav" in text and "1 .txt" in text


def test_it_shows_examples_as_shapes_never_as_names(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    archive = _zip(tmp_path / "v.zip", {"iPhone Voicemail/Ana Costa 2018-12-21 15.02.amr": b"a"})
    text = str(_refused(six["voicemail"], archive))
    assert "Xxx Xxxxx 9999-99-99 99.99.amr" in text
    assert "Ana" not in text.split("\n", 1)[1] and "Costa" not in text.split("\n", 1)[1]


def test_it_says_what_the_source_was_looking_for(six: dict[str, Collector], tmp_path: Path) -> None:
    wanted = {
        "voicemail": "voicemail.db",
        "whatsapp": "_chat.txt",
        "messenger": "message_1.json",
        "mail": ".mbox",
        "googlevoice": ".html",
        "imessage": "chat.db",
    }
    for collector_id, needle in wanted.items():
        text = str(
            _refused(six[collector_id], _zip(tmp_path / f"{collector_id}.zip", {"a.xyz": "x"}))
        )
        assert "Looking for:" in text and needle in text, collector_id


def test_voicemail_files_with_names_it_could_not_read_are_named_as_the_problem(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    archive = _zip(tmp_path / "v.zip", {"iPhone Voicemail/Ana Costa.amr": b"a", "b.amr": b"a"})
    text = str(_refused(six["voicemail"], archive))
    assert "2 audio files" in text and "none of their names start with a date" in text
    assert "(2018-12-21) 15 02 31 - Jane Smith.amr" in text  # the pattern, as an example


def test_a_zip_inside_the_zip_is_called_out(six: dict[str, Collector], tmp_path: Path) -> None:
    archive = _zip(tmp_path / "outer.zip", {"inner.zip": b"PK", "readme.txt": "x"})
    assert "holds another .zip" in str(_refused(six["voicemail"], archive))


def test_files_a_mac_adds_are_not_counted_as_the_export(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    archive = _zip(
        tmp_path / "v.zip",
        {"__MACOSX/._a.amr": b"x", "folder/.DS_Store": b"x", "folder/notes.txt": "x"},
    )
    text = str(_refused(six["voicemail"], archive))
    assert "a zip with 1 file" in text and "2 hidden or Mac system files" in text


def test_an_empty_zip_and_an_empty_folder_are_said_to_be_empty(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    assert "is empty" in str(_refused(six["voicemail"], _zip(tmp_path / "e.zip", {})))
    (tmp_path / "empty").mkdir()
    assert "a folder that is empty" in str(_refused(six["voicemail"], tmp_path / "empty"))


def test_a_single_file_given_where_a_folder_is_needed_says_so(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    single = tmp_path / "Ana Costa.amr"
    single.write_bytes(b"a")
    text = str(_refused(six["voicemail"], single))
    assert "a single file" in text and "needs a folder or a .zip" in text


def test_a_missing_path_says_whether_its_folder_is_there(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    text = str(_refused(six["voicemail"], tmp_path / "nothing.zip"))
    assert text.startswith(f"Not found: {tmp_path / 'nothing.zip'}")
    assert "folder is there" in text
    elsewhere = str(_refused(six["voicemail"], tmp_path / "no" / "such" / "x.zip"))
    assert "folder is not there either" in elsewhere


def test_a_file_that_is_not_a_zip_is_not_called_one(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    fake = tmp_path / "voicemail.zip"
    fake.write_text("this is not a zip")
    text = str(_refused(six["voicemail"], fake))
    assert "not a readable zip" in text and "17 bytes" in text


def test_the_details_travel_with_the_error_for_a_screen_to_show_separately() -> None:
    error = InputError("Nothing.", ["one", "two"])
    assert error.summary == "Nothing." and error.details == ["one", "two"]
    assert str(error) == "Nothing.\none\ntwo"
    assert str(InputError("Plain.")) == "Plain."


def test_a_source_that_is_found_still_imports_as_before(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    folder = tmp_path / "vm"
    folder.mkdir()
    (folder / "(2018-12-21) 15 02 31 - Jane Smith.amr").write_bytes(b"a")
    assert six["voicemail"].preview(folder, {}).items == 1
    assert inputs.shape("x") == "x"


# --- Where the reasons show up ---------------------------------------------------------------


def test_the_service_carries_the_reasons_separately_as_well(tmp_path: Path) -> None:
    from caixa.service import Service, ServiceError

    service = Service(roots=[tmp_path])
    service.box_create(str(tmp_path / "Box"), name="Box")
    archive = _zip(tmp_path / "v.zip", {"notes.txt": "x"})
    with pytest.raises(ServiceError) as stop:
        service.import_preview("voicemail", str(archive))
    assert stop.value.kind == "input"
    assert str(stop.value).startswith("Nothing to import was found")
    assert any(line.startswith("Looking for:") for line in stop.value.data["details"])
    assert all("\n" not in line for line in stop.value.data["details"])


def test_a_failed_import_job_keeps_the_reasons(tmp_path: Path) -> None:
    from caixa.service import Service

    service = Service(roots=[tmp_path])
    service.box_create(str(tmp_path / "Box"), name="Box")
    job = service.import_start("voicemail", str(_zip(tmp_path / "v.zip", {"notes.txt": "x"})))
    done = service.wait(job["id"], 30)
    assert done["status"] == "failed"
    assert "What Caixa saw: a zip with 1 file" in done["error"] and "Looking for:" in done["error"]
