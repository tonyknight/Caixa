"""Shared setup for Caixa's tests.

Caixa's tests use the synthetic fixture family whose builders live with Chattr (see
`tests/fixtures/README.md`). This conftest makes it importable and builds a real `chattr.sqlite`
from it for the adapter tests. Treat what it returns as read-only; copy before changing it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest

CHATTR_TESTS = Path(__file__).resolve().parents[1] / "tools" / "chattr" / "tests"
if str(CHATTR_TESTS) not in sys.path:
    sys.path.insert(0, str(CHATTR_TESTS))

from fixtures import FamilyExports, build_all, family  # noqa: E402  (needs the path above)


@pytest.fixture(autouse=True)
def _private_caixa_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No test reads or writes the real per-user Caixa folder (what Caixa remembers lives there),
    and a worker or `caixa` process a test starts inherits this one."""
    monkeypatch.setenv("CAIXA_HOME", str(tmp_path_factory.mktemp("caixa-home")))


@pytest.fixture(scope="session")
def fixture_family(tmp_path_factory: pytest.TempPathFactory) -> FamilyExports:
    return build_all(tmp_path_factory.mktemp("family"))


@dataclass
class ChattrArchive:
    root: Path  # the Chattr root
    database: Path  # chattr.sqlite
    owner: str


@pytest.fixture(scope="session")
def chattr_archive(
    tmp_path_factory: pytest.TempPathFactory, fixture_family: FamilyExports
) -> Iterator[ChattrArchive]:
    """A real Chattr archive of the fixture family (iMessage, WhatsApp, Messenger, mail, voice)."""
    from chattr import commands, preflight
    from chattr.config import Settings

    base = tmp_path_factory.mktemp("chattr-archive")
    (base / "home").mkdir()
    root = base / "Chattr"
    with pytest.MonkeyPatch.context() as patch:  # isolate HOME only while building
        patch.setenv("HOME", str(base / "home"))
        patch.delenv("CHATTR_ROOT", raising=False)
        assert preflight.run_preflight(str(root), interactive=False)
        config = root / "config.json"
        data = json.loads(config.read_text())
        owner = family.OWNER
        data["global"]["owner"] = {
            "name": owner.name,
            "identifiers": [*owner.phones, *owner.emails],
        }
        data["global"]["contacts"]["vcf_file_path"] = str(fixture_family.paths["contacts"])
        config.write_text(json.dumps(data))
        settings = Settings.load(root)
        paths = fixture_family.paths
        imessage = paths["imessage"]
        commands.convert_imessage(
            settings,
            db_path=imessage,
            attachment_root=imessage.parent / "Attachments",
            spam_mode="disabled",
            workers=1,
        )
        ios = paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt"
        commands.convert(settings, "whatsapp", ios)
        commands.convert(settings, "messenger", paths["messenger"])
        commands.convert(settings, "mail", paths["mbox"])
        commands.convert(settings, "googlevoice", paths["google_voice"])
    yield ChattrArchive(root, commands.central_database(settings), owner.name)
