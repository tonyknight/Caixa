"""`caixa serve`: one command that starts the browser interface and opens it.

The interface is a plugin for DeepSeek Harness (`dsh web`), which needs Node.js 24.9 or newer. This
module checks Node, prepares Caixa's *own* harness (never the user's `~/.dsh`: a per-user folder
holding the pinned `dsh`, its profile and the Caixa plugin), writes the privacy patch, then starts
`dsh web` on this computer only, supervises it, and opens the browser.

Preparing (this file's first half) and launching (second half) are separate so each can be tested
without the other.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

#: The one DeepSeek Harness version Caixa's plugin is built and tested against (the plugin's
#: `engines.dsh`). Harness plugin interfaces change between versions, so it is never a range.
DSH_VERSION = "0.2.2-alpha.2"
PLUGIN_NAME = "caixa-dsh-plugin"
MIN_NODE = (24, 9)
PROFILE = "web"
#: Ports DeepSeek Harness itself uses by default; Caixa never takes them.
RESERVED_PORTS = (3080, 3081)
LOCAL_MODEL_ENDPOINT = "http://localhost:11434/v1"

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class ServeError(Exception):
    """Something stops `caixa serve`; the message says what and how to fix it."""


# --- Node -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    path: Path
    version: tuple[int, int, int]


def parse_node_version(text: str) -> Optional[tuple[int, int, int]]:
    """`v24.9.0` → (24, 9, 0); None when the text is not a Node version."""
    found = re.match(r"^v(\d+)\.(\d+)\.(\d+)", text.strip())
    return (int(found[1]), int(found[2]), int(found[3])) if found else None


def find_node(explicit: Optional[str] = None, run: Runner = subprocess.run) -> Node:
    """Find a Node new enough for DeepSeek Harness: `explicit`, `$CAIXA_NODE`, then the path."""
    wanted = explicit or os.environ.get("CAIXA_NODE") or shutil.which("node")
    advice = (
        "Install it from https://nodejs.org/ (or with your package manager, for example "
        "`brew install node`), then run `caixa serve` again."
    )
    needs = f"Caixa's browser interface needs Node.js {MIN_NODE[0]}.{MIN_NODE[1]} or newer"
    if not wanted:
        raise ServeError(f"{needs}, and Node was not found. {advice}")
    try:
        reported = run([wanted, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise ServeError(f"{needs}, and {wanted} could not be run ({error}). {advice}") from None
    version = parse_node_version(reported.stdout)
    if version is None:
        raise ServeError(
            f"{wanted} did not report a version, so it does not look like Node.js. {advice}"
        )
    if version[:2] < MIN_NODE:
        raise ServeError(
            f"{needs}, but found Node.js {'.'.join(map(str, version))} at {wanted}. {advice}"
        )
    return Node(Path(wanted), version)


# --- Where things live ------------------------------------------------------------------------


def caixa_home(
    environ: Optional[Mapping[str, str]] = None,
    platform_name: Optional[str] = None,
    home: Optional[Path] = None,
) -> Path:
    """Caixa's per-user folder for the harness and its state (`$CAIXA_HOME` overrides)."""
    env = os.environ if environ is None else environ
    platform = platform_name or sys.platform
    user = home or Path.home()
    if env.get("CAIXA_HOME"):
        return Path(env["CAIXA_HOME"])
    if platform == "darwin":
        return user / "Library" / "Application Support" / "Caixa"
    if platform.startswith("win"):
        return Path(env.get("LOCALAPPDATA") or user / "AppData" / "Local") / "Caixa"
    return Path(env.get("XDG_DATA_HOME") or user / ".local" / "share") / "caixa"


def dsh_home(home: Path) -> Path:
    """The `DSH_HOME` Caixa gives its harness: separate from anyone's own."""
    return home / "dsh-home"


def plugin_directory(environ: Optional[Mapping[str, str]] = None) -> Path:
    """The Caixa plugin: `$CAIXA_PLUGIN`, else the `harness/` folder of a checkout."""
    env = os.environ if environ is None else environ
    folder = (
        Path(env["CAIXA_PLUGIN"])
        if env.get("CAIXA_PLUGIN")
        else Path(__file__).resolve().parents[1] / "harness"
    )
    if not (folder / "package.json").is_file():
        raise ServeError(
            f"There is no Caixa plugin at {folder}. Run this from a Caixa checkout, or set "
            "CAIXA_PLUGIN to the folder holding the built plugin."
        )
    return folder


