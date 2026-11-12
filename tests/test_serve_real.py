"""`caixa serve` against the real, pinned DeepSeek Harness and the real Caixa plugin.

Skipped unless this computer can run it: Node 24.9+ (found through $CAIXA_NODE, or on the path),
`pnpm`, the harness installed and built (`pnpm --dir harness install`), and no `caixa serve` already
using the same CAIXA_HOME (each test has its own).
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa import serve
from caixa.box import Box

HARNESS = Path(__file__).resolve().parents[1] / "harness"
DSH = HARNESS / "node_modules" / ".bin" / "dsh"


def _node() -> str | None:
    try:
        return str(serve.find_node(None).path)
    except serve.ServeError:
        return None


NODE = _node()
READY = (
    bool(NODE)
    and bool(shutil.which("pnpm"))
    and DSH.exists()
    and (HARNESS / "lib" / "client.js").exists()
)
pytestmark = pytest.mark.skipif(not READY, reason="needs Node 24.9+, pnpm and a built harness")


@pytest.fixture(scope="module")
def running(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    folder = tmp_path_factory.mktemp("real-serve")
    box = Box.create(folder / "Box", name="Real box")
    env = {k: v for k, v in os.environ.items() if k != "CAIXA_BOX"}
    env.update(CAIXA_HOME=str(folder / "home"), CAIXA_NODE=str(NODE), CAIXA_DSH=str(DSH))
    process = subprocess.Popen(
        [sys.executable, "-m", "caixa", "serve", "--no-browser", "--box", str(box.root), "--read-only"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )  # fmt: skip
    assert process.stdout is not None
    link, out = "", ""
    for _ in range(100):
        line = process.stdout.readline()
        out += line
        found = re.search(r"http://127\.0\.0\.1:\d+/\?token=\S+", line)
        if found:
            link = found.group(0)
            break
    assert link, f"no link: {out} {process.stderr.read() if process.stderr else ''}"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.open(link, timeout=30).read()  # signs in: DSH sets its cookie
    state = json.loads((folder / "home" / "serve.json").read_text())
    yield {"folder": folder, "box": box, "env": env, "link": link, "opener": opener, "out": out,
           "process": process, "port": int(re.search(r":(\d+)/", link).group(1)), "state": state}  # fmt: skip
    process.terminate()
    try:
        process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def _call(running: dict[str, Any], method: str, **params: Any) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{running['port']}/api/caixa/rpc",
        data=json.dumps({"method": method, "params": params}).encode(),
        headers={"content-type": "application/json"},
    )
    return json.loads(running["opener"].open(request, timeout=30).read())  # type: ignore[no-any-return]


def test_the_harness_comes_up_with_the_plugin_and_serves_only_this_computer(
    running: dict[str, Any],
) -> None:
    assert running["link"].startswith("http://127.0.0.1:")
    status = json.loads(
        running["opener"]
        .open(f"http://127.0.0.1:{running['port']}/api/caixa/status", timeout=30)
        .read()
    )
    assert status == {"worker": "running", "shell": True}
    request = urllib.request.Request(f"http://127.0.0.1:{running['port']}/api/caixa/status")
    with pytest.raises(urllib.error.HTTPError) as stop:  # no sign-in cookie
        urllib.request.urlopen(request, timeout=30)
    assert stop.value.code == 401


def test_the_box_and_read_only_reach_the_worker(running: dict[str, Any]) -> None:
    assert _call(running, "box.status")["result"]["name"] == "Real box"
    refused = _call(running, "box.create", path=str(running["folder"] / "Other"))
    assert refused["ok"] is False and refused["error"]["kind"] == "read_only"
    assert not (running["folder"] / "Other").exists()


def test_the_privacy_patch_took_effect(running: dict[str, Any]) -> None:
    dump = subprocess.run(
        [str(DSH), "--patch", str(running["folder"] / "home" / "caixa.patch.yml"), "--profile", "web", "--dump-config"],
        env=serve.child_env(serve.find_node(None), serve.dsh_home(running["folder"] / "home")),
        capture_output=True, text=True, timeout=120,
    )  # fmt: skip
    assert dump.returncode == 0, dump.stderr
    for row in ("session-log-deepseek", "session-telemetry-otel"):
        found = re.search(
            rf"- id: {row}\n(?:  .*\n|    .*\n|      .*\n)*?  disabled: true", dump.stdout
        )
        assert found, row
    assert "no row" not in dump.stderr.lower() and "does not exist" not in dump.stderr.lower()


def test_the_token_is_nowhere_it_should_not_be(running: dict[str, Any]) -> None:
    token = running["link"].split("token=")[1]
    log = (running["folder"] / "home" / "logs" / "dsh.log").read_text()
    assert token not in log and token not in running["out"].replace(running["link"], "")
    assert oct((running["folder"] / "home" / "serve.json").stat().st_mode & 0o777) == "0o600"
    patch = (running["folder"] / "home" / "caixa.patch.yml").read_text()
    assert token not in patch


def test_the_harness_runs_in_its_own_home_not_the_users(running: dict[str, Any]) -> None:
    assert (running["folder"] / "home" / "dsh-home" / "profiles" / "web" / "package.json").is_file()
    assert not (
        Path.home() / ".dsh" / "profiles" / "web" / "node_modules" / "caixa-dsh-plugin"
    ).exists()


def test_stopping_ends_everything(running: dict[str, Any]) -> None:
    pid = running["state"]["pid"]
    running["process"].send_signal(2)  # Control-C
    running["process"].wait(timeout=60)
    end = time.time() + 20
    while time.time() < end:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.killpg(pid, 0)
    assert not (running["folder"] / "home" / "serve.json").exists()
