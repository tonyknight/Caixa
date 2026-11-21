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


def test_the_swift_helper_is_in_the_repository_with_its_protocol() -> None:
    """It cannot be built here (it needs macOS 26); this checks it is the program Caixa runs."""
    package = (apple.PACKAGE / "Package.swift").read_text(encoding="utf-8")
    assert f'name: "{apple.PROGRAM}"' in package and '.macOS("26.0")' in package
    main = (apple.PACKAGE / "Sources" / apple.PROGRAM / "main.swift").read_text(encoding="utf-8")
    for needed in ("import FoundationModels", "SystemLanguageModel.default.availability",
                   "LanguageModelSession", "--check", "guardrailViolation",
                   "not_eligible", "not_enabled", "not_ready", "refused"):  # fmt: skip
        assert needed in main, needed
    assert (apple.PACKAGE / "README.md").is_file()


# --- Building with Xcode's Swift, on Apple silicon (bug 20261121-07) ------------------------------

import subprocess  # noqa: E402


class _Calls:
    """Stands in for subprocess.run: answers `--version` and `sysctl` as told, records the rest."""

    def __init__(
        self, version: str = "Apple Swift version 6.2 (swiftlang-6.2.0.19.9)", arm64: str = "1"
    ) -> None:
        self.version, self.arm64, self.seen = version, arm64, []

    def __call__(self, command, **kwargs):  # type: ignore[no-untyped-def]
        self.seen.append((list(command), kwargs.get("env")))
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout=self.version, stderr="")
        if command[:2] == ["sysctl", "-n"]:
            return subprocess.CompletedProcess(command, 0, stdout=self.arm64 + "\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


@pytest.fixture
def mac(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Calls:
    monkeypatch.delenv(apple.OVERRIDE, raising=False)
    monkeypatch.setattr(apple, "_is_mac", lambda: True)
    monkeypatch.setattr(apple, "PACKAGE", tmp_path / "apple-intelligence")
    monkeypatch.setattr(apple.shutil, "which", lambda name: f"/usr/bin/{name}")
    calls = _Calls()
    monkeypatch.setattr(apple.subprocess, "run", calls)
    return calls


def test_an_old_swift_is_refused_naming_its_version(mac: _Calls) -> None:
    mac.version = "Apple Swift version 5.0.3 (swift-5.0.3-RELEASE)"
    with pytest.raises(apple.AppleUnavailable) as error:
        apple.helper()
    said = str(error.value)
    assert "5.0.3" in said and "6.2" in said and "xcode-select" in said
    assert not any("build" in c for c, _ in mac.seen)  # nothing was built


def test_the_build_uses_xcodes_swift_without_a_toolchains_choice(
    mac: _Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOOLCHAINS", "swift-5.0.3-RELEASE")
    with pytest.raises(apple.AppleUnavailable):  # (the fake build makes no program)
        apple.helper()
    builds = [(c, env) for c, env in mac.seen if "build" in c]
    assert builds and builds[0][0][:3] == ["xcrun", "swift", "build"]
    assert builds[0][1] is not None and "TOOLCHAINS" not in builds[0][1]


def test_a_mac_without_apple_silicon_is_told_at_once(mac: _Calls) -> None:
    mac.arm64 = "0"
    found = apple.check()
    assert found["ready"] is False and found["reason"] == "not_eligible"
    assert not any("build" in c or c[-1] == "--version" for c, _ in mac.seen)