def require_built(plugin: Path) -> None:
    missing = [name for name in ("index.js", "client.js") if not (plugin / "lib" / name).is_file()]
    if missing:
        raise ServeError(
            f"The Caixa plugin in {plugin} is not built yet (no lib/{missing[0]}). Build it with "
            "`pnpm --dir harness install` and `pnpm --dir harness build`."
        )


def validate_port(port: int) -> int:
    """0 (any free port) or 3082 and up; never DeepSeek Harness's own 3080 and 3081."""
    if port == 0:
        return 0
    if port in RESERVED_PORTS:
        raise ServeError(
            f"Port {port} is DeepSeek Harness's own; choose 3082 or higher, or 0 for any free port."
        )
    if not 3082 <= port <= 65535:
        raise ServeError(
            f"Port {port} is not usable; choose 3082 to 65535, or 0 for any free port."
        )
    return port


# --- The privacy patch ------------------------------------------------------------------------


def _quote(value: str) -> str:
    """A YAML double-quoted scalar (JSON strings are valid YAML, escapes included)."""
    return json.dumps(value, ensure_ascii=False)


def privacy_patch(
    box: Optional[str],
    read_only: bool,
    python: str,
    endpoint: str = LOCAL_MODEL_ENDPOINT,
) -> str:
    """The configuration layer Caixa adds to its harness.

    Session logs and telemetry are switched off, a local OpenAI-compatible model is offered as a
    placeholder (nothing is sent until someone chooses it and it points at their own computer), and
    the Caixa plugin is told which box to open, whether it is read-only, and which Python runs the
    worker.
    """
    command = ", ".join(_quote(part) for part in (python, "-m", "caixa"))
    lines = [
        "# Written by `caixa serve`; edits are overwritten on the next start.",
        "# Caixa's harness never sends session logs or telemetry anywhere.",
        "- id: session-log-deepseek",
        "  disabled: true",
        "- id: session-telemetry-otel",
        "  disabled: true",
        "- id: llm-pi-ai",
        "  config:",
        "    providers:",
        "      local:",
        "        api: openai-completions",
        f"        baseURL: {_quote(endpoint)}",
        "        apiKeyEnv: CAIXA_LOCAL_MODEL_KEY",
        "        models:",
        "          - id: local-model",
        "- id: caixa",
        "  config:",
        f"    command: [{command}]",
    ]
    if box:
        lines.append(f"    box: {_quote(box)}")
    lines.append(f"    readOnly: {'true' if read_only else 'false'}")
    return "\n".join(lines) + "\n"


def write_patch(home: Path, box: Optional[str], read_only: bool, python: str) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    path = home / "caixa.patch.yml"
    path.write_text(privacy_patch(box, read_only, python), encoding="utf-8")
    path.chmod(0o600)
    return path


# --- Preparing the harness --------------------------------------------------------------------


