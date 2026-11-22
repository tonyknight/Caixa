"""Apple Intelligence: the Mac's own on-device model, for summaries and translation.

Apple's Foundation Models (macOS 26 or later, Apple silicon, Apple Intelligence turned on) can only
be called from Swift, so Caixa carries a small Swift program, `tools/apple-intelligence/`, and talks
to it over its input and output:

- `caixa-apple-intelligence --check` prints `{"ready": true}`, or `{"ready": false, "reason",
  "message"}` saying why the model cannot be used (`not_eligible`, `not_enabled`, `not_ready`);
- without arguments it reads one request per line, `{"id", "instructions", "prompt",
  "temperature"}`, and writes one answer per line, `{"id", "text"}` or `{"id", "error",
  "refused"}` (`refused`: the model's safety filter declined it).

`helper()` builds the program the first time it is needed (`swift build -c release`, which needs
Xcode or its command-line tools) and says which command to run when it cannot. `AppleIntelligence`
runs several helpers at once and lends each request to a free one; it answers the same `chat` and
`translate` calls as Chattr's OpenAI-compatible client, so summaries and translation use either.
Nothing leaves the Mac.

`CAIXA_APPLE_INTELLIGENCE`, when set, is the command to run instead of the built helper (the tests
use a stand-in that speaks the same protocol).
"""

from __future__ import annotations

import itertools
import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

from chattr.translation import INSTRUCTION, Translation, TranslationError, clean_reply

#: The command to run instead of the built helper.
OVERRIDE = "CAIXA_APPLE_INTELLIGENCE"
#: The Swift package, in the repository beside Chattr.
PACKAGE = Path(__file__).resolve().parents[1] / "tools" / "apple-intelligence"
PROGRAM = "caixa-apple-intelligence"
NAME = "Apple Intelligence"

#: Why the model cannot be used, in words a person can act on.
REASONS = {
    "not_a_mac": "Apple Intelligence runs only on a Mac (macOS 26 or later, Apple silicon).",
    "not_eligible": "This Mac cannot run Apple Intelligence (it needs Apple silicon and macOS 26 "
    "or later).",
    "not_enabled": "Apple Intelligence is turned off. Turn it on in System Settings, Apple "
    "Intelligence & Siri.",
    "not_ready": "Apple Intelligence is not ready yet (its model may still be downloading). Try "
    "again later.",
    "not_built": "Caixa's Apple Intelligence helper is not built.",
}


class AppleUnavailable(TranslationError):
    """Apple Intelligence cannot be used here (the message says why)."""


class Declined(TranslationError):
    """The model's safety filter declined this request."""


def _is_mac() -> bool:
    return sys.platform == "darwin"


#: The oldest Swift that has Apple's Foundation Models (the one Xcode 26 brings).
SWIFT_NEEDED = (6, 2)


def _swift() -> list[str]:
    """Xcode's own Swift (`xcrun swift`), not whatever `swift` comes first on the PATH (an old
    toolchain from swift.org there cannot build the helper); plain `swift` without `xcrun`."""
    return ["xcrun", "swift"] if shutil.which("xcrun") else ["swift"]


def _build_environment() -> dict[str, str]:
    """The environment without `TOOLCHAINS`, which would choose another toolchain over Xcode's."""
    return {k: v for k, v in os.environ.items() if k != "TOOLCHAINS"}


def _build_command() -> list[str]:
    return [*_swift(), "build", "-c", "release", "--package-path", str(PACKAGE)]


