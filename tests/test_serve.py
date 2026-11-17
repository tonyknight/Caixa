"""`caixa serve`: Caixa's own window, started in this process, found again, and stopped."""

from __future__ import annotations

import io
import json
import os
import stat
import threading
import time
import urllib.request
from pathlib import Path

import pytest
from fixtures import family

from caixa import serve
from caixa.serve import ServeError
from caixa.service import Service


def test_the_home_is_per_user(tmp_path: Path) -> None:
    home = tmp_path / "me"
    assert serve.caixa_home({}, "linux", home) == home / ".local" / "share" / "caixa"
    assert (
        serve.caixa_home({}, "darwin", home) == home / "Library" / "Application Support" / "Caixa"
    )
    assert serve.caixa_home({"CAIXA_HOME": str(tmp_path / "x")}, "linux", home) == tmp_path / "x"


@pytest.mark.parametrize("port", [0, 1024, 3080, 8000, 65535])
def test_good_ports(port: int) -> None:
    assert serve.validate_port(port) == port


@pytest.mark.parametrize("port", [1, 80, 1023, 65536])
def test_bad_ports_are_refused_with_the_reason(port: int) -> None:
    with pytest.raises(ServeError, match="1024 to 65535"):
        serve.validate_port(port)


def test_nothing_running_is_nothing_to_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAIXA_HOME", str(tmp_path / "home"))
    out = io.StringIO()
    assert serve.run(serve.Options(stop=True), out=out) == 0
    assert "Nothing is running to stop." in out.getvalue()


def test_a_stale_record_is_dropped(tmp_path: Path) -> None:
    serve._save_state(tmp_path, {"pid": 999_999_9, "port": 1, "url": "x", "started": 0})
    assert serve.read_state(tmp_path) is None
    assert not serve.state_path(tmp_path).exists()


def test_it_serves_the_box_says_where_and_stops_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("CAIXA_HOME", str(home))
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Served box", owner=family.OWNER.name)
    made.close()
    out = io.StringIO()
    finished = threading.Event()
    result: dict[str, int] = {}

    def serving() -> None:
        options = serve.Options(box=str(tmp_path / "Box"), no_browser=True)
        result["code"] = serve.run(options, until=finished.is_set, out=out)

    thread = threading.Thread(target=serving)
    thread.start()
    try:
        for _ in range(100):
            if serve.state_path(home).exists():
                break
            time.sleep(0.05)
        state = json.loads(serve.state_path(home).read_text(encoding="utf-8"))
        assert stat.S_IMODE(serve.state_path(home).stat().st_mode) == 0o600
        assert state["pid"] == os.getpid() and state["box"] == str((tmp_path / "Box").resolve())
        link = state["url"]
        assert f"Open this link in your web browser: {link}" in out.getvalue()
        assert "this computer only" in out.getvalue()
        assert "DeepSeek" not in out.getvalue() and "Node" not in out.getvalue()
        # the link signs in and the window answers, with the box open
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        with opener.open(link, timeout=10) as page:
            assert b'<div id="caixa">' in page.read()
        request = urllib.request.Request(
            f"http://127.0.0.1:{state['port']}/api/caixa/rpc",
            data=json.dumps({"method": "box.status"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with opener.open(request, timeout=10) as reply:
            assert json.loads(reply.read())["result"]["name"] == "Served box"
        # run again while it runs: it says so and opens the same window
        again = io.StringIO()
        assert serve.run(serve.Options(no_browser=True), out=again) == 0
        assert "already running" in again.getvalue() and link in again.getvalue()
        with pytest.raises(ServeError, match="different box or mode"):
            serve.run(serve.Options(read_only=True, no_browser=True), out=io.StringIO())
    finally:
        finished.set()
        thread.join(30)
    assert result["code"] == 0
    assert "Stopped Caixa." in out.getvalue()
    assert not serve.state_path(home).exists()