def child_env(node: Node, dsh: Path, base: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """The environment for every harness process: this Node first on the path, Caixa's own home,
    telemetry off, ask-before-acting permissions."""
    env = dict(os.environ if base is None else base)
    env["PATH"] = str(node.path.parent) + os.pathsep + env.get("PATH", "")
    env["DSH_HOME"] = str(dsh)
    env["DSH_TELEMETRY_DISABLED"] = "1"
    env["DSH_PERMISSION_MODE"] = "workspace-write"
    return env


@dataclass(frozen=True)
class Prepared:
    dsh: Path  # the `dsh` program
    dsh_home: Path
    env: dict[str, str]


def _tail(text: str, lines: int = 6) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def prepare(
    home: Path,
    node: Node,
    plugin: Path,
    dsh: Optional[Path] = None,
    run: Runner = subprocess.run,
) -> Prepared:
    """Make sure the pinned `dsh` is installed and its `web` profile carries the Caixa plugin.

    Both steps happen once; later starts find them done. Installing `dsh` needs the network (the
    first run only).
    """
    home.mkdir(parents=True, exist_ok=True)
    harness_home = dsh_home(home)
    env = child_env(node, harness_home)
    program = dsh or home / "dsh" / "node_modules" / ".bin" / "dsh"
    if not program.exists():
        npm = node.path.parent / "npm"
        install = run(
            [str(npm) if npm.exists() else "npm", "install", "--prefix", str(home / "dsh"),
             "--no-audit", "--no-fund", f"@deepseek-ai/dsh@{DSH_VERSION}"],
            capture_output=True, text=True, env=env, timeout=900,
        )  # fmt: skip
        if install.returncode != 0 or not program.exists():
            raise ServeError(
                f"Could not install DeepSeek Harness {DSH_VERSION}. Installing it needs the "
                f"network, on first run only:\n{_tail(install.stderr or install.stdout)}"
            )
    if not _plugin_added(harness_home):
        added = run(
            [str(program), "plugin", "--profile", PROFILE, "add", str(plugin)],
            capture_output=True, text=True, env=env, timeout=900,
        )  # fmt: skip
        if added.returncode != 0 or not _plugin_added(harness_home):
            output = (added.stderr or "") + (added.stdout or "")
            if "pnpm" in output:
                raise ServeError(
                    "DeepSeek Harness needs pnpm to add plugins. Install it with "
                    "`npm install -g pnpm` (or `corepack enable`), then run `caixa serve` again."
                )
            raise ServeError(
                f"Could not add the Caixa plugin to DeepSeek Harness:\n{_tail(output)}"
            )
    return Prepared(program, harness_home, env)


def _plugin_added(harness_home: Path) -> bool:
    manifest = harness_home / "profiles" / PROFILE / "package.json"
    try:
        bundles: Any = json.loads(manifest.read_text(encoding="utf-8"))["dsh"]["profile"]["bundles"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return PLUGIN_NAME in bundles


# --- Launching --------------------------------------------------------------------------------

LINK = re.compile(r"http://127\.0\.0\.1:(\d+)/\?token=[\w\-]+")
_TOKEN = re.compile(r"(token=)[\w\-%.]+")


def redact(text: str) -> str:
    """Hide the sign-in token wherever a line carrying it would be shown or kept."""
    return _TOKEN.sub(r"\1***", text)


def state_path(home: Path) -> Path:
    return home / "serve.json"


def command_line(prepared: Prepared, patch: Path, port: int) -> list[str]:
    """`dsh web` on this computer only, without opening a browser (Caixa does that), with the patch.

    `--patch` is a launcher option and must come before the profile and the app's own options.
    """
    return [
        str(prepared.dsh), "--patch", str(patch), "--profile", PROFILE, "--no-open",
        "--host", "127.0.0.1", "--port", str(port),
    ]  # fmt: skip


@dataclass
class Running:
    pid: int
    port: int
    url: str  # carries the token: shown to the browser, never logged
    box: Optional[str]
    read_only: bool
    process: Optional["subprocess.Popen[str]"] = None  # None when found again rather than started


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # a process that has ended but not been collected is not alive
        return Path(f"/proc/{pid}/stat").read_text().split(")")[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def _answers(url: str, timeout: float = 3) -> bool:
    """Whether the sign-in link works: DeepSeek Harness sets its cookie and redirects, so follow it
    with a cookie jar and expect the page."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        with opener.open(url, timeout=timeout) as reply:
            return bool(reply.status == 200)
    except (OSError, urllib.error.URLError):
        return False


def stop_group(
    pid: int, grace: float = 10, process: Optional["subprocess.Popen[str]"] = None
) -> None:
    """End a process and everything it started: ask politely, then make sure.

    `pid` leads its own group (it was started in a session of its own). The group gets SIGTERM and
    `grace` seconds for its leader to finish; whatever is left in the group is then killed, so no
    helper the harness started outlives it. `process` lets the caller's own child be collected.
    """

    def leader_gone() -> bool:
        return process.poll() is not None if process is not None else not _alive(pid)

    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    end = time.time() + grace
    while not leader_gone() and time.time() < end:
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    end = time.time() + 5
    while not leader_gone() and time.time() < end:
        time.sleep(0.05)


def _save_state(home: Path, running: Running) -> None:
    home.mkdir(parents=True, exist_ok=True)
    path = state_path(home)
    path.write_text(
        json.dumps(
            {"pid": running.pid, "port": running.port, "url": running.url, "box": running.box,
             "read_only": running.read_only, "started": time.time()}  # fmt: skip
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)  # it holds the sign-in link


def read_state(home: Path, check: bool = True) -> Optional[dict[str, Any]]:
    """The harness a previous `caixa serve` left running; stale records are removed."""
    path = state_path(home)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        pid, url = int(state["pid"]), str(state["url"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if check and not (_alive(pid) and _answers(url)):
        path.unlink(missing_ok=True)
        return None
    return dict(state)


def check_compatible(state: Optional[dict[str, Any]], box: Optional[str], read_only: bool) -> None:
    """A running harness keeps its box and mode; asking for others must not silently reuse it."""
    if state is None:
        return
    if state.get("box") != box or bool(state.get("read_only")) != read_only:
        raise ServeError(
            "Caixa is already running with a different box or mode. Stop it first with "
            "`caixa serve --stop`, then start it again."
        )


def start(
    prepared: Prepared,
    patch: Path,
    port: int,
    home: Path,
    box: Optional[str],
    read_only: bool,
    link_timeout: float = 90,
    ready_timeout: float = 30,
) -> Running:
    """Start `dsh web` in a group of its own and return once it answers at its link.

    The link is read from the harness's standard output; its token is never printed or logged (the
    log keeps `token=***`), and lives only in the 0600 state file and the returned object.
    """
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log = open(logs / "dsh.log", "a", encoding="utf-8", buffering=1)
    process = subprocess.Popen(
        command_line(prepared, patch, port), env=prepared.env, text=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )  # fmt: skip
    found: dict[str, str] = {}
    announced = threading.Event()
    tail: list[str] = []

    def pump(stream: Any, watch: bool) -> None:
        for line in stream:
            clean = redact(line.rstrip("\n"))
            log.write(clean + "\n")
            tail.append(clean)
            del tail[:-8]
            match = LINK.search(line) if watch else None
            if match and "url" not in found:
                found["url"], found["port"] = match.group(0), match.group(1)
                announced.set()

    for stream, watch in ((process.stdout, True), (process.stderr, False)):
        threading.Thread(target=pump, args=(stream, watch), daemon=True).start()

    def fail(message: str) -> ServeError:
        stop_group(process.pid, grace=2, process=process)
        state_path(home).unlink(missing_ok=True)
        return ServeError(message)

    deadline = time.time() + link_timeout
    while not announced.is_set():
        if process.poll() is not None:
            time.sleep(0.3)  # let the last lines of its output arrive
            raise fail(
                f"DeepSeek Harness stopped before it was ready (exit {process.returncode}):\n"
                + "\n".join(tail[-6:])
            )
        if time.time() > deadline:
            raise fail(
                f"DeepSeek Harness did not say where it is running within {link_timeout:g} seconds. "
                f"Its log is {logs / 'dsh.log'}."
            )
        announced.wait(0.1)
    url, chosen = found["url"], int(found["port"])
    ready = time.time() + ready_timeout
    while not _answers(url):
        if process.poll() is not None or time.time() > ready:
            raise fail(
                f"DeepSeek Harness printed its address but did not answer there within "
                f"{ready_timeout:g} seconds. Its log is {logs / 'dsh.log'}."
            )
        time.sleep(0.2)
    running = Running(process.pid, chosen, url, box, read_only, process)
    _save_state(home, running)
    return running


def stop(home: Path) -> bool:
    """Stop the harness a previous `caixa serve` left running; False when there was none."""
    state = read_state(home, check=False)
    if state is None:
        return False
    stop_group(int(state["pid"]))
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
    node: Optional[str] = None


def _never() -> bool:
    return False


def run(options: Options, until: Callable[[], bool] = _never, out: Any = None) -> int:
    """Everything `caixa serve` does. `until` ends the wait early (for tests); Control-C ends it too."""

    def say(text: str) -> None:
        print(text, file=out or sys.stdout, flush=True)

    if sys.platform.startswith("win"):
        raise ServeError("`caixa serve` does not support Windows yet.")
    home = caixa_home()
    if options.stop:
        say("Stopped Caixa." if stop(home) else "Nothing is running to stop.")
        return 0
    validate_port(options.port)
    box = str(Path(options.box).expanduser().resolve()) if options.box else None
    state = read_state(home)
    check_compatible(state, box, options.read_only)
    if state is not None:
        running = Running(
            int(state["pid"]), int(state["port"]), str(state["url"]), box, options.read_only
        )
        say(f"Caixa is already running at http://127.0.0.1:{running.port}/")
    else:
        node = find_node(options.node)
        plugin = plugin_directory()
        require_built(plugin)
        given = os.environ.get("CAIXA_DSH")
        prepared = prepare(home, node, plugin, Path(given) if given else None)
        patch = write_patch(home, box, options.read_only, sys.executable)
        say("Starting Caixa…")
        running = start(prepared, patch, options.port, home, box, options.read_only)
        say(f"Caixa is running at http://127.0.0.1:{running.port}/ (this computer only).")
    if options.no_browser:
        say(f"Open this link in your web browser: {running.url}")
    else:
        webbrowser.open(running.url)
    say("Press Control-C to stop Caixa.")
    try:
        while not until():
            process = running.process
            gone = process.poll() is not None if process else not _alive(running.pid)
            if gone:
                state_path(home).unlink(missing_ok=True)
                raise ServeError(
                    "DeepSeek Harness stopped. Its log is " + str(home / "logs" / "dsh.log")
                )
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    stop_group(running.pid, process=running.process)
    state_path(home).unlink(missing_ok=True)
    say("Stopped Caixa.")
    return 0
