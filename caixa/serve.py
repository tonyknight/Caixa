"""`caixa serve`: one command that starts the browser interface and opens it.

The interface is a plugin for DeepSeek Harness (`dsh web`), which needs Node.js 24.9 or newer. This
module checks Node, prepares Caixa's *own* harness (never the user's `~/.dsh`: a per-user folder
holding the pinned `dsh`, its profile and the Caixa plugin), writes the privacy patch, then starts
`dsh web` on this computer only, supervises it, and opens the browser.

Preparing (this file's first half) and launching (second half) are separate so each can be tested
without the other.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
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
