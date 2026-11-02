"""`caixa serve`, part 2: starting, supervising, reattaching and stopping the harness."""

from __future__ import annotations

import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest

from caixa import serve
from caixa.serve import ServeError

FAKE = Path(__file__).parent / "fake_dsh.py"
TOKEN = "SECRET-TOKEN-0123456789"


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # a zombie is not alive
        return Path(f"/proc/{pid}/stat").read_text().split(")")[1].split()[0] != "Z"
    except OSError:
        return True


def wait_for(condition, seconds: float = 20) -> bool:  # type: ignore[no-untyped-def]
    end = time.time() + seconds
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "caixa-home"


@pytest.fixture
def prepared(tmp_path: Path, home: Path, monkeypatch: pytest.MonkeyPatch) -> serve.Prepared:
    monkeypatch.setenv("FAKE_PIDFILE", str(tmp_path / "pids"))
    node = tmp_path / "node"
    node.write_text("#!/bin/sh\necho v24.9.0\n")
    node.chmod(0o755)
    env = serve.child_env(serve.Node(node, (24, 9, 0)), serve.dsh_home(home))
    env["FAKE_PIDFILE"] = str(tmp_path / "pids")
    return serve.Prepared(FAKE, serve.dsh_home(home), env)


def pids(tmp_path: Path) -> tuple[int, int]:
    wait_for(
        lambda: (tmp_path / "pids").exists() and (tmp_path / "pids").read_text().count("\n") >= 3
    )
    first = (tmp_path / "pids").read_text().splitlines()[0].split()
    return int(first[0]), int(first[1])


@pytest.fixture(autouse=True)
def cleanup(home: Path) -> Iterator[None]:
    yield
    state = serve.read_state(home, check=False)
    if state:
        serve.stop_group(state["pid"], grace=1)


# --- Starting -------------------------------------------------------------------------------


def test_start_reads_the_link_checks_it_answers_and_saves_the_state(
    tmp_path: Path, home: Path, prepared: serve.Prepared
) -> None:
    patch = serve.write_patch(home, None, False, sys.executable)
    running = serve.start(prepared, patch, 0, home, box=None, read_only=False)
    assert re.fullmatch(r"http://127\.0\.0\.1:\d+/\?token=" + TOKEN, running.url)
    assert running.port > 0 and alive(running.pid)
    state = json.loads((home / "serve.json").read_text())
    assert (
        state["pid"] == running.pid
        and state["port"] == running.port
        and state["url"] == running.url
    )
    assert stat.S_IMODE((home / "serve.json").stat().st_mode) == 0o600  # it holds the token


def test_the_harness_runs_in_its_own_group_on_this_computer_with_the_patch_and_home(
    tmp_path: Path, home: Path, prepared: serve.Prepared
) -> None:
    patch = serve.write_patch(home, None, False, sys.executable)
    running = serve.start(prepared, patch, 0, home, box=None, read_only=False)
    pid, grandchild = pids(tmp_path)
    assert pid == running.pid and os.getsid(pid) == pid != os.getsid(0)  # a session of its own
    assert os.getpgid(grandchild) == pid  # its children are in that group
    lines = (tmp_path / "pids").read_text().splitlines()
    assert lines[1] == str(patch) and lines[2] == str(serve.dsh_home(home))


def test_the_command_line_binds_loopback_and_never_opens_a_browser_itself(
    tmp_path: Path, home: Path, prepared: serve.Prepared
) -> None:
    argv = serve.command_line(prepared, home / "caixa.patch.yml", 3500)
    assert argv[0] == str(FAKE)
    assert (
        argv[argv.index("--host") + 1] == "127.0.0.1" and argv[argv.index("--port") + 1] == "3500"
    )
    assert "--no-open" in argv and argv[argv.index("--profile") + 1] == "web"
    assert argv[argv.index("--patch") + 1] == str(home / "caixa.patch.yml")
    # the real dsh refuses `--patch` after the app's own options (found by running it)
    assert argv.index("--patch") < argv.index("--profile") < argv.index("--no-open")


def test_the_token_never_reaches_the_log_or_the_terminal(
    tmp_path: Path, home: Path, prepared: serve.Prepared, capsys: pytest.CaptureFixture[str]
) -> None:
    patch = serve.write_patch(home, None, False, sys.executable)
    running = serve.start(prepared, patch, 0, home, box=None, read_only=False)
    assert wait_for(
        lambda: (home / "logs" / "dsh.log").exists()
        and "harness is up" in (home / "logs" / "dsh.log").read_text()
    )
    log = (home / "logs" / "dsh.log").read_text()
    assert TOKEN not in log and "token=***" in log
    captured = capsys.readouterr()
    assert TOKEN not in captured.out + captured.err
    assert running.url.count(TOKEN) == 1  # the one place it lives besides the 0600 state file


