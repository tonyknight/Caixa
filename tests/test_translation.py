"""Translation in Caixa: the settings, the key, the Test button, and translating during an import."""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family
from stub_server import StubServer

from caixa import settings, translation
from caixa.box import Box
from caixa.collectors.base import Collector, Progress
from caixa.collectors.options import OptionsError, validate
from caixa.collectors.registry import discover
from caixa.service import Service, ServiceError
from caixa.state import State

REMOTE = "https://openrouter.ai/api/v1"


@pytest.fixture
def server() -> Iterator[StubServer]:
    srv = StubServer()
    yield srv
    srv.close()


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box.create(tmp_path / "Box", "Test box")


def _on(box: Box, endpoint: str, **more: object) -> None:
    settings.save(
        box,
        {
            "translation.enabled": True,
            "translation.endpoint": endpoint,
            "translation.model": "test-model",
            **more,
        },
    )


# --- Settings -------------------------------------------------------------------------------------


def test_translation_is_off_until_someone_turns_it_on(box: Box) -> None:
    values = settings.load(box)
    assert values["translation.enabled"] is False and values["translation.allow_remote"] is False


def test_a_model_on_this_computer_needs_nothing_more(box: Box, server: StubServer) -> None:
    _on(box, server.endpoint)
    assert settings.load(box)["translation.endpoint"] == server.endpoint


def test_a_service_on_the_internet_needs_an_explicit_yes(box: Box) -> None:
    with pytest.raises(OptionsError) as refused:
        _on(box, REMOTE)
    assert "leave this computer" in str(refused.value)
    assert settings.load(box)["translation.enabled"] is False  # nothing was saved
    _on(box, REMOTE, **{"translation.allow_remote": True})
    assert settings.load(box)["translation.endpoint"] == REMOTE


@pytest.mark.parametrize(
    ("values", "words"),
    [
        ({"translation.enabled": True, "translation.model": "m"}, "no endpoint"),
        (
            {"translation.enabled": True, "translation.endpoint": "http://localhost:1/v1"},
            "no model",
        ),
        ({"translation.endpoint": "openrouter.ai"}, "not a web address"),
    ],
)
def test_settings_that_cannot_work_are_refused_in_words(box: Box, values: dict, words: str) -> None:
    with pytest.raises(OptionsError, match=words):
        settings.save(box, values)


# --- The key --------------------------------------------------------------------------------------


def test_the_key_is_kept_outside_the_box_and_only_its_owner_can_read_it(
    box: Box, tmp_path: Path
) -> None:
    keys = translation.Keys(tmp_path / "home")
    keys.set(REMOTE, "sk-secret-123")
    assert keys.get(REMOTE) == "sk-secret-123"
    if sys.platform != "win32":
        assert stat.S_IMODE(keys.path.stat().st_mode) == 0o600
    _on(box, REMOTE, **{"translation.allow_remote": True})
    inside = "".join(
        p.read_text("utf-8", "replace") for p in box.caixa_dir.rglob("*") if p.is_file()
    )
    assert "sk-secret-123" not in inside


def test_a_key_is_never_sent_to_another_host(tmp_path: Path) -> None:
    keys = translation.Keys(tmp_path / "home")
    keys.set(REMOTE, "sk-secret-123")
    assert keys.get("https://api.deepseek.com/v1") is None
    assert keys.get("https://openrouter.ai/api/v2") == "sk-secret-123"  # the same host
    keys.set(REMOTE, "")
    assert keys.get(REMOTE) is None and not keys.path.exists()


def test_the_interface_learns_only_that_a_key_is_saved(tmp_path: Path, server: StubServer) -> None:
    service = Service(roots=[tmp_path], state=State(tmp_path / "home"))
    service.call("box.create", {"path": str(tmp_path / "Box"), "name": "Test box"})
    service.call("settings.set", {"values": {"translation.endpoint": server.endpoint}})
    assert service.call("settings.get")["translation"] == {"key_saved": False}
    saved = service.call("translation.key", {"endpoint": server.endpoint, "key": "sk-secret-123"})
    assert saved == {"key_saved": True}
    reply = service.call("settings.get")
    assert reply["translation"] == {"key_saved": True} and "sk-secret-123" not in json.dumps(reply)