def _apple_silicon() -> bool:
    """Whether this Mac has Apple silicon (also true for a program run through Rosetta). When the
    Mac does not say, it is taken to have it, and the model's own check decides."""
    try:
        said = subprocess.run(
            ["sysctl", "-n", "hw.optional.arm64"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    answer = (said.stdout or "").strip()
    return answer != "0" if said.returncode == 0 and answer else True


def _swift_version() -> Optional[tuple[tuple[int, int], str]]:
    """The Swift that would build the helper: (major, minor) and the version as it says it."""
    try:
        said = subprocess.run(
            [*_swift(), "--version"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=_build_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    found = re.search(r"Swift version ((\d+)\.(\d+)[\d.]*)", f"{said.stdout}\n{said.stderr}")
    if not found:
        return None
    return (int(found.group(2)), int(found.group(3))), found.group(1)


def _built() -> Path:
    return PACKAGE / ".build" / "release" / PROGRAM


def _stale(program: Path) -> bool:
    if not program.is_file():
        return True
    built = program.stat().st_mtime
    sources = [PACKAGE / "Package.swift", *(PACKAGE / "Sources").rglob("*.swift")]
    return any(s.is_file() and s.stat().st_mtime > built for s in sources)


_build_lock = threading.Lock()


def helper() -> list[str]:
    """The command that runs the helper, building it first when it is missing or older than its
    sources (raises `AppleUnavailable`, naming the command to run, when that cannot be done)."""
    given = os.environ.get(OVERRIDE, "").strip()
    if given:
        return shlex.split(given)
    if not _is_mac():
        raise AppleUnavailable(REASONS["not_a_mac"])
    if not _apple_silicon():
        raise AppleUnavailable(REASONS["not_eligible"])
    command = " ".join(shlex.quote(part) for part in _build_command())
    with _build_lock:
        program = _built()
        if _stale(program):
            if shutil.which("xcrun") is None and shutil.which("swift") is None:
                raise AppleUnavailable(
                    f"{REASONS['not_built']} It needs Xcode or its command-line tools "
                    f"(xcode-select --install); then run: {command}"
                )
            version = _swift_version()
            if version is not None and version[0] < SWIFT_NEEDED:
                raise AppleUnavailable(
                    f"{REASONS['not_built']} The Swift it found is {version[1]}; "
                    f"Apple Intelligence needs Swift {SWIFT_NEEDED[0]}.{SWIFT_NEEDED[1]}, which "
                    "comes with Xcode 26. Install Xcode 26 and select it (sudo xcode-select -s "
                    "/Applications/Xcode.app); an older toolchain in ~/Library/Developer/Toolchains "
                    f"or a TOOLCHAINS setting can hide it. Then run: {command}"
                )
            try:
                subprocess.run(
                    _build_command(),
                    check=True,
                    capture_output=True,
                    timeout=1800,
                    env=_build_environment(),
                )
            except (OSError, subprocess.SubprocessError) as error:
                said = getattr(error, "stderr", b"") or b""
                tail = said.decode("utf-8", "replace").strip().splitlines()[-3:]
                raise AppleUnavailable(
                    f"{REASONS['not_built']} Building it failed"
                    + (f" ({' / '.join(tail)})" if tail else "")
                    + f". Run it yourself to see why: {command}"
                ) from error
            if not program.is_file():
                raise AppleUnavailable(f"{REASONS['not_built']} Run: {command}")
    return [str(program)]


def check(build: bool = True) -> dict[str, Any]:
    """`{ready, reason, message}`: whether the Mac's model can be used now, or why not. Without
    `build`, a helper that is not built yet is reported (`not_built`) rather than built."""
    if not os.environ.get(OVERRIDE, "").strip() and _is_mac() and not _apple_silicon():
        return {"ready": False, "reason": "not_eligible", "message": REASONS["not_eligible"]}
    if not build and not os.environ.get(OVERRIDE, "").strip() and _is_mac() and _stale(_built()):
        return {"ready": False, "reason": "not_built", "message": REASONS["not_built"] + " It is built "
                "when Apple Intelligence is chosen and tested (this needs Xcode or its command-line "
                "tools)."}  # fmt: skip
    try:
        command = helper()
    except AppleUnavailable as error:
        reason = "not_a_mac" if not _is_mac() and not os.environ.get(OVERRIDE) else "not_built"
        return {"ready": False, "reason": reason, "message": str(error)}
    try:
        done = subprocess.run(
            [*command, "--check"], capture_output=True, text=True, timeout=60, check=False
        )
        answer = json.loads(done.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as error:
        return {
            "ready": False,
            "reason": "unavailable",
            "message": f"The helper did not answer: {error}",
        }
    if answer.get("ready"):
        return {"ready": True, "reason": None, "message": ""}
    reason = str(answer.get("reason") or "unavailable")
    return {
        "ready": False,
        "reason": reason,
        "message": REASONS.get(reason)
        or str(answer.get("message") or "Apple Intelligence is not available."),
    }


class _Helper:
    """One running helper: a request in, its answer out, one at a time."""

    def __init__(self, command: list[str]) -> None:
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def ask(self, request: dict[str, Any]) -> dict[str, Any]:
        assert self.process.stdin is not None and self.process.stdout is not None
        try:
            self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
            line = self.process.stdout.readline()
        except (OSError, ValueError) as error:
            raise TranslationError(f"Apple Intelligence stopped answering: {error}") from error
        if not line:
            raise TranslationError("Apple Intelligence stopped answering.")
        answer: dict[str, Any] = json.loads(line)
        return answer

    def close(self) -> None:
        try:
            if self.process.stdin:
                self.process.stdin.close()
            self.process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            self.process.kill()


class AppleIntelligence:
    """The Mac's model through `workers` helpers at once (started when first needed).

    Answers `chat(messages)` like Chattr's OpenAI-compatible client: the system messages are the
    instructions, the rest the prompt (an earlier answer and a note, for a retry, follow the first
    request). `translate(text)` uses Chattr's translation instruction."""

    server_name = NAME
    model = NAME
    api_key = None

    def __init__(self, workers: int = 4, target_language: str = "English") -> None:
        self.workers = max(1, int(workers))
        self.target_language = target_language
        self.retries = 0
        self._idle: queue.Queue[_Helper] = queue.Queue()
        self._all: list[_Helper] = []
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    def __enter__(self) -> "AppleIntelligence":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _take(self) -> _Helper:
        with self._lock:
            if self._idle.empty() and len(self._all) < self.workers:
                started = _Helper(helper())
                self._all.append(started)
                return started
        return self._idle.get()

    def chat(
        self, messages: list[dict[str, str]], temperature: float = 0
    ) -> tuple[str, dict[str, Any]]:
        instructions = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        turns = [m for m in messages if m["role"] != "system"]
        if len(turns) == 1:
            prompt = turns[0]["content"]
        else:
            labels = {"user": "Request", "assistant": "Your earlier answer"}
            prompt = "\n\n".join(
                f"{labels.get(m['role'], m['role'])}:\n{m['content']}" for m in turns
            )
        request = {
            "id": next(self._ids),
            "instructions": instructions,
            "prompt": prompt,
            "temperature": temperature,
        }
        one = self._take()
        try:
            answer = one.ask(request)
        except TranslationError:
            with self._lock:  # a helper that stopped is not lent again
                if one in self._all:
                    self._all.remove(one)
            one.close()
            raise
        self._idle.put(one)
        if answer.get("refused"):
            raise Declined(f"{NAME} declined this: {answer.get('error') or 'its safety filter'}.")
        if "error" in answer:
            raise TranslationError(f"{NAME} could not answer: {answer['error']}")
        return str(answer.get("text") or ""), {}

    def translate(self, text: str) -> Translation:
        reply, _ = self.chat(
            [
                {"role": "system", "content": INSTRUCTION.format(language=self.target_language)},
                {"role": "user", "content": text},
            ]
        )
        return Translation(clean_reply(text, reply))

    def close(self) -> None:
        with self._lock:
            helpers, self._all = self._all, []
        for one in helpers:
            one.close()


_remembered: dict[str, tuple[float, bool]] = {}
#: How long an answer to "can Apple Intelligence be used?" is trusted.
REMEMBER_SECONDS = 600


def available() -> bool:
    """Whether Apple Intelligence can be used now (building its helper the first time), the answer
    remembered for ten minutes: Automatic asks this before every summary and translation run."""
    key = os.environ.get(OVERRIDE, "")
    now = time.monotonic()
    found = _remembered.get(key)
    if found and now - found[0] < REMEMBER_SECONDS:
        return found[1]
    ready = bool(check()["ready"])
    _remembered[key] = (now, ready)
    return ready


def forget() -> None:
    """Ask again next time (after the helper was built, or Apple Intelligence turned on)."""
    _remembered.clear()


def provider(workers: int, target_language: str = "English") -> Optional[AppleIntelligence]:
    """The Mac's model with `workers` helpers, or None when it cannot be used."""
    return AppleIntelligence(workers, target_language) if check()["ready"] else None
