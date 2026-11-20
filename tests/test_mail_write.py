"""Writing a Cleaned or Reduced mbox: chosen mails copied byte for byte, checked, then named."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from caixa.mail import write
from caixa.mail.index import MailError
from caixa.mail.write import output_name, output_path, preflight

TODAY = date(2026, 11, 20)


@pytest.mark.parametrize(
    ("source", "tag", "expected"),
    [
        (
            "All mail Including Spam and Trash.mbox",
            "Cleaned",
            "(2026-11-20) All mail Including Spam and Trash [Cleaned].mbox",
        ),
        (
            "(2026-11-18) All mail Including Spam and Trash [Cleaned].mbox",
            "Reduced",
            "(2026-11-20) All mail Including Spam and Trash [Reduced].mbox",
        ),
        ("(2026-11-19) Work [Reduced].mbox", "Reduced", "(2026-11-20) Work [Reduced].mbox"),
        ("Takeout/Mail/Work.mbox", "Cleaned", "(2026-11-20) Work [Cleaned].mbox"),
        ("Archive/Inbox.mbox/mbox", "Cleaned", "(2026-11-20) Inbox [Cleaned].mbox"),
        ("old-export", "Cleaned", "(2026-11-20) old-export [Cleaned].mbox"),
    ],
)
def test_names(source: str, tag: str, expected: str) -> None:
    assert output_name(source, tag, TODAY) == expected


def test_the_new_file_goes_beside_the_source_and_never_over_another(tmp_path: Path) -> None:
    source = tmp_path / "exports" / "Work.mbox"
    source.parent.mkdir()
    source.write_bytes(b"From a@example.com Mon Jan  1 00:00:00 2024\n\nhi\n")
    first = output_path(source, "", "Cleaned", TODAY)
    assert first == tmp_path / "exports" / "(2026-11-20) Work [Cleaned].mbox"
    first.write_bytes(b"")
    assert output_path(source, "", "Cleaned", TODAY).name == "(2026-11-20) Work [Cleaned] (2).mbox"
    zipped = tmp_path / "takeout.zip"
    zipped.write_bytes(b"")
    assert output_path(zipped, "Takeout/Mail/Work.mbox", "Cleaned", TODAY) == (
        tmp_path / "(2026-11-20) Work [Cleaned].mbox"
    )
    apple = tmp_path / "Mail" / "Inbox.mbox" / "mbox"
    assert output_path(apple, "", "Reduced", TODAY) == (
        tmp_path / "Mail" / "(2026-11-20) Inbox [Reduced].mbox"
    )


def test_an_unwritable_folder_or_too_little_room_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight(tmp_path, 1000)  # fine
    monkeypatch.setattr(write.os, "access", lambda path, mode: False)
    with pytest.raises(MailError, match="cannot be written"):
        preflight(tmp_path, 1000)
    monkeypatch.undo()

    class Usage:
        total, used, free = 10**12, 10**12 - 5_000_000, 5_000_000

    monkeypatch.setattr(write.shutil, "disk_usage", lambda path: Usage())
    with pytest.raises(MailError, match="room"):
        preflight(tmp_path, 4_000_000_000)
