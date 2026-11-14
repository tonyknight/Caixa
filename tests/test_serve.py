"""`caixa serve`, part 1: the checks and the preparation before anything starts."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from caixa import serve
from caixa.serve import ServeError


def _fake_node(folder: Path, version: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    node = folder / "node"
    node.write_text(f"#!/bin/sh\necho v{version}\n")
    node.chmod(0o755)
    return node


# --- Node -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("v24.9.0\n", (24, 9, 0)),
        ("v24.22.2", (24, 22, 2)),
        ("v25.0.0-nightly", (25, 0, 0)),
        ("v22.1.0", (22, 1, 0)),
    ],
)
def test_node_versions_are_read(text: str, expected: tuple[int, int, int]) -> None:
    assert serve.parse_node_version(text) == expected


@pytest.mark.parametrize("text", ["", "node", "v", "24.9", "version 24"])
def test_something_that_is_not_a_node_version_is_none(text: str) -> None:
    assert serve.parse_node_version(text) is None


def test_a_new_enough_node_is_accepted(tmp_path: Path) -> None:
    node = _fake_node(tmp_path, "24.9.0")
    found = serve.find_node(str(node))
    assert found.version == (24, 9, 0) and found.path == node


def test_too_old_a_node_is_explained_with_what_was_found_and_how_to_fix_it(tmp_path: Path) -> None:
    node = _fake_node(tmp_path, "22.3.0")
    with pytest.raises(ServeError) as stop:
        serve.find_node(str(node))
    message = str(stop.value)
    assert "22.3.0" in message and "24.9" in message and str(node) in message
    assert "nodejs.org" in message


def test_a_missing_node_is_explained(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ServeError, match="Node.js 24.9 or newer, and Node was not found") as stop:
        serve.find_node(None)
    assert "nodejs.org" in str(stop.value)


def test_a_program_that_is_not_node_is_explained(tmp_path: Path) -> None:
    fake = tmp_path / "node"
    fake.write_text("#!/bin/sh\necho hello\n")
    fake.chmod(0o755)
    with pytest.raises(ServeError, match="did not report a version"):
        serve.find_node(str(fake))


def test_node_is_found_on_the_path_or_in_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    on_path = _fake_node(tmp_path / "bin", "24.10.0")
    monkeypatch.setenv("PATH", str(on_path.parent))
    monkeypatch.delenv("CAIXA_NODE", raising=False)
    assert serve.find_node(None).path == on_path
    chosen = _fake_node(tmp_path / "chosen", "25.1.0")
    monkeypatch.setenv("CAIXA_NODE", str(chosen))
    assert serve.find_node(None).path == chosen


# --- Where things live ----------------------------------------------------------------------


def test_the_home_is_per_user_and_never_the_users_own_dsh(tmp_path: Path) -> None:
    home = tmp_path / "me"
    assert serve.caixa_home({}, "linux", home) == home / ".local" / "share" / "caixa"
    assert (
        serve.caixa_home({"XDG_DATA_HOME": str(tmp_path / "xdg")}, "linux", home)
        == tmp_path / "xdg" / "caixa"
    )
    assert (
        serve.caixa_home({}, "darwin", home) == home / "Library" / "Application Support" / "Caixa"
    )
    assert (
        serve.caixa_home({"LOCALAPPDATA": str(tmp_path / "L")}, "win32", home)
        == tmp_path / "L" / "Caixa"
    )
    assert serve.caixa_home({"CAIXA_HOME": str(tmp_path / "x")}, "linux", home) == tmp_path / "x"
    for platform in ("linux", "darwin", "win32"):
        assert ".dsh" not in str(serve.caixa_home({}, platform, home))


def test_the_dsh_home_is_inside_caixas_home(tmp_path: Path) -> None:
    assert serve.dsh_home(tmp_path) == tmp_path / "dsh-home"


def test_the_plugin_is_the_harness_folder_of_a_checkout() -> None:
    plugin = serve.plugin_directory({})
    assert (plugin / "package.json").is_file()
    assert json.loads((plugin / "package.json").read_text())["name"] == serve.PLUGIN_NAME


def test_the_plugin_can_be_named_by_the_environment(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    assert serve.plugin_directory({"CAIXA_PLUGIN": str(tmp_path)}) == tmp_path
    with pytest.raises(ServeError, match="no Caixa plugin"):
        serve.plugin_directory({"CAIXA_PLUGIN": str(tmp_path / "missing")})


def test_an_unbuilt_plugin_says_how_to_build_it(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    with pytest.raises(ServeError, match="pnpm --dir harness install"):
        serve.require_built(tmp_path)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "index.js").write_text("")
    (tmp_path / "lib" / "client.js").write_text("")
    serve.require_built(tmp_path)


def test_the_pin_is_the_one_the_plugin_declares() -> None:
    package = json.loads((Path(__file__).parents[1] / "harness" / "package.json").read_text())
    assert (
        serve.DSH_VERSION
        == package["engines"]["dsh"]
        == package["devDependencies"]["@deepseek-ai/dsh"]
    )


# --- Ports ----------------------------------------------------------------------------------


@pytest.mark.parametrize("port", [0, 3082, 3500, 8765, 65535])
def test_good_ports(port: int) -> None:
    assert serve.validate_port(port) == port


@pytest.mark.parametrize("port", [3080, 3081, 80, 1023, -1, 65536])
def test_bad_ports_are_refused_with_the_reason(port: int) -> None:
    with pytest.raises(ServeError, match="port"):
        serve.validate_port(port)


# --- The privacy patch ----------------------------------------------------------------------


def _patch(**options: object) -> str:
    defaults: dict[str, object] = {"box": None, "read_only": False, "python": "/usr/bin/python3"}
    return serve.privacy_patch(**{**defaults, **options})  # type: ignore[arg-type]


def test_the_patch_turns_off_session_logs_and_telemetry() -> None:
    text = _patch()
    for row in ("session-log-deepseek", "session-telemetry-otel"):
        assert f"- id: {row}\n  disabled: true" in text
    assert "session-log-deepseek" in text and "dsh-otel-collector" not in text


def test_the_patch_removes_deepseeks_notice_sign_in_prompt_and_brand() -> None:
    text = _patch()
    for row in ("ui-settings-models", "ui-brand-official", "ui-plugin-manager", "ui-schedule"):
        assert f"- id: {row}\n  disabled: true" in text
    assert "ui-workspace" not in text.replace("# ", "")  # the harness will not load without it


def test_the_patch_says_the_window_is_caixas_own() -> None:
    assert "    shell: true" in _patch()


def test_the_patch_configures_the_plugin_with_this_python_the_box_and_read_only() -> None:
    text = _patch(box="/boxes/Our Box", read_only=True, python="/opt/py thon/bin/python")
    assert "- id: caixa" in text
    assert '"/opt/py thon/bin/python", "-m", "caixa"' in text
    assert '"/boxes/Our Box"' in text and "readOnly: true" in text
    plain = _patch()
    assert "box:" not in plain and "readOnly: false" in plain


def test_the_patch_names_a_local_model_placeholder() -> None:
    text = _patch()
    assert "- id: llm-pi-ai" in text and "openai-completions" in text
    assert "http://localhost:11434/v1" in text


def test_the_child_asks_before_acting_and_sends_no_telemetry(tmp_path: Path) -> None:
    node = serve.Node(tmp_path / "bin" / "node", (24, 9, 0))
    env = serve.child_env(node, tmp_path / "dsh-home", {"PATH": "/usr/bin", "HOME": "/me"})
    assert env["DSH_PERMISSION_MODE"] == "workspace-write"
    assert env["DSH_TELEMETRY_DISABLED"] == "1" and env["DSH_HOME"] == str(tmp_path / "dsh-home")
    assert env["PATH"] == f"{tmp_path / 'bin'}:/usr/bin" and env["HOME"] == "/me"


def test_quoting_makes_awkward_paths_safe() -> None:
    text = _patch(box='/boxes/a "quoted": name\n# not a comment')
    assert "\n# not a comment" not in text  # the newline stayed inside the quoted string
    assert '\\"quoted\\"' in text


def test_the_patch_is_written_where_dsh_is_told_to_read_it(tmp_path: Path) -> None:
    path = serve.write_patch(tmp_path, box=None, read_only=False, python="python3")
    assert path == tmp_path / "caixa.patch.yml" and path.read_text(encoding="utf-8").startswith("#")
    assert not stat.S_IMODE(path.stat().st_mode) & 0o022  # not writable by others


# --- Preparing the harness ------------------------------------------------------------------


class Recorder:
    """Stands in for `subprocess.run`: records what was asked and makes the files it would."""

    def __init__(self, dsh_home: Path | None = None) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []
        self.dsh_home = dsh_home

    def __call__(self, argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = dict(kwargs.get("env") or {})  # type: ignore[call-overload]
        self.calls.append((list(argv), env))
        if argv[0].endswith("npm"):
            prefix = Path(argv[argv.index("--prefix") + 1])
            (prefix / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)
            (prefix / "node_modules" / ".bin" / "dsh").write_text("#!/bin/sh\n")
        if "plugin" in argv:
            assert self.dsh_home is not None
            profile = self.dsh_home / "profiles" / "web"
            profile.mkdir(parents=True, exist_ok=True)
            (profile / "package.json").write_text(
                json.dumps(
                    {"dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", serve.PLUGIN_NAME]}}}
                )
            )
        return subprocess.CompletedProcess(argv, 0, "", "")


def _plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "plugin"
    (plugin / "lib").mkdir(parents=True, exist_ok=True)
    (plugin / "package.json").write_text(json.dumps({"name": serve.PLUGIN_NAME}))
    (plugin / "lib" / "index.js").write_text("")
    (plugin / "lib" / "client.js").write_text("")
    return plugin


def test_preparing_installs_the_pinned_dsh_once_and_adds_the_plugin_once(tmp_path: Path) -> None:
    home = tmp_path / "home"
    node = serve.Node(_fake_node(tmp_path / "n", "24.9.0"), (24, 9, 0))
    run = Recorder(serve.dsh_home(home))
    first = serve.prepare(home, node, _plugin(tmp_path), run=run)
    installs = [argv for argv, _ in run.calls if argv[0].endswith("npm")]
    assert len(installs) == 1 and installs[0][1] == "ci"  # from the shipped lockfile, not a range
    locked = json.loads((home / "dsh" / "package.json").read_text())
    assert locked["dependencies"]["@deepseek-ai/dsh"] == serve.DSH_VERSION
    adds = [(argv, env) for argv, env in run.calls if "plugin" in argv]
    assert len(adds) == 1
    argv, env = adds[0]
    assert argv[1:5] == ["plugin", "--profile", "web", "add"] and argv[5] == str(_plugin(tmp_path))
    assert env["DSH_HOME"] == str(serve.dsh_home(home)) and env["DSH_TELEMETRY_DISABLED"] == "1"
    assert (
        str(node.path.parent) == env["PATH"].split(":")[0]
    )  # the Node that was checked is the one used
    assert first.dsh == home / "dsh" / "node_modules" / ".bin" / "dsh"

    run.calls.clear()
    serve.prepare(home, node, _plugin(tmp_path), run=run)
    assert run.calls == []  # nothing to do the second time


def test_the_shipped_lockfile_pins_the_harness_and_its_prereleases() -> None:
    manifest = json.loads(serve._data_file("package.json"))
    lock = json.loads(serve._data_file("package-lock.json"))
    assert manifest["dependencies"] == {"@deepseek-ai/dsh": serve.DSH_VERSION}
    packages = lock["packages"]
    assert packages["node_modules/@deepseek-ai/dsh"]["version"] == serve.DSH_VERSION
    # the build the plugin was tested with: a newer cordis cannot save the harness's settings
    assert packages["node_modules/@deepseek-ai/cordis"]["version"] == "4.0.6-alpha.1"
    for name, version in manifest["overrides"].items():
        assert packages[f"node_modules/{name}"]["version"] == version
    assert all(
        entry["resolved"].startswith("https://registry.npmjs.org/")
        for entry in packages.values()
        if "resolved" in entry
    )


def test_an_install_made_without_the_lockfile_is_replaced(tmp_path: Path) -> None:
    home = tmp_path / "home"
    node = serve.Node(_fake_node(tmp_path / "n", "24.9.0"), (24, 9, 0))
    old = home / "dsh" / "node_modules" / ".bin"  # what `npm install dsh@version` left before
    old.mkdir(parents=True)
    (old / "dsh").write_text("#!/bin/sh\n")
    (home / "dsh" / "node_modules" / "stray").write_text("x")
    run = Recorder(serve.dsh_home(home))
    serve.prepare(home, node, _plugin(tmp_path), run=run)
    assert [argv[1] for argv, _ in run.calls if argv[0].endswith("npm")] == ["ci"]
    assert not (home / "dsh" / "node_modules" / "stray").exists()
    run.calls.clear()
    serve.prepare(home, node, _plugin(tmp_path), run=run)
    assert run.calls == []  # and then left alone


def test_a_dsh_given_by_the_environment_is_used_and_nothing_is_installed(tmp_path: Path) -> None:
    home = tmp_path / "home"
    given = tmp_path / "mine" / "dsh"
    given.parent.mkdir()
    given.write_text("#!/bin/sh\n")
    node = serve.Node(_fake_node(tmp_path / "n", "24.9.0"), (24, 9, 0))
    run = Recorder(serve.dsh_home(home))
    prepared = serve.prepare(home, node, _plugin(tmp_path), dsh=given, run=run)
    assert prepared.dsh == given
    assert not any(argv[0].endswith("npm") for argv, _ in run.calls)


def test_a_failed_install_says_what_failed_and_where_to_look(tmp_path: Path) -> None:
    def failing(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "", "network is down")

    node = serve.Node(_fake_node(tmp_path / "n", "24.9.0"), (24, 9, 0))
    with pytest.raises(ServeError, match="network is down") as stop:
        serve.prepare(tmp_path / "home", node, _plugin(tmp_path), run=failing)
    assert "first run" in str(stop.value)


def test_a_missing_pnpm_is_explained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    node = serve.Node(_fake_node(tmp_path / "n", "24.9.0"), (24, 9, 0))
    given = tmp_path / "dsh"
    given.write_text("#!/bin/sh\n")

    def no_pnpm(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, "", "spawn pnpm ENOENT")

    with pytest.raises(ServeError, match="pnpm") as stop:
        serve.prepare(home, node, _plugin(tmp_path), dsh=given, run=no_pnpm)
    assert "npm install -g pnpm" in str(stop.value)


# --- The interface is rebuilt when its source has changed ------------------------------------------


def _checkout(tmp_path: Path, built_before_source: bool) -> Path:
    """A plugin folder with source and a build; the build is older or newer than the source."""
    plugin = _plugin(tmp_path)
    (plugin / "src" / "client").mkdir(parents=True)
    source = plugin / "src" / "client" / "page.tsx"
    source.write_text("export {}")
    (plugin / "scripts").mkdir()
    (plugin / "scripts" / "build.mjs").write_text("")
    old, new = 1_700_000_000, 1_700_000_500
    for built in (plugin / "lib" / "index.js", plugin / "lib" / "client.js"):
        os.utime(built, (old, old) if built_before_source else (new, new))
    for file in (source, plugin / "scripts" / "build.mjs", plugin / "package.json"):
        os.utime(file, (new, new) if built_before_source else (old, old))
    return plugin


def test_a_build_older_than_its_source_is_stale(tmp_path: Path) -> None:
    assert serve.is_stale(_checkout(tmp_path, built_before_source=True))


def test_a_build_newer_than_its_source_is_current(tmp_path: Path) -> None:
    assert not serve.is_stale(_checkout(tmp_path, built_before_source=False))


def test_a_plugin_with_no_source_beside_it_is_taken_as_built(tmp_path: Path) -> None:
    assert not serve.is_stale(_plugin(tmp_path))  # an installed plugin: only lib/ is shipped


def test_a_stale_interface_is_rebuilt_before_starting_and_says_so(tmp_path: Path) -> None:
    plugin = _checkout(tmp_path, built_before_source=True)
    node = serve.Node(tmp_path / "bin" / "node", (24, 9, 0))
    (plugin / "node_modules").mkdir()
    ran: list[list[str]] = []
    said: list[str] = []

    def run(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        ran.append(command)
        assert options["cwd"] == str(plugin)
        for built in ("index.js", "client.js"):
            (plugin / "lib" / built).write_text("new")
        return subprocess.CompletedProcess(command, 0, "", "")

    assert serve.ensure_built(plugin, node, said.append, run=run) is True
    assert ran == [[str(node.path), "scripts/build.mjs"]]
    assert any("rebuilding" in line for line in said)
    assert not serve.is_stale(plugin)
    assert serve.ensure_built(plugin, node, said.append, run=run) is False and len(ran) == 1


def test_a_first_build_installs_what_the_build_needs(tmp_path: Path) -> None:
    plugin = _checkout(tmp_path, built_before_source=True)
    shutil.rmtree(plugin / "lib")
    node = serve.Node(tmp_path / "bin" / "node", (24, 9, 0))
    ran: list[str] = []

    def run(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        ran.append(Path(command[0]).name + " " + command[1])
        if command[1] == "scripts/build.mjs":
            (plugin / "lib").mkdir(exist_ok=True)
            for built in ("index.js", "client.js"):
                (plugin / "lib" / built).write_text("new")
        return subprocess.CompletedProcess(command, 0, "", "")

    serve.ensure_built(plugin, node, lambda line: None, run=run)
    assert ran == ["pnpm install", "node scripts/build.mjs"]


def test_a_build_that_fails_says_what_to_run(tmp_path: Path) -> None:
    plugin = _checkout(tmp_path, built_before_source=True)
    (plugin / "node_modules").mkdir()
    node = serve.Node(tmp_path / "bin" / "node", (24, 9, 0))

    def run(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "error: Could not resolve esbuild")

    with pytest.raises(ServeError) as stop:
        serve.ensure_built(plugin, node, lambda line: None, run=run)
    assert "pnpm --dir harness install" in str(stop.value) and "Could not resolve" in str(
        stop.value
    )
