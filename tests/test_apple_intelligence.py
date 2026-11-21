"""Apple Intelligence through its helper: ready or why not, several helpers at once, and a refusal.

The Swift helper cannot run here; `stand_in_apple.py` speaks its protocol."""

from __future__ import annotations

import shlex
import sys
import time
from pathlib import Path

import pytest
from chattr.translation import Translation, TranslationError

from caixa import apple_intelligence as apple

STAND_IN = Path(__file__).with_name("stand_in_apple.py")


@pytest.fixture
def stand_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        apple.OVERRIDE, f"{shlex.quote(sys.executable)} {shlex.quote(str(STAND_IN))}"
    )


def test_check_says_ready(stand_in: None) -> None:
    assert apple.check() == {"ready": True, "reason": None, "message": ""}


def test_check_says_why_not(stand_in: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAND_IN_APPLE", "not_enabled")
    found = apple.check()
    assert found["ready"] is False and found["reason"] == "not_enabled" and found["message"]


def test_anything_but_a_mac_is_told_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(apple.OVERRIDE, raising=False)
    monkeypatch.setattr(apple, "_is_mac", lambda: False)
    found = apple.check()
    assert found["ready"] is False and found["reason"] == "not_a_mac"


def test_without_swift_the_message_names_the_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(apple.OVERRIDE, raising=False)
    monkeypatch.setattr(apple, "_is_mac", lambda: True)
    monkeypatch.setattr(apple, "PACKAGE", tmp_path / "apple-intelligence")
    monkeypatch.setattr(apple.shutil, "which", lambda name: None)
    with pytest.raises(apple.AppleUnavailable) as error:
        apple.helper()
    assert "swift build -c release --package-path" in str(error.value)
    assert apple.check()["reason"] == "not_built"


def test_answers_come_back_for_each_request(stand_in: None) -> None:
    with apple.AppleIntelligence(workers=2) as model:
        text, usage = model.chat(
            [{"role": "system", "content": "Be brief please"}, {"role": "user", "content": "Hello"}]
        )
        assert text == "3 | Hello" and usage == {}
        assert model.chat([{"role": "user", "content": "Again"}])[0] == "0 | Again"


def test_a_retry_carries_the_earlier_answer_in_the_prompt(stand_in: None) -> None:
    with apple.AppleIntelligence(workers=1) as model:
        text, _ = model.chat(
            [
                {"role": "system", "content": "Summarize"},
                {"role": "user", "content": "The conversation"},
                {"role": "assistant", "content": "Too long an answer"},
                {"role": "user", "content": "Shorter, please"},
            ]
        )
    assert "The conversation" in text and "Too long an answer" in text and "Shorter, please" in text


def test_several_helpers_answer_at_once(stand_in: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("STAND_IN_APPLE_DELAY", "0.4")
    with apple.AppleIntelligence(workers=4) as model:
        model.chat([{"role": "user", "content": "warm up"}])  # (the helpers have started)
        started = time.monotonic()
        with ThreadPoolExecutor(4) as pool:
            answers = list(
                pool.map(lambda n: model.chat([{"role": "user", "content": f"n{n}"}])[0], range(4))
            )
        took = time.monotonic() - started
    assert answers == [f"0 | n{n}" for n in range(4)]
    assert took < 1.2  # one after another would take 1.6 s


def test_a_declined_request_raises_declined(stand_in: None) -> None:
    with apple.AppleIntelligence(workers=1) as model:
        with pytest.raises(apple.Declined) as declined:
            model.chat([{"role": "user", "content": "DECLINE this"}])
        assert isinstance(declined.value, TranslationError)
        assert model.chat([{"role": "user", "content": "still works"}])[0] == "0 | still works"


def test_it_translates_like_the_endpoint_client(stand_in: None) -> None:
    with apple.AppleIntelligence(workers=1) as model:
        result = model.translate("Bom dia")
    assert isinstance(result, Translation) and result.text.endswith("| Bom dia")
    assert model.model == "Apple Intelligence" and model.api_key is None
