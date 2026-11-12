"""`caixa worker` over its real stdio: every method, notifications, errors and `--read-only`."""

from __future__ import annotations

import io
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterator, Optional

import pytest
from fixtures import family

from caixa.service import Service
from caixa.worker import Worker

ALL_METHODS = {
    "box.create",
    "box.open",
    "box.status",
    "collectors.list",
    "import.preview",
    "import.preview.cancel",
    "import.start",
    "import.cancel",
    "jobs.list",
    "jobs.get",
    "jobs.log",
    "people.list",
    "people.unresolved",
    "people.link",
    "people.merge",
    "people.rename",
    "browse.list",
    "browse.file",
    "settings.get",
    "settings.set",
    "files.list",
    "inbox.list",
    "session.get",
    "session.set",
    "session.forget",
    "diagnostics.report",
}


class Client:
    """Talks to a worker process the way the harness does: one JSON object per line."""

    def __init__(self, *args: str, cwd: Path) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-m", "caixa.worker", *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=cwd,
        )
        self.messages: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self.notifications: list[dict[str, Any]] = []
        self.stray: list[str] = []  # lines on stdout that were not JSON-RPC (there must be none)
        self._next = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                message = json.loads(line)
                assert message["jsonrpc"] == "2.0"
            except (ValueError, AssertionError, KeyError, TypeError):
                self.stray.append(line)
                continue
            self.messages.put(message)

    def send_raw(self, text: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(text + "\n")
        self.process.stdin.flush()

    def _await(self, wanted: Any, timeout: float) -> dict[str, Any]:
        deadline = time.time() + timeout
        while True:
            message = self.messages.get(timeout=max(0.01, deadline - time.time()))
            if "id" not in message:
                self.notifications.append(message)
                continue
            if message["id"] == wanted:
                return message

    def call(self, method: str, timeout: float = 60, **params: Any) -> dict[str, Any]:
        """The whole response (result or error)."""
        self._next += 1
        self.send_raw(
            json.dumps({"jsonrpc": "2.0", "id": self._next, "method": method, "params": params})
        )
        return self._await(self._next, timeout)

    def result(self, method: str, **params: Any) -> Any:
        response = self.call(method, **params)
        assert "error" not in response, response
        return response["result"]

    def wait_notification(self, name: str, timeout: float = 60, **match: Any) -> dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for note in self.notifications:
                if note["method"] == name and all(
                    note["params"].get(k) == v for k, v in match.items()
                ):
                    return note
            try:
                message = self.messages.get(timeout=0.05)
            except queue.Empty:
                continue
            if "id" not in message:
                self.notifications.append(message)
        raise AssertionError(f"no {name} notification; saw {self.notifications}")

    def close(self) -> int:
        assert self.process.stdin is not None
        self.process.stdin.close()
        code = self.process.wait(timeout=60)
        for stream in (self.process.stdout, self.process.stderr):
            if stream:
                stream.close()
        return code


@pytest.fixture
def worker(tmp_path: Path) -> Iterator[Client]:
    client = Client("--root", str(tmp_path), "--inbox-poll", "0.05", cwd=tmp_path)
    yield client
    if client.process.poll() is None:
        client.close()
    assert client.stray == []  # nothing but the protocol ever reached stdout


def _created(worker: Client, tmp_path: Path) -> dict[str, Any]:
    return worker.result(
        "box.create", path=str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name
    )


def _whatsapp(fixture_family) -> str:
    return str(fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt")


# --- The basics -----------------------------------------------------------------------------


def test_the_worker_describes_itself(worker: Client) -> None:
    info = worker.result("worker.info")
    assert info["protocol"] == 1 and info["read_only"] is False
    assert ALL_METHODS <= set(info["methods"])


def test_every_documented_method_exists() -> None:
    assert ALL_METHODS == set(Service.METHODS)


def test_a_box_is_made_and_described_over_the_wire(worker: Client, tmp_path: Path) -> None:
    status = _created(worker, tmp_path)
    assert status["name"] == "Our box" and status["owner"] == family.OWNER.name
    assert worker.result("box.status")["items"] == 0
    ids = {c["id"] for c in worker.result("collectors.list")}
    assert {"imessage", "whatsapp", "messenger", "mail", "googlevoice", "voicemail"} <= ids
    assert worker.result("settings.get")["values"]["privacy.default"] == "private"
    assert worker.result("browse.list")["entries"]
    assert worker.result("files.list")["path"] == str(tmp_path)


def test_a_worker_can_start_with_a_box_already_open(tmp_path: Path) -> None:
    first = Client("--root", str(tmp_path), cwd=tmp_path)
    first.result("box.create", path=str(tmp_path / "Box"), name="Our box")
    first.close()
    second = Client("--box", str(tmp_path / "Box"), cwd=tmp_path)
    try:
        assert second.result("box.status")["name"] == "Our box"
    finally:
        second.close()
    assert second.stray == []


def test_a_worker_started_with_no_box_reopens_the_last_one(tmp_path: Path) -> None:
    first = Client("--root", str(tmp_path), cwd=tmp_path)
    first.result("box.create", path=str(tmp_path / "Box"), name="Our box")
    first.result("session.set", values={"view": "jobs", "draft": {"step": "options"}})
    first.close()
    second = Client("--root", str(tmp_path), cwd=tmp_path)  # no --box: what stopping lost before
    try:
        assert second.result("box.status")["name"] == "Our box"
        session = second.result("session.get")
        assert session["view"] == "jobs" and session["draft"] == {"step": "options"}
        assert [b["name"] for b in session["recent"]] == ["Our box"]
    finally:
        second.close()
    assert second.stray == []


def test_a_box_that_has_gone_is_not_reopened_and_is_not_an_error(tmp_path: Path) -> None:
    first = Client("--root", str(tmp_path), cwd=tmp_path)
    first.result("box.create", path=str(tmp_path / "Box"), name="Our box")
    first.close()
    shutil.rmtree(tmp_path / "Box")
    second = Client("--root", str(tmp_path), cwd=tmp_path)
    try:
        assert second.call("box.status")["error"]["data"]["kind"] == "no_box"
        recent = second.result("session.get")["recent"]
        assert [(b["name"], b["exists"]) for b in recent] == [("Our box", False)]
    finally:
        second.close()


def test_a_box_named_on_the_command_line_wins_over_the_last_one(tmp_path: Path) -> None:
    first = Client("--root", str(tmp_path), cwd=tmp_path)
    first.result("box.create", path=str(tmp_path / "Old"), name="Old box")
    first.result("box.create", path=str(tmp_path / "New"), name="New box")
    first.close()
    second = Client("--box", str(tmp_path / "Old"), cwd=tmp_path)
    try:
        assert second.result("box.status")["name"] == "Old box"
    finally:
        second.close()


def test_a_worker_told_to_open_a_missing_box_says_so_and_stops(tmp_path: Path) -> None:
    client = Client("--box", str(tmp_path / "nothing"), cwd=tmp_path)
    assert client.process.wait(timeout=60) == 1
    assert "not a Caixa box" in (client.process.stderr.read() if client.process.stderr else "")


# --- Imports with notifications -------------------------------------------------------------


def test_an_import_is_followed_by_notifications(
    worker: Client, tmp_path: Path, fixture_family
) -> None:
    _created(worker, tmp_path)
    preview = worker.result(
        "import.preview", collector="whatsapp", source=_whatsapp(fixture_family)
    )
    assert preview["items"] == 7
    job = worker.result("import.start", collector="whatsapp", source=_whatsapp(fixture_family))
    finished = worker.wait_notification("job.finished", job=job["id"])
    assert finished["params"]["status"] == "done" and finished["params"]["result"]["inserted"] == 7
    stages = [
        n["params"]["stage"]
        for n in worker.notifications
        if n["method"] == "job.progress" and n["params"]["job"] == job["id"]
    ]
    order = ["preparing", "importing", "linking", "filing", "rendering", "syncing", "done"]
    assert stages[0] == "preparing" and stages[-1] == "done"
    assert stages == sorted(stages, key=order.index)
    assert worker.result("jobs.get", job=job["id"])["status"] == "done"
    assert [j["id"] for j in worker.result("jobs.list")] == [job["id"]]
    assert worker.result("box.status")["items"] == 7
    page = worker.result("browse.file", path="People/Ana Costa/(2024) Ana Costa.html")
    assert "Que lindo! Buy two." in page["content"]


def test_people_changes_go_over_the_wire(worker: Client, tmp_path: Path, fixture_family) -> None:
    _created(worker, tmp_path)
    job = worker.result("import.start", collector="whatsapp", source=_whatsapp(fixture_family))
    worker.wait_notification("job.finished", job=job["id"])
    handles = worker.result("people.unresolved")["handles"]
    assert [h["identifier"] for h in handles] == ["Ana Costa"]
    linked = worker.result(
        "people.link", service="WhatsApp", identifier="Ana Costa", person="Ana (daughter)"
    )
    worker.wait_notification("job.finished", job=linked["job"]["id"])
    assert worker.result("people.unresolved")["handles"] == []
    assert worker.result("browse.list", path="People/Ana (daughter)")["entries"]


def test_a_collectors_printing_never_reaches_the_protocol(
    worker: Client, tmp_path: Path, fixture_family
) -> None:
    _created(worker, tmp_path)
    job = worker.result("import.start", collector="whatsapp", source=_whatsapp(fixture_family))
    worker.wait_notification("job.finished", job=job["id"])
    log = Path(worker.result("jobs.get", job=job["id"])["log"])
    assert log.read_text(encoding="utf-8").strip()  # the chatter went to the log
    # (the fixture fails the test at teardown if a single stray line reached stdout)


def test_a_failed_import_is_a_notification_with_a_plain_error(
    worker: Client, tmp_path: Path
) -> None:
    _created(worker, tmp_path)
    (tmp_path / "empty").mkdir()
    job = worker.result("import.start", collector="whatsapp", source=str(tmp_path / "empty"))
    finished = worker.wait_notification("job.finished", job=job["id"])
    assert finished["params"]["status"] == "failed"
    assert "Nothing to import" in finished["params"]["error"]


# --- The inbox ------------------------------------------------------------------------------


def test_a_file_dropped_in_the_inbox_is_announced(worker: Client, tmp_path: Path) -> None:
    _created(worker, tmp_path)
    time.sleep(0.3)  # let the watcher take its first look
    (tmp_path / "Box" / "Inbox" / "chat.zip").write_bytes(b"zip")
    note = worker.wait_notification("inbox.changed", timeout=30)
    assert [e["name"] for e in note["params"]["entries"]] == ["chat.zip"]
    assert worker.result("inbox.list")["entries"][0]["name"] == "chat.zip"


# --- Errors ---------------------------------------------------------------------------------


def test_errors_use_json_rpc_codes_and_say_why(worker: Client, tmp_path: Path) -> None:
    unknown = worker.call("no.such.method")
    assert (
        unknown["error"]["code"] == -32601 and unknown["error"]["data"]["kind"] == "unknown_method"
    )
    no_box = worker.call("box.status")
    assert no_box["error"]["code"] == -32000 and no_box["error"]["data"]["kind"] == "no_box"
    _created(worker, tmp_path)
    bad = worker.call("import.preview", collector="whatsapp")  # source missing
    assert bad["error"]["code"] == -32602 and "source" in bad["error"]["message"]
    options = worker.call(
        "import.preview", collector="imessage", source=str(tmp_path), options={"workers": 0}
    )
    assert options["error"]["code"] == -32602 and options["error"]["data"]["errors"]
    missing = worker.call("browse.file", path="People/nothing.html")
    assert missing["error"]["data"]["kind"] == "not_found"


def test_malformed_requests_are_answered_not_fatal(worker: Client) -> None:
    worker.send_raw("this is not json")
    assert worker._await(None, 30)["error"]["code"] == -32700
    worker.send_raw(json.dumps([1, 2, 3]))
    assert worker._await(None, 30)["error"]["code"] == -32600
    worker.send_raw(json.dumps({"jsonrpc": "2.0", "id": 7, "method": "box.status", "params": [1]}))
    assert worker._await(7, 30)["error"]["code"] == -32602
    assert worker.result("worker.info")["protocol"] == 1  # still alive


def test_a_notification_gets_no_answer(worker: Client) -> None:
    worker.send_raw(json.dumps({"jsonrpc": "2.0", "method": "worker.info"}))
    assert worker.result("worker.info")  # the next real request is the next answer


def test_closing_stdin_ends_the_worker_cleanly(worker: Client) -> None:
    assert worker.close() == 0


# --- Read-only ------------------------------------------------------------------------------


@pytest.fixture
def viewer(tmp_path: Path) -> Iterator[Client]:
    maker = Client("--root", str(tmp_path), cwd=tmp_path)
    maker.result("box.create", path=str(tmp_path / "Box"), name="Our box", owner="Maria Costa")
    maker.close()
    client = Client(
        "--box", str(tmp_path / "Box"), "--read-only", "--root", str(tmp_path), cwd=tmp_path
    )
    yield client
    if client.process.poll() is None:
        client.close()
    assert client.stray == []


def test_read_only_reads_everything(viewer: Client) -> None:
    assert viewer.result("worker.info")["read_only"] is True
    assert viewer.result("box.status")["owner"] == "Maria Costa"
    assert viewer.result("jobs.list") == [] and viewer.result("people.list")["people"]
    assert viewer.result("people.unresolved") == {"handles": []}
    viewer.result("settings.get")
    viewer.result("browse.list")
    viewer.result("inbox.list")
    assert viewer.result("collectors.list")


@pytest.mark.parametrize(
    "method, params",
    [
        ("box.create", {"path": "/tmp/never"}),
        ("import.start", {"collector": "whatsapp", "source": "/tmp/x"}),
        ("import.cancel", {"job": 1}),
        ("people.link", {"service": "WhatsApp", "identifier": "x", "person": "Someone"}),
        ("people.rename", {"person": 1, "name": "New"}),
        ("people.merge", {"source": 1, "target": 2}),
        ("settings.set", {"values": {"privacy.default": "public"}}),
        ("import.start", {}),  # refused even before its parameters are looked at
    ],
)
def test_read_only_refuses_every_write_method(viewer: Client, method: str, params: dict) -> None:
    response = viewer.call(method, **params)
    assert response["error"]["data"]["kind"] == "read_only", response
    assert "read-only" in response["error"]["message"]


def test_the_write_methods_are_exactly_the_ones_read_only_refuses() -> None:
    writes = {name for name, m in Service.METHODS.items() if m.write}
    assert writes == {
        "box.create",
        "import.start",
        "import.cancel",
        "people.link",
        "people.rename",
        "people.merge",
        "settings.set",
    }


def test_read_only_changes_nothing_on_disk(tmp_path: Path) -> None:
    maker = Client("--root", str(tmp_path), cwd=tmp_path)
    maker.result("box.create", path=str(tmp_path / "Box"), owner="Maria Costa")
    maker.close()

    def files() -> dict[str, bytes]:
        return {
            str(p.relative_to(tmp_path)): p.read_bytes()
            for p in sorted((tmp_path / "Box").rglob("*"))
            if p.is_file() and not p.name.endswith(("-wal", "-shm"))
        }

    before = files()
    client = Client("--box", str(tmp_path / "Box"), "--read-only", cwd=tmp_path)
    for method in ("box.status", "jobs.list", "people.list", "settings.get", "browse.list"):
        client.result(method)
    client.call("settings.set", values={"privacy.default": "public"})
    client.close()
    assert files() == before


# --- Concurrency (in process, with a collector that waits) ---------------------------------


def test_a_long_job_never_blocks_other_requests(tmp_path: Path) -> None:
    from caixa.collectors.registry import Registry
    from tests.test_service_jobs import Fake  # the waiting collector

    fake = Fake()
    registry = Registry()
    registry.register(fake, "test")
    service = Service(registry=registry, roots=[tmp_path])
    service.box_create(str(tmp_path / "Box"))
    reader, writer = os.pipe()
    out = io.StringIO()
    worker = Worker(service, out, inbox_poll=60)
    thread = threading.Thread(
        target=worker.serve, args=(os.fdopen(reader, encoding="utf-8"),), daemon=True
    )
    thread.start()
    send = os.fdopen(writer, "w", encoding="utf-8")
    source = tmp_path / "x.txt"
    source.write_text("x")

    def ask(number: int, method: str, **params: Any) -> None:
        send.write(
            json.dumps({"jsonrpc": "2.0", "id": number, "method": method, "params": params}) + "\n"
        )
        send.flush()

    def answers() -> dict[Any, dict[str, Any]]:
        return {m["id"]: m for m in map(json.loads, out.getvalue().splitlines()) if "id" in m}

    ask(1, "import.start", collector="fake", source=str(source), options={"mode": "wait"})
    assert fake.started.wait(30)
    ask(2, "jobs.list")
    ask(3, "import.cancel", job=answers_wait(answers, 1)["result"]["id"])
    deadline = time.time() + 30
    while time.time() < deadline and not {2, 3} <= set(answers()):
        time.sleep(0.02)
    assert {2, 3} <= set(answers())  # answered while the import was still running
    fake.release.set()
    send.close()
    thread.join(timeout=60)
    assert not thread.is_alive()


def answers_wait(answers: Any, number: int) -> dict[str, Any]:
    deadline = time.time() + 30
    while time.time() < deadline:
        found = answers()
        if number in found:
            return found[number]  # type: ignore[no-any-return]
        time.sleep(0.02)
    raise AssertionError(f"no answer to request {number}")
