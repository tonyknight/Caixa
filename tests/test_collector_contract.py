"""The collector contract: declarations, option validation, discovery, and the box they import into."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import pytest

from caixa.box import Box, BoxError
from caixa.collectors.base import Collector, CollectorInfo, Preview, Progress, RunResult
from caixa.collectors.options import OptionsError, defaults, validate
from caixa.collectors.registry import Registry, discover

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "mode": {"type": "string", "enum": ["fast", "careful"], "default": "careful"},
        "workers": {"type": "integer", "minimum": 1, "maximum": 8, "default": 4},
        "ratio": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
        "verbose": {"type": "boolean", "default": False},
        "label": {"type": "string"},
    },
    "required": ["label"],
    "additionalProperties": False,
}


# --- Options --------------------------------------------------------------------------------


def test_defaults_come_from_the_schema() -> None:
    assert defaults(SCHEMA) == {"mode": "careful", "workers": 4, "ratio": 0.5, "verbose": False}


def test_valid_options_are_merged_with_the_defaults() -> None:
    given = {"label": "x", "workers": 2}
    cleaned = validate(SCHEMA, given)
    assert cleaned == {
        "mode": "careful",
        "workers": 2,
        "ratio": 0.5,
        "verbose": False,
        "label": "x",
    }
    assert given == {"label": "x", "workers": 2}  # not changed


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"label": "x", "colour": "red"}, "colour"),
        ({"label": "x", "workers": "four"}, "workers"),
        ({"label": "x", "workers": True}, "workers"),
        ({"label": "x", "workers": 1.5}, "workers"),
        ({"label": "x", "workers": 0}, "at least 1"),
        ({"label": "x", "workers": 9}, "at most 8"),
        ({"label": "x", "mode": "reckless"}, "one of"),
        ({"label": "x", "ratio": 1.5}, "at most 1"),
        ({"label": "x", "verbose": "yes"}, "verbose"),
        ({"label": 3}, "label"),
        ({}, "label"),
    ],
)
def test_bad_options_are_refused_with_a_message_naming_the_option(
    options: dict[str, Any], message: str
) -> None:
    with pytest.raises(OptionsError) as error:
        validate(SCHEMA, options)
    assert any(message in e for e in error.value.errors)


def test_every_problem_is_reported_at_once() -> None:
    with pytest.raises(OptionsError) as error:
        validate(SCHEMA, {"workers": 99, "mode": "x", "extra": 1})
    assert len(error.value.errors) == 4  # workers, mode, extra, and the missing label


def test_an_integer_is_a_valid_number() -> None:
    assert validate(SCHEMA, {"label": "x", "ratio": 1})["ratio"] == 1


# --- Collectors and the registry ------------------------------------------------------------


class Fake:
    def __init__(self, id: str = "fake", name: str = "A fake source") -> None:
        self.info = CollectorInfo(
            id=id,
            name=name,
            platform="Test",
            inputs=("file",),
            how_to_export="Press the button.",
            options_schema={"type": "object", "properties": {}},
        )

    def preview(
        self, source: Path, options: Mapping[str, Any], box: Optional[Box] = None
    ) -> Preview:
        return Preview(items=1)

    def run(
        self,
        box: Box,
        source: Path,
        options: Mapping[str, Any],
        progress: Callable[[Progress], None],
    ) -> RunResult:
        progress(Progress("working", 1, 1))
        return RunResult(inserted=1)


class _EntryPoint:
    def __init__(self, name: str, loader: Callable[[], Any]) -> None:
        self.name, self._loader = name, loader

    def load(self) -> Any:
        return self._loader()


def test_a_collector_has_the_protocol_shape() -> None:
    assert isinstance(Fake(), Collector)
    assert not isinstance(object(), Collector)


def test_register_get_and_list() -> None:
    registry = Registry()
    registry.register(Fake("b", "Beta"))
    registry.register(Fake("a", "Alpha"))
    assert registry.get("a").info.name == "Alpha"
    assert [c.info.id for c in registry.all()] == ["a", "b"]  # by display name
    with pytest.raises(KeyError, match="nope"):
        registry.get("nope")


def test_a_duplicate_id_is_refused() -> None:
    registry = Registry()
    registry.register(Fake("same"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Fake("same"))


def test_an_object_that_is_not_a_collector_is_refused() -> None:
    with pytest.raises(TypeError, match="collector"):
        Registry().register(object())  # type: ignore[arg-type]


def test_discovery_loads_single_collectors_and_lists_of_them() -> None:
    registry = discover(
        [
            _EntryPoint("one", lambda: Fake("one", "One")),
            _EntryPoint("many", lambda: [Fake("m1", "M1"), Fake("m2", "M2")]),
        ]
    )
    assert [c.info.id for c in registry.all()] == ["m1", "m2", "one"]
    assert registry.problems == []


def test_one_broken_plugin_does_not_hide_the_others() -> None:
    def broken() -> Any:
        raise ImportError("no module named gone")

    registry = discover(
        [
            _EntryPoint("good", lambda: Fake("good")),
            _EntryPoint("broken", broken),
            _EntryPoint("nonsense", lambda: 42),
            _EntryPoint("dupe", lambda: Fake("good")),
        ]
    )
    assert [c.info.id for c in registry.all()] == ["good"]
    problems = " | ".join(registry.problems)
    assert "broken" in problems and "gone" in problems
    assert "nonsense" in problems and "dupe" in problems and "already registered" in problems


def test_the_description_is_plain_json_for_the_ui() -> None:
    registry = discover([_EntryPoint("one", lambda: Fake("one", "One"))])
    description = registry.describe()
    json.dumps(description)
    (entry,) = description
    assert entry == {
        "id": "one",
        "name": "One",
        "platform": "Test",
        "inputs": ["file"],
        "how_to_export": "Press the button.",
        "options_schema": {"type": "object", "properties": {}},
        "source": "one",
    }


def test_the_real_entry_point_group_is_read_by_default() -> None:
    assert isinstance(discover(), Registry)  # no error whatever is installed


# --- The box --------------------------------------------------------------------------------


def test_a_box_has_the_folders_a_person_expects(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Our Family", name="Our Family")
    for folder in ("Messages", "Mail", "People", ".caixa/work", ".caixa/logs"):
        assert (box.root / folder).is_dir(), folder
    readme = (box.root / "README.md").read_text(encoding="utf-8")
    assert "Our Family" in readme and "Caixa" in readme
    assert json.loads((box.root / ".caixa" / "box.yaml").read_text())["name"] == "Our Family"


def test_a_box_can_be_reopened_and_not_recreated_over_itself(tmp_path: Path) -> None:
    created = Box.create(tmp_path / "box", name="Box")
    again = Box.open(tmp_path / "box")
    assert again.name == "Box" and again.root == created.root
    with pytest.raises(BoxError, match="already"):
        Box.create(tmp_path / "box", name="Other")


def test_opening_something_that_is_not_a_box_is_explained(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    with pytest.raises(BoxError, match="not a Caixa box"):
        Box.open(tmp_path / "plain")
    with pytest.raises(BoxError, match="not a Caixa box"):
        Box.open(tmp_path / "missing")


def test_creating_in_a_folder_that_has_files_keeps_them(tmp_path: Path) -> None:
    folder = tmp_path / "existing"
    folder.mkdir()
    (folder / "mine.txt").write_text("keep me")
    (folder / "README.md").write_text("my own readme")
    Box.create(folder, name="Existing")
    assert (folder / "mine.txt").read_text() == "keep me"
    assert (folder / "README.md").read_text() == "my own readme"


def test_status_counts_what_is_in_the_box(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "box", name="Box")
    status = box.status()
    assert status["name"] == "Box" and status["items"] == 0 and status["people"] == 0
    assert status["imports"] == [] and status["by_type"] == {}
    assert box.master_path == box.root / ".caixa" / "caixa.sqlite"
    assert box.work_dir("chattr") == box.root / ".caixa" / "work" / "chattr"