def test_redaction() -> None:
    assert (
        serve.redact("open http://127.0.0.1:1/?token=abc-DEF_123 now")
        == "open http://127.0.0.1:1/?token=*** now"
    )
    assert serve.redact("nothing secret") == "nothing secret"


def test_a_harness_that_never_prints_its_link_is_stopped_and_explained(
    tmp_path: Path, home: Path, prepared: serve.Prepared
) -> None:
    prepared.env["FAKE_MODE"] = "silent"
    patch = serve.write_patch(home, None, False, sys.executable)
    with pytest.raises(ServeError, match="did not say where it is running") as stop:
        serve.start(prepared, patch, 0, home, box=None, read_only=False, link_timeout=1.5)
    assert TOKEN not in str(stop.value)
    pid, grandchild = pids(tmp_path)
    assert wait_for(lambda: not alive(pid) and not alive(grandchild))
    assert not (home / "serve.json").exists()


def test_a_harness_that_stops_at_once_is_explained_without_its_token(
    tmp_path: Path, home: Path, prepared: serve.Prepared
) -> None:
    prepared.env["FAKE_MODE"] = "early"
    patch = serve.write_patch(home, None, False, sys.executable)
    with pytest.raises(ServeError, match="stopped before it was ready") as stop:
        serve.start(prepared, patch, 0, home, box=None, read_only=False, link_timeout=10)
    assert "something is wrong" in str(stop.value) and TOKEN not in str(stop.value)
    assert not (home / "serve.json").exists()


def test_a_link_that_does_not_answer_is_not_reported_as_running(
    tmp_path: Path, home: Path, prepared: serve.Prepared
) -> None:
    prepared.env["FAKE_MODE"] = "noready"
    patch = serve.write_patch(home, None, False, sys.executable)
    with pytest.raises(ServeError, match="did not answer"):
        serve.start(
            prepared, patch, 0, home, box=None, read_only=False, link_timeout=10, ready_timeout=1.5
        )
    pid, grandchild = pids(tmp_path)
    assert wait_for(lambda: not alive(pid) and not alive(grandchild))


# --- Stopping -------------------------------------------------------------------------------


def test_stopping_ends_the_whole_group_and_forgets_the_state(
    tmp_path: Path, home: Path, prepared: serve.Prepared
) -> None:
    patch = serve.write_patch(home, None, False, sys.executable)
    running = serve.start(prepared, patch, 0, home, box=None, read_only=False)
    _, grandchild = pids(tmp_path)
    serve.stop(home)
    assert wait_for(lambda: not alive(running.pid) and not alive(grandchild))
    assert not (home / "serve.json").exists()


def test_stopping_when_nothing_runs_says_so(home: Path) -> None:
    assert serve.stop(home) is False


def test_a_stale_state_is_dropped(home: Path) -> None:
    home.mkdir(parents=True)
    (home / "serve.json").write_text(
        json.dumps({"pid": 2**22 + 7, "port": 1, "url": "http://127.0.0.1:1/?token=x"})
    )
    assert serve.read_state(home) is None
    assert not (home / "serve.json").exists()


# --- Reattaching ----------------------------------------------------------------------------


def test_a_running_harness_is_found_again(
    tmp_path: Path, home: Path, prepared: serve.Prepared
) -> None:
    patch = serve.write_patch(home, None, False, sys.executable)
    running = serve.start(prepared, patch, 0, home, box=None, read_only=False)
    found = serve.read_state(home)
    assert found is not None and found["pid"] == running.pid and found["url"] == running.url


def test_options_that_differ_from_the_running_ones_are_refused_with_the_way_out(
    tmp_path: Path, home: Path, prepared: serve.Prepared
) -> None:
    patch = serve.write_patch(home, "/boxes/A", False, sys.executable)
    serve.start(prepared, patch, 0, home, box="/boxes/A", read_only=False)
    serve.check_compatible(serve.read_state(home), box="/boxes/A", read_only=False)
    for box, read_only in (("/boxes/B", False), ("/boxes/A", True), (None, False)):
        with pytest.raises(ServeError, match="caixa serve --stop"):
            serve.check_compatible(serve.read_state(home), box=box, read_only=read_only)


# --- The real command, in a process of its own ---------------------------------------------


