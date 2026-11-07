"""A report a person can paste when something does not work.

It answers what is installed, what is set up, and what happened lately, and, for a source that would
not import, what Caixa sees in it. It never holds a name, a number or message text: file names inside
a source are shown as shapes (letters as x, digits as 9) and the home folder's name is hidden.
Making it changes nothing in the box.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from caixa import __version__, serve, settings
from caixa.collectors.inputs import InputError
from caixa.collectors.options import validate
from caixa.state import caixa_home

if TYPE_CHECKING:
    from caixa.service import Service

#: Programs Caixa can use, and what each one is for.
PROGRAMS = (
    ("node", "the browser interface (needs 24.9 or newer)"),
    ("ffmpeg", "voicemail transcription"),
    ("whisper-cli", "voicemail transcription"),
    ("exiftool", "photo and video dates (optional)"),
)


def _run(argv: list[str]) -> str:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (
        (done.stdout or done.stderr).strip().splitlines()[0] if (done.stdout or done.stderr) else ""
    )


def _size(count: int) -> str:
    return f"{count / 1024:.1f} KB" if count < 1024 * 1024 else f"{count / 1024 / 1024:.1f} MB"


def _programs() -> list[str]:
    lines = []
    for name, purpose in PROGRAMS:
        found = shutil.which(name)
        if not found:
            lines.append(f"{name}: not found (used for {purpose})")
            continue
        version = _run([found, "--version"] if name != "ffmpeg" else [found, "-version"])
        lines.append(f"{name}: {found}" + (f" ({version[:60]})" if version else ""))
    return lines


def _package_version(package: Path) -> str:
    try:
        import json

        return str(json.loads((package / "package.json").read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError):
        return "not installed"


def _interface() -> list[str]:
    home = caixa_home()
    harness = home / "dsh"
    lines = [f"Caixa's folder: {home}"]
    modules = harness / "node_modules" / "@deepseek-ai"
    lines.append(f"harness: {_package_version(modules / 'dsh')} (wanted {serve.DSH_VERSION})")
    lines.append(f"harness cordis: {_package_version(modules / 'cordis')}")
    try:
        current = serve._install_is_current(harness)
    except OSError:
        current = False
    lines.append(f"harness installed from Caixa's lockfile: {'yes' if current else 'no'}")
    lines.append(f"remembered state: {'yes' if (home / 'state.json').is_file() else 'none yet'}")
    return lines


def _box(service: "Service") -> list[str]:
    box = service.box
    if box is None:
        return ["no box is open"]
    status = box.status(read_only=service.read_only)
    lines = [
        f"{status['name']} at {box.root}",
        f"{status['items']} items, {status['people']} people",
        f"read-only: {'yes' if service.read_only else 'no'}",
    ]
    values = settings.load(box)
    model = str(values.get("speech.model") or "")
    if not model:
        lines.append("speech model: not set")
    else:
        path = Path(model).expanduser()
        lines.append(
            f"speech model: set, file found ({_size(path.stat().st_size)})"
            if path.is_file()
            else "speech model: set, but there is no file at that path"
        )
    lines.append(f"speech language: {values.get('speech.language') or '(detect)'}")
    lines.append(
        f"translation: {'on' if values.get('translation.enabled') else 'off'}"
        + (", endpoint set" if values.get("translation.endpoint") else "")
    )
    return lines


def _jobs(service: "Service") -> list[str]:
    if service.box is None or service.jobs is None:
        return []
    lines = []
    for job in service.jobs.list(limit=5):
        error = (job.get("error") or "").splitlines()
        line = f"#{job['id']} {job['collector'] or job['kind']} {job['status']}"
        if job["status"] not in ("done", "queued"):
            line += f" at {job['stage'] or '?'}"
        lines.append(line)
        lines.extend(f"    {text}" for text in error[:12])
    return lines


def _source(service: "Service", collector: str, source: str) -> list[str]:
    try:
        found = service.registry.get(collector)
    except KeyError:
        return [f"unknown collector '{collector}'"]
    lines = [f"collector: {collector} ({found.info.name})", f"source: {source}"]
    try:
        options = validate(found.info.options_schema, {})
        preview = found.preview(Path(source).expanduser(), options, service.box)
    except InputError as error:
        lines.append("Cannot be imported:")
        lines.extend(f"    {text}" for text in str(error).splitlines())
        return lines
    except Exception as error:  # the report must always be made
        lines.append(f"Cannot be imported: {type(error).__name__}: {error}")
        return lines
    lines.append(f"Would import: {preview.items} items in {preview.conversations} conversations")
    if preview.first:
        lines.append(f"from {preview.first} to {preview.last}")
    if preview.unresolved:
        lines.append(f"{len(preview.unresolved)} names or numbers would need linking to people")
    lines.extend(preview.warnings)
    return lines


def report(
    service: "Service", collector: Optional[str] = None, source: Optional[str] = None
) -> str:
    """The report as text. With a `collector` and `source`, it also checks that source."""
    sections: list[tuple[str, list[str]]] = [
        (
            "Caixa",
            [
                f"caixa {__version__}",
                f"python {platform.python_version()} at {sys.executable}",
                f"{platform.system()} {platform.release()} ({platform.machine()})",
            ],
        ),
        ("Programs", _programs()),
        ("Interface", _interface()),
        ("Box", _box(service)),
    ]
    recent = _jobs(service)
    if recent:
        sections.append(("Recent imports", recent))
    if collector and source:
        sections.append(("This source", _source(service, collector, source)))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = f"Caixa diagnostic report ({stamp})\n"
    for title, lines in sections:
        text += f"\n== {title} ==\n" + "\n".join(lines) + "\n"
    home = str(Path.home())
    return text.replace(home, "~") if home not in ("", "/") else text
