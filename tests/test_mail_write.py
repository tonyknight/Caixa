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


# --- Copying, checking and recording (T02) ------------------------------------------------------

import hashlib  # noqa: E402
import mailbox  # noqa: E402
import shutil as shell  # noqa: E402

from fixtures.builders.noisy_mbox import MAILBOX_NAME, NoisyMail  # noqa: E402

from caixa.collectors.base import Progress  # noqa: E402
from caixa.mail.index import MailIndex  # noqa: E402
from caixa.mail.write import write_mbox  # noqa: E402


def _ranges(index: MailIndex, source_id: int) -> list[tuple[int, int, int]]:
    return index.connection.execute(
        "SELECT position, offset, length FROM mails WHERE source_id = ? ORDER BY position",
        (source_id,),
    ).fetchall()


@pytest.fixture
def copied(tmp_path: Path, noisy_mail: NoisyMail) -> Path:
    folder = tmp_path / "exports"
    folder.mkdir()
    return Path(shell.copy(noisy_mail.gmail, folder / MAILBOX_NAME))


def test_the_chosen_mails_are_copied_byte_for_byte_and_the_source_is_untouched(
    tmp_path: Path, copied: Path
) -> None:
    index = MailIndex(tmp_path / "index.sqlite")
    (source,) = index.read(copied, account="Gmail")
    before = (hashlib.sha256(copied.read_bytes()).hexdigest(), copied.stat().st_mtime_ns)
    rows = _ranges(index, source.source_id)
    keep = [p for p, _, _ in rows if p % 2 == 0]
    result = write_mbox(index, source.source_id, keep, "Cleaned", today=TODAY)
    assert result.path == copied.parent / f"(2026-11-20) {MAILBOX_NAME[:-5]} [Cleaned].mbox"
    data = copied.read_bytes()
    expected = b"".join(data[o : o + n] for p, o, n in rows if p % 2 == 0)
    assert result.path.read_bytes() == expected
    assert result.mails == len(keep) and result.size == len(expected)
    box = mailbox.mbox(str(result.path), create=False)
    assert len(box) == len(keep)
    box.close()
    assert (hashlib.sha256(copied.read_bytes()).hexdigest(), copied.stat().st_mtime_ns) == before
    assert not list(copied.parent.glob("*.part"))


def test_from_a_zip_the_new_mbox_goes_beside_it(tmp_path: Path, noisy_mail: NoisyMail) -> None:
    zipped = Path(shell.copy(noisy_mail.zip, tmp_path / "gmail.zip"))
    index = MailIndex(tmp_path / "index.sqlite")
    (source,) = index.read(zipped, account="Gmail")
    rows = _ranges(index, source.source_id)
    keep = [p for p, _, _ in rows if p >= 50]
    result = write_mbox(index, source.source_id, keep, "Cleaned", today=TODAY)
    assert result.path.parent == tmp_path
    data = noisy_mail.gmail.read_bytes()
    assert result.path.read_bytes() == b"".join(data[o : o + n] for p, o, n in rows if p >= 50)


def test_one_or_four_workers_write_the_same_file(tmp_path: Path, copied: Path) -> None:
    index = MailIndex(tmp_path / "index.sqlite")
    (source,) = index.read(copied, account="Gmail")
    keep = [p for p, _, _ in _ranges(index, source.source_id) if p % 3]
    one = write_mbox(index, source.source_id, keep, "Cleaned", today=TODAY, workers=1)
    four = write_mbox(index, source.source_id, keep, "Cleaned", today=TODAY, workers=4)
    assert four.path.name.endswith("[Cleaned] (2).mbox")
    assert one.path.read_bytes() == four.path.read_bytes()


def test_the_new_mbox_is_in_the_index_as_a_child_with_the_account(
    tmp_path: Path, copied: Path
) -> None:
    index = MailIndex(tmp_path / "index.sqlite")
    (source,) = index.read(copied, account="Gmail")
    keep = [p for p, _, _ in _ranges(index, source.source_id) if p < 10]
    result = write_mbox(index, source.source_id, keep, "Cleaned", today=TODAY)
    child = {s["id"]: s for s in index.sources()}[result.source_id]
    assert (
        child["kind"],
        child["parent_id"],
        child["account"],
        child["status"],
        child["mails"],
    ) == (
        "cleaned",
        source.source_id,
        "Gmail",
        "read",
        10,
    )
    (again,) = index.read(result.path, account=None)
    assert again.reused and again.source_id == result.source_id and again.account == "Gmail"
    data = result.path.read_bytes()
    for position, offset, length in _ranges(index, result.source_id):
        sha = index.connection.execute(
            "SELECT sha256 FROM mails WHERE source_id = ? AND position = ?",
            (result.source_id, position),
        ).fetchone()[0]
        assert hashlib.sha256(data[offset : offset + length]).hexdigest() == sha
    senders = index.connection.execute(
        "SELECT SUM(mails) FROM senders WHERE source_id = ?", (result.source_id,)
    ).fetchone()[0]
    assert senders == 10


def test_a_failed_check_or_a_cancel_leaves_nothing(
    tmp_path: Path, copied: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = MailIndex(tmp_path / "index.sqlite")
    (source,) = index.read(copied, account="Gmail")
    keep = [p for p, _, _ in _ranges(index, source.source_id)]
    monkeypatch.setattr(write, "hash_ranges", lambda path, ranges: ["0" * 64 for _ in ranges])
    with pytest.raises(MailError, match="check"):
        write_mbox(index, source.source_id, keep, "Cleaned", today=TODAY)
    monkeypatch.undo()

    class Stop(Exception):
        pass

    def progress(step: Progress) -> None:
        if step.stage == "writing" and step.current:
            raise Stop()

    with pytest.raises(Stop):
        write_mbox(index, source.source_id, keep, "Cleaned", today=TODAY, progress=progress)
    assert sorted(p.name for p in copied.parent.iterdir()) == [MAILBOX_NAME]
    assert len(index.sources()) == 1
