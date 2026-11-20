"""The mail index: an mbox read once, mail by mail, without importing anything."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fixtures.builders.noisy_mbox import MAILBOX_NAME, NoisyMail

from caixa.collectors.base import Progress
from caixa.mail.index import MailError, MailIndex


@pytest.fixture
def index(tmp_path: Path) -> MailIndex:
    return MailIndex(tmp_path / "mail" / "index.sqlite")


def _rows(index: MailIndex, source_id: int) -> list[dict[str, Any]]:
    db = index.connection
    db.row_factory = sqlite3.Row
    return [
        dict(r)
        for r in db.execute(
            "SELECT * FROM mails WHERE source_id = ? ORDER BY position", (source_id,)
        )
    ]


def _by_subject(rows: list[dict[str, Any]], subject: str) -> dict[str, Any]:
    (row,) = [r for r in rows if r["subject"] == subject]
    return row


def test_every_mail_is_indexed_with_its_facts(index: MailIndex, noisy_mail: NoisyMail) -> None:
    (result,) = index.read(noisy_mail.gmail, account="Gmail")
    expected = [m for m in noisy_mail.catalogue.values() if "gmail" in m.accounts]
    assert result.mails == len(expected) and not result.reused and result.account == "Gmail"
    rows = _rows(index, result.source_id)
    assert len(rows) == len(expected)
    first = _by_subject(rows, "Fotos de São Martinho")
    assert first["message_id"] == "joao-photos-1@example.org"
    assert first["sender_address"] == "joao.costa@example.org"
    assert first["sender_name"] == "João Costa"
    assert first["tz_offset_minutes"] == 0 and first["date_utc"].startswith("2019-11-02T09:30")
    assert json.loads(first["labels"]) == ["Inbox", "Família"]
    assert json.loads(first["recipients"]) == [["to", "Maria Costa", "maria.costa@example.com"]]
    reply = _by_subject(rows, "Re: Wedding update")
    assert reply["in_reply_to"] == "ana-wedding-1@example.com"
    assert _by_subject(rows, "Wedding update")["tz_offset_minutes"] == -300
    assert _by_subject(rows, "Café na sexta — confirmas?")["sender_name"] == "Inês Rocha"
    assert _by_subject(rows, "Book club in March")["attachments"] == 1
    assert _by_subject(rows, "You have 3 new notifications")["position"] >= 0
    signals = json.loads(_by_subject(rows, "The Daily Fold — issue 2")["signals"])
    assert signals["list-id"].startswith("The Daily Fold") and signals["precedence"] == "bulk"


def test_the_ranges_are_the_file_and_each_hash_matches(
    index: MailIndex, noisy_mail: NoisyMail
) -> None:
    (result,) = index.read(noisy_mail.gmail, account="Gmail")
    data = noisy_mail.gmail.read_bytes()
    rows = _rows(index, result.source_id)
    assert rows[0]["offset"] == 0
    for row, following in zip(rows, rows[1:] + [None]):
        end = row["offset"] + row["length"]
        assert end == (following["offset"] if following else len(data))
        piece = data[row["offset"] : end]
        assert piece.startswith(b"From ")
        assert hashlib.sha256(piece).hexdigest() == row["sha256"]


def test_thread_keys(index: MailIndex, noisy_mail: NoisyMail) -> None:
    (result,) = index.read(noisy_mail.gmail, account="Gmail")
    rows = _rows(index, result.source_id)
    photos = {r["thread_key"] for r in rows if "Fotos de São Martinho" in r["subject"]}
    assert photos == {"gmail:1790000000000000001"}
    attic = {r["thread_key"] for r in rows if "The attic boxes" in r["subject"]}
    assert attic == {"msgid:joao-attic-1@example.org"}
    walk = {r["thread_key"] for r in rows if "Sintra walk" in r["subject"]}
    assert len(walk) == 1
    nomid = _by_subject(rows, "Hello from the conference")
    assert nomid["message_id"] is None and nomid["thread_key"]


def test_senders_are_summed(index: MailIndex, noisy_mail: NoisyMail) -> None:
    (result,) = index.read(noisy_mail.gmail, account="Gmail")
    db = index.connection
    mails, size, names, first, last = db.execute(
        "SELECT mails, size, names, first_utc, last_utc FROM senders "
        "WHERE source_id = ? AND address = ?",
        (result.source_id, "news@dailyfold.example.com"),
    ).fetchone()
    lengths = db.execute(
        "SELECT SUM(length) FROM mails WHERE source_id = ? AND sender_address = ?",
        (result.source_id, "news@dailyfold.example.com"),
    ).fetchone()[0]
    assert mails == 6 and size == lengths and json.loads(names) == ["The Daily Fold"]
    assert first < last


def test_one_or_four_workers_give_the_same_index(tmp_path: Path, noisy_mail: NoisyMail) -> None:
    one, four = MailIndex(tmp_path / "1.sqlite"), MailIndex(tmp_path / "4.sqlite")
    (a,) = one.read(noisy_mail.gmail, account="Gmail", workers=1, range_size=4096)
    (b,) = four.read(noisy_mail.gmail, account="Gmail", workers=4, range_size=4096)
    assert _rows(one, a.source_id) == _rows(four, b.source_id)


def test_reading_again_reuses_and_a_changed_file_is_read_again(
    index: MailIndex, noisy_mail: NoisyMail, tmp_path: Path
) -> None:
    copy = tmp_path / "copy.mbox"
    shutil.copy(noisy_mail.gmail, copy)
    (first,) = index.read(copy, account="Gmail")
    (again,) = index.read(copy, account=None)  # the index knows its account
    assert again.reused and again.source_id == first.source_id and again.account == "Gmail"
    with copy.open("ab") as out:
        out.write(b"From a@example.com Mon Jan  1 00:00:00 2024\nSubject: added\n\nhi\n\n")
    (changed,) = index.read(copy, account=None)
    assert not changed.reused and changed.mails == first.mails + 1


def test_refusals(index: MailIndex, tmp_path: Path, noisy_mail: NoisyMail) -> None:
    text = tmp_path / "notes.mbox"
    text.write_text("Dear diary,\n")
    with pytest.raises(MailError, match="not an mbox"):
        index.read(text, account="Gmail")
    with pytest.raises(MailError, match="account"):
        index.read(noisy_mail.gmail, account=None)
    for bad in ("", "  ", "a/b", "..", ".hidden", "x" * 65):
        with pytest.raises(MailError, match="account"):
            index.read(noisy_mail.gmail, account=bad)
    with pytest.raises(MailError, match="Not found"):
        index.read(tmp_path / "missing.mbox", account="Gmail")


def test_cancelling_leaves_no_half_read_source(index: MailIndex, noisy_mail: NoisyMail) -> None:
    class Stop(Exception):
        pass

    def progress(step: Progress) -> None:
        if step.current:
            raise Stop()

    with pytest.raises(Stop):
        index.read(noisy_mail.gmail, account="Gmail", range_size=4096, progress=progress)
    assert index.connection.execute("SELECT COUNT(*) FROM mails").fetchone()[0] == 0
    assert (
        index.connection.execute("SELECT COUNT(*) FROM sources WHERE status = 'read'").fetchone()[0]
        == 0
    )
    (result,) = index.read(noisy_mail.gmail, account="Gmail")
    assert not result.reused and result.mails > 50


def test_cleaned_and_reduced_names_give_the_kind(
    index: MailIndex, noisy_mail: NoisyMail, tmp_path: Path
) -> None:
    named = tmp_path / f"(2026-11-20) {MAILBOX_NAME[:-5]} [Cleaned].mbox"
    shutil.copy(noisy_mail.gmail, named)
    index.read(named, account="Gmail")
    assert index.connection.execute("SELECT kind FROM sources").fetchone()[0] == "cleaned"


def test_the_index_file_is_private(index: MailIndex, noisy_mail: NoisyMail) -> None:
    index.read(noisy_mail.gmail, account="Gmail")
    assert index.path.stat().st_mode & 0o077 == 0
    assert index.path.parent.stat().st_mode & 0o077 == 0
    assert zipfile.is_zipfile(noisy_mail.zip)  # (the zip test of T02 uses it)