@pytest.fixture
def environment(tmp_path: Path, home: Path) -> dict[str, str]:
    node = tmp_path / "bin" / "node"
    node.parent.mkdir()
    node.write_text("#!/bin/sh\necho v24.9.0\n")
    node.chmod(0o755)
    plugin = tmp_path / "plugin"
    (plugin / "lib").mkdir(parents=True)
    (plugin / "package.json").write_text(json.dumps({"name": serve.PLUGIN_NAME}))
    (plugin / "lib" / "index.js").write_text("")
    (plugin / "lib" / "client.js").write_text("")
    env = {k: v for k, v in os.environ.items() if k not in ("CAIXA_BOX", "CAIXA_NODE")}
    env.update(CAIXA_HOME=str(home), CAIXA_NODE=str(node), CAIXA_DSH=str(FAKE),
               CAIXA_PLUGIN=str(plugin), FAKE_PIDFILE=str(tmp_path / "pids"))  # fmt: skip
    return env


def launch(environment: dict[str, str], *args: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "caixa", "serve", "--no-browser", *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment,
    )  # fmt: skip


def read_link(process: subprocess.Popen[str], seen: list[str] | None = None) -> str:
    """The sign-in link the launcher printed; every line read on the way goes into `seen`."""
    assert process.stdout is not None
    for _ in range(50):
        line = process.stdout.readline()
        if seen is not None:
            seen.append(line)
        found = re.search(r"http://127\.0\.0\.1:\d+/\?token=\S+", line)
        if found:
            return found.group(0)
    raise AssertionError("no link was printed")


def test_killing_the_launcher_leaves_the_harness_and_the_next_start_reattaches(
    tmp_path: Path, home: Path, environment: dict[str, str]
) -> None:
    first = launch(environment)
    link = read_link(first)
    harness, grandchild = pids(tmp_path)
    first.kill()  # not a clean stop: the launcher is gone, the harness is not
    first.communicate()
    assert alive(harness) and alive(grandchild)

    second = launch(environment)
    printed: list[str] = []
    assert (
        read_link(second, printed) == link
    )  # the same harness, found again; no second one started
    assert alive(harness)
    second.send_signal(signal.SIGINT)  # a clean stop ends the harness and everything under it
    out, err = second.communicate(timeout=30)
    assert second.returncode == 0 and "already running" in "".join(printed)
    assert wait_for(lambda: not alive(harness) and not alive(grandchild))
    assert not (home / "serve.json").exists()
    assert TOKEN not in err and TOKEN not in (home / "logs" / "dsh.log").read_text()


def test_a_second_start_with_other_options_says_how_to_change_them(
    tmp_path: Path, home: Path, environment: dict[str, str]
) -> None:
    first = launch(environment)
    read_link(first)
    second = launch(environment, "--read-only")
    out, err = second.communicate(timeout=30)
    assert second.returncode == 1 and "caixa serve --stop" in err
    stop = subprocess.run([sys.executable, "-m", "caixa", "serve", "--stop"], env=environment,
                          capture_output=True, text=True)  # fmt: skip
    assert stop.returncode == 0 and "Stopped" in stop.stdout
    first.communicate(timeout=30)


def test_stop_with_nothing_running_is_fine(environment: dict[str, str]) -> None:
    result = subprocess.run([sys.executable, "-m", "caixa", "serve", "--stop"], env=environment,
                            capture_output=True, text=True)  # fmt: skip
    assert result.returncode == 0 and "Nothing is running" in result.stdout


def test_the_checks_come_first_and_say_what_to_do(
    tmp_path: Path, environment: dict[str, str]
) -> None:
    old = tmp_path / "old-node"
    old.write_text("#!/bin/sh\necho v22.1.0\n")
    old.chmod(0o755)
    result = subprocess.run([sys.executable, "-m", "caixa", "serve", "--no-browser", "--node", str(old)],
                            env=environment, capture_output=True, text=True)  # fmt: skip
    assert result.returncode == 1 and "22.1.0" in result.stderr and "nodejs.org" in result.stderr
    bad_port = subprocess.run([sys.executable, "-m", "caixa", "serve", "--port", "3080"], env=environment,
                              capture_output=True, text=True)  # fmt: skip
    assert bad_port.returncode == 1 and "3080" in bad_port.stderr


def test_a_box_is_checked_and_handed_to_the_plugin(
    tmp_path: Path, environment: dict[str, str]
) -> None:
    refused = subprocess.run([sys.executable, "-m", "caixa", "serve", "--box", str(tmp_path / "nope")],
                             env=environment, capture_output=True, text=True)  # fmt: skip
    assert refused.returncode == 1 and "not a Caixa box" in refused.stderr
    from caixa.box import Box

    Box.create(tmp_path / "Box", name="Box")
    process = launch(environment, "--box", str(tmp_path / "Box"), "--read-only")
    read_link(process)
    patch = Path(environment["CAIXA_HOME"]) / "caixa.patch.yml"
    text = patch.read_text()
    assert str(tmp_path / "Box") in text and "readOnly: true" in text
    subprocess.run(
        [sys.executable, "-m", "caixa", "serve", "--stop"], env=environment, capture_output=True
    )
    process.communicate(timeout=30)
