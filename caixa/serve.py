"""`caixa serve`: start Caixa's window on this computer and open it in the browser.

Caixa serves its own window (see `caixa.web`): one Python process holds the service layer and the
web server, so nothing else needs to be installed or started. The box that was open last time
opens again unless another is named.

What a running Caixa is (its process, port and sign-in link) is kept in `serve.json` in Caixa's
per-user folder, readable only by its owner, so that `caixa serve` run again opens the same window
and `caixa serve --stop` can end it from another terminal.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from caixa import revision
from caixa.service import Service, ServiceError
from caixa.state import State, caixa_home

__all__ = ["Options", "ServeError", "run", "stop", "read_state", "state_path", "caixa_home"]


class ServeError(Exception):
    """Something stops `caixa serve`; the message says what and how to fix it."""


def validate_port(port: int) -> int:
    """0 (any free port) or 1024 to 65535."""
    if port == 0 or 1024 <= port <= 65535:
        return port
    raise ServeError(f"Port {port} is not usable; choose 1024 to 65535, or 0 for any free port.")


# --- What is running --------------------------------------------------------------------------


def state_path(home: Path) -> Path:
    return home / "serve.json"


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # a process that has ended but not been collected is not alive
        return Path(f"/proc/{pid}/stat").read_text().split(")")[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def _answers(port: int, timeout: float = 3) -> bool:
    """Whether Caixa answers on that port (without signing in: it says who it is either way)."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/caixa/status", headers={"Host": f"127.0.0.1:{port}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except urllib.error.HTTPError as error:
        return error.headers.get("Server", "").startswith("Caixa")
    except OSError:
        return False


def _save_state(home: Path, state: dict[str, Any]) -> None:
    home.mkdir(parents=True, exist_ok=True)
    path = state_path(home)
    part = path.with_name(path.name + ".part")
    handle = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # it holds the link
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        json.dump(state, out)
    os.replace(part, path)


def read_state(home: Path, check: bool = True) -> Optional[dict[str, Any]]:
    """The Caixa a previous `caixa serve` left running; a stale record is removed."""
    path = state_path(home)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        pid, port = int(state["pid"]), int(state["port"])
        str(state["url"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if check and not (_alive(pid) and _answers(port)):
        path.unlink(missing_ok=True)
        return None
    return dict(state)


def check_compatible(state: Optional[dict[str, Any]], box: Optional[str], read_only: bool) -> None:
    """A running Caixa keeps its mode; asking for another, or for a box it was not started with,
    must not silently reuse it."""
    if state is None:
        return
    if (box is not None and state.get("box") != box) or bool(state.get("read_only")) != read_only:
        raise ServeError(
            "Caixa is already running with a different box or mode. Stop it first with "
            "`caixa serve --stop`, then start it again."
        )


def stop(home: Path, grace: float = 10) -> bool:
    """Stop the Caixa a previous `caixa serve` left running; False when there was none."""
    state = read_state(home, check=False)
    if state is None:
        return False
    pid = int(state["pid"])
    if pid != os.getpid() and _alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        end = time.time() + grace
        while _alive(pid) and time.time() < end:
            time.sleep(0.05)
    state_path(home).unlink(missing_ok=True)
    return True


# --- The command ------------------------------------------------------------------------------


@dataclass
class Options:
    box: Optional[str] = None
    read_only: bool = False
    port: int = 0
    no_browser: bool = False
    stop: bool = False


def _last_box(state: State, say: Callable[[str], None]) -> Optional[str]:
    """The box that was open last time, when it is still there (and say so); else None."""
    last = state.last_box()
    if last is None:
        return None
    name = next((b["name"] for b in state.recent_boxes() if b["path"] == last), "")
    say(f"Reopening your last box{f' ({name})' if name else ''}: {last}")
    return last


def _never() -> bool:
    return False


def run(options: Options, until: Callable[[], bool] = _never, out: Any = None) -> int:
    """Everything `caixa serve` does. `until` ends the wait early (for tests); Control-C (or
    `caixa serve --stop`) ends it too."""
    from caixa.web import CaixaServer

    def say(text: str) -> None:
        print(text, file=out or sys.stdout, flush=True)

    home = caixa_home()
    if options.stop:
        say("Stopped Caixa." if stop(home) else "Nothing is running to stop.")
        return 0
    validate_port(options.port)
    box = str(Path(options.box).expanduser().resolve()) if options.box else None
    running = read_state(home)
    check_compatible(running, box, options.read_only)
    if running is not None:
        say(f"Caixa is already running at http://127.0.0.1:{running['port']}/")
        if revision.changed_since(float(running.get("started", 0))):
            say(
                "Caixa's code has changed since it was started, and it is still running the "
                "old code. Stop it with `caixa serve --stop` and start it again."
            )
        _open(str(running["url"]), options.no_browser, say)
        return 0

    remembered = State(home)
    service = Service(read_only=options.read_only, state=remembered, batch_pages=True)
    chosen = box or _last_box(remembered, say)
    if chosen:
        try:
            service.box_open(chosen)
        except ServiceError as error:
            if box:
                raise ServeError(str(error)) from None
            say(f"Could not reopen {chosen}: {error}")
    try:
        server = CaixaServer(service, options.port)
    except OSError as error:
        service.close()
        raise ServeError(f"Caixa could not listen on port {options.port}: {error}") from None
    version = revision.commit()
    server.start()
    _save_state(
        home,
        {"pid": os.getpid(), "port": server.port, "url": server.link, "box": chosen,
         "read_only": options.read_only, "started": time.time()},
    )  # fmt: skip
    say(
        f"Caixa{f' (commit {version})' if version else ''} is running at "
        f"http://127.0.0.1:{server.port}/ (this computer only)."
    )
    _open(server.link, options.no_browser, say)
    say("Press Control-C to stop Caixa.")

    ended = threading.Event()
    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGTERM, lambda *_: ended.set())
    try:
        while not until() and not ended.is_set():
            ended.wait(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
        server.stop()
        service.close(cancel=True)
        state = read_state(home, check=False)
        if state is not None and int(state.get("pid", -1)) == os.getpid():
            state_path(home).unlink(missing_ok=True)
    say("Stopped Caixa.")
    return 0


def _open(link: str, no_browser: bool, say: Callable[[str], None]) -> None:
    if no_browser:
        say(f"Open this link in your web browser: {link}")
    elif not webbrowser.open(link):
        say(f"Open this link in your web browser: {link}")