def test_a_key_is_not_saved_for_a_service_reached_without_https(tmp_path: Path) -> None:
    service = Service(roots=[tmp_path], state=State(tmp_path / "home"))
    with pytest.raises(ServiceError, match="https"):
        service.call("translation.key", {"endpoint": "http://example.org/v1", "key": "sk-1"})


# --- Trying it ------------------------------------------------------------------------------------


def test_the_test_sends_one_fixed_sentence_and_shows_the_answer(
    tmp_path: Path, server: StubServer
) -> None:
    service = Service(roots=[tmp_path], state=State(tmp_path / "home"))
    values = {"translation.endpoint": server.endpoint, "translation.model": "test-model"}
    reply = service.call("translation.test", {"values": values, "key": "sk-typed"})
    assert reply["ok"] and reply["translation"] == "I arrived! Let us have dinner."
    assert reply["sample"] == translation.SAMPLE and reply["local"] and reply["used_key"]
    (request,) = server.requests
    assert request["json"]["messages"][1]["content"] == translation.SAMPLE
    assert request["json"]["model"] == "test-model"
    assert request["headers"]["Authorization"] == "Bearer sk-typed"


def test_the_test_uses_the_saved_key_when_none_is_typed(tmp_path: Path, server: StubServer) -> None:
    service = Service(roots=[tmp_path], state=State(tmp_path / "home"))
    service.call("translation.key", {"endpoint": server.endpoint, "key": "sk-saved"})
    values = {"translation.endpoint": server.endpoint, "translation.model": "m"}
    assert service.call("translation.test", {"values": values})["ok"]
    assert server.requests[0]["headers"]["Authorization"] == "Bearer sk-saved"


def test_a_failing_test_says_why(tmp_path: Path, server: StubServer) -> None:
    service = Service(roots=[tmp_path], state=State(tmp_path / "home"))
    server.status, server.reply = 401, {"error": {"message": "No auth credentials found"}}
    values = {"translation.endpoint": server.endpoint, "translation.model": "m"}
    reply = service.call("translation.test", {"values": values})
    assert reply["ok"] is False and "refused the key" in reply["message"]
    assert "No auth credentials found" in reply["message"]
    missing = service.call("translation.test", {"values": {"translation.endpoint": ""}})
    assert missing["ok"] is False and "address" in missing["message"]


# --- During an import -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def messenger() -> Collector:
    return discover().get("messenger")


def _import(collector: Collector, box: Box, source: Path):
    events: list[Progress] = []
    result = collector.run(box, source, validate(collector.info.options_schema, {}), events.append)
    return result, events


def _page(box: Box) -> str:
    return "".join(p.read_text("utf-8") for p in (box.root / "People").rglob("(*.html"))


def test_an_import_translates_nothing_while_translation_is_off(
    messenger: Collector, fixture_family, box: Box, server: StubServer
) -> None:
    result, events = _import(messenger, box, fixture_family.paths["messenger"])
    assert result.translated == 0 and server.requests == []
    assert "translating" not in [e.stage for e in events]


def test_an_import_translates_what_needs_it_and_the_page_shows_it(
    messenger: Collector, fixture_family, box: Box, server: StubServer
) -> None:
    _on(box, server.endpoint)
    result, events = _import(messenger, box, fixture_family.paths["messenger"])
    assert result.translated >= 1 and result.translated == len(server.requests)
    assert result.warnings == []
    stages = [e.stage for e in events]
    assert stages.index("linking") < stages.index("translating") < stages.index("rendering")
    assert 'class="translation">I arrived! Let us have dinner.' in _page(box)
    # every request carried one message and the translate-only instruction, nothing else
    for request in server.requests:
        system, user = request["json"]["messages"]
        assert "Return only the translated text" in system["content"] and user["role"] == "user"
    again, _ = _import(messenger, box, fixture_family.paths["messenger"])
    assert again.translated == 0 and len(server.requests) == result.translated  # never sent twice


def test_a_translation_service_that_is_down_does_not_fail_the_import(
    messenger: Collector, fixture_family, box: Box
) -> None:
    _on(box, "http://127.0.0.1:9/v1")
    result, _ = _import(messenger, box, fixture_family.paths["messenger"])
    assert result.inserted > 0 and result.translated == 0
    (note,) = [w for w in result.warnings if "ranslat" in w]
    assert "Could not reach the translation server" in note and "Test" in note
