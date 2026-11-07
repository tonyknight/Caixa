"""What Caixa remembers between runs: the last boxes, where you were, and the import in progress."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from caixa.service import Service, ServiceError
from caixa.state import State


@pytest.fixture
def state(tmp_path: Path) -> State:
    return State(tmp_path / "home")


def _box(service: Service, root: Path, name: str = "Our box") -> Path:
    service.box_create(str(root), name=name, owner="Maria Costa")
    return root


# --- The store ------------------------------------------------------------------------------


def test_nothing_is_remembered_at_first(state: State) -> None:
    assert state.recent_boxes() == [] and state.last_box() is None
    assert state.view("/boxes/A") == (None, None)


def test_the_boxes_opened_are_remembered_newest_first_without_repeats(state: State) -> None:
    for name in ("A", "B", "A", "C"):
        state.remember_box(f"/boxes/{name}", name)
    assert [b["path"] for b in state.recent_boxes(check=False)] == [
        "/boxes/C",
        "/boxes/A",
        "/boxes/B",
    ]


def test_only_the_last_ten_boxes_are_kept(state: State) -> None:
    for number in range(15):
        state.remember_box(f"/boxes/{number}", f"Box {number}")
    assert len(state.recent_boxes(check=False)) == 10
    assert state.recent_boxes(check=False)[0]["path"] == "/boxes/14"


def test_a_box_that_has_gone_is_listed_as_missing_not_dropped(state: State, tmp_path: Path) -> None:
    (tmp_path / "here" / ".caixa").mkdir(parents=True)
    state.remember_box(str(tmp_path / "here"), "Here")
    state.remember_box(str(tmp_path / "gone"), "Gone")
    listed = {b["name"]: b["exists"] for b in state.recent_boxes()}
    assert listed == {"Here": True, "Gone": False}
    assert state.last_box() is None  # the newest, "Gone", is not there to reopen


def test_forgetting_a_box_removes_it_and_what_was_kept_about_it(state: State) -> None:
    state.remember_box("/boxes/A", "A")
    state.set_view("/boxes/A", view="jobs", draft={"step": "options"})
    state.forget_box("/boxes/A")
    assert state.recent_boxes(check=False) == [] and state.view("/boxes/A") == (None, None)


def test_the_view_and_the_draft_are_kept_per_box(state: State) -> None:
    state.set_view("/boxes/A", view="import", draft={"collector": "voicemail", "step": "options"})
    state.set_view("/boxes/B", view="people")
    assert state.view("/boxes/A") == ("import", {"collector": "voicemail", "step": "options"})
    assert state.view("/boxes/B") == ("people", None)


def test_the_draft_can_be_cleared_without_touching_the_view(state: State) -> None:
    state.set_view("/boxes/A", view="import", draft={"step": "options"})
    state.set_view("/boxes/A", draft=None)
    assert state.view("/boxes/A") == ("import", None)


def test_an_oversized_draft_is_refused(state: State) -> None:
    with pytest.raises(ValueError, match="too large"):
        state.set_view("/boxes/A", draft={"values": "x" * 100_000})


def test_it_survives_a_new_instance_and_is_private_to_the_user(tmp_path: Path) -> None:
    State(tmp_path / "home").remember_box("/boxes/A", "A")
    again = State(tmp_path / "home")
    assert again.recent_boxes(check=False)[0]["name"] == "A"
    path = tmp_path / "home" / "state.json"
    assert not stat.S_IMODE(path.stat().st_mode) & 0o077


def test_a_damaged_file_is_set_aside_and_never_stops_anything(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "state.json").write_text("{not json", encoding="utf-8")
    broken = State(home)
    assert broken.recent_boxes() == []
    broken.remember_box("/boxes/A", "A")  # and it can start again
    assert json.loads((home / "state.json").read_text())["recent"][0]["path"] == "/boxes/A"
    assert (home / "state.json.damaged").exists()


def test_a_folder_that_cannot_be_written_is_not_an_error(tmp_path: Path) -> None:
    blocked = tmp_path / "file"
    blocked.write_text("a file where a folder should be")
    State(blocked / "home").remember_box("/boxes/A", "A")  # nothing to save into, nothing raised


# --- Through the service --------------------------------------------------------------------


def test_creating_and_opening_a_box_remember_it(tmp_path: Path, state: State) -> None:
    service = Service(roots=[tmp_path], state=state)
    first = _box(service, tmp_path / "First", "First box")
    second = _box(service, tmp_path / "Second", "Second box")
    service.box_open(str(first))
    names = [b["name"] for b in service.session_get()["recent"]]
    assert names == ["First box", "Second box"]
    assert service.session_get()["last_box"] == str(first.resolve())


def test_the_session_says_where_you_were_in_the_open_box(tmp_path: Path, state: State) -> None:
    service = Service(roots=[tmp_path], state=state)
    _box(service, tmp_path / "Box")
    assert service.session_get()["view"] is None
    service.session_set({"view": "jobs", "draft": {"collector": "voicemail", "step": "input"}})
    again = Service(roots=[tmp_path], state=state)
    again.box_open(str(tmp_path / "Box"))
    session = again.session_get()
    assert session["view"] == "jobs" and session["draft"]["collector"] == "voicemail"


def test_a_view_with_no_box_open_is_refused(tmp_path: Path, state: State) -> None:
    service = Service(roots=[tmp_path], state=state)
    with pytest.raises(ServiceError) as stop:
        service.session_set({"view": "jobs"})
    assert stop.value.kind == "no_box"


def test_bad_session_values_are_refused_whole(tmp_path: Path, state: State) -> None:
    service = Service(roots=[tmp_path], state=state)
    _box(service, tmp_path / "Box")
    with pytest.raises(ServiceError) as stop:
        service.session_set({"view": "jobs", "colour": "red"})
    assert stop.value.kind == "invalid_params"
    with pytest.raises(ServiceError):
        service.session_set({"draft": "not an object"})
    assert service.session_get()["view"] is None  # nothing from the bad calls was kept


def test_read_only_still_remembers_where_you_were_but_never_touches_the_box(
    tmp_path: Path, state: State
) -> None:
    writer = Service(roots=[tmp_path], state=state)
    _box(writer, tmp_path / "Box")
    before = {p: p.read_bytes() for p in (tmp_path / "Box").rglob("*") if p.is_file()}
    viewer = Service(read_only=True, roots=[tmp_path], state=state)
    viewer.box_open(str(tmp_path / "Box"))
    viewer.session_set({"view": "browse"})
    assert viewer.session_get()["view"] == "browse"
    after = {
        p: p.read_bytes()
        for p in (tmp_path / "Box").rglob("*")
        if p.is_file() and not p.name.endswith(("-wal", "-shm"))
    }
    assert {p: b for p, b in before.items() if p in after} == {
        p: after[p] for p in before if p in after
    }


def test_without_a_state_nothing_is_remembered_and_nothing_fails(tmp_path: Path) -> None:
    service = Service(roots=[tmp_path])  # tests and the command line: no state
    _box(service, tmp_path / "Box")
    assert service.session_get()["recent"] == []
    service.session_set({"view": "jobs"})  # accepted, simply not kept


def test_session_methods_are_known_and_read_only_safe() -> None:
    assert {"session.get", "session.set", "session.forget"} <= set(Service.METHODS)
    assert not any(
        Service.METHODS[m].write for m in ("session.get", "session.set", "session.forget")
    )


def test_the_home_variable_is_where_it_lives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAIXA_HOME", str(tmp_path / "elsewhere"))
    State.default().remember_box("/boxes/A", "A")
    assert (tmp_path / "elsewhere" / "state.json").is_file()
    assert os.environ["CAIXA_HOME"]
