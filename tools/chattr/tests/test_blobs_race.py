"""Two readers storing the same file at once (a mail import's worker processes, the same
signature logo in mails of two batches): both succeed, and the file is whole.

The bug: both wrote `<hash>.part`; the first moved it into place, the second's move found nothing
(FileNotFoundError), and the import stopped, blamed on voicemail."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from chattr import blobs, commands
from chattr.config import Settings
from chattr.parsers.mbox_parser import MboxParser

DATA = b"the same signature logo" * 100


@pytest.mark.parametrize("store", ["bytes", "file"])
def test_a_writer_that_finishes_first_does_not_stop_the_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, store: str
) -> None:
    root, source = tmp_path / "files", tmp_path / "logo.png"
    source.write_bytes(DATA)
    digest = blobs.hashlib.sha256(DATA).hexdigest()
    real_replace, raced = os.replace, []

    def write() -> str:
        if store == "bytes":
            return blobs.store_by_hash(root, DATA, ".png")[1]
        return blobs.store_file_by_hash(root, source, digest)

    def replace(src: object, dst: object) -> None:  # the other reader gets in between
        if not raced:
            raced.append(True)
            write()
        real_replace(src, dst)

    monkeypatch.setattr(blobs.os, "replace", replace)
    relative = write()
    assert raced and (root / relative).read_bytes() == DATA
    assert not list(root.rglob("*.part*"))  # nothing half-written left behind


def test_a_missing_file_in_a_mail_import_is_not_blamed_on_voicemail(
    chattr_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mbox = tmp_path / "one.mbox"
    mbox.write_bytes(b"From a@example.com Mon Jan  6 10:00:00 2025\nSubject: x\n\nhi\n")

    def missing(self: MboxParser, path: object) -> list:  # type: ignore[type-arg]
        raise FileNotFoundError(2, "No such file or directory", "/files/ab/abcdef.png.part")

    monkeypatch.setattr(MboxParser, "parse", missing)
    with pytest.raises(commands.CommandError) as stop:
        commands.convert(Settings.load(chattr_root), "mail", mbox)
    message = str(stop.value)
    assert "voicemail" not in message.lower()
    assert "abcdef.png.part" in message and "one.mbox" in message
