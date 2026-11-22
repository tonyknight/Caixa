"""Mail keyed by its Message-ID alone, the account it came from, and records built by workers."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fixtures.builders.noisy_mbox import build_noisy_mbox

from chattr import commands
from chattr.config import Settings
from chattr.parsers.mbox_parser import MboxParser
from chattr.records import ConversationRecord, MessageRecord, assign_ids


def _mail(thread: str, extra: str = "") -> bytes:
    return (
        b"From ana.costa@example.com Mon Jan  6 10:00:00 2025\n"
        b"From: Ana Costa <ana.costa@example.com>\nTo: Maria Costa <maria.costa@example.com>\n"
        b"Subject: Dinner\nDate: Mon, 06 Jan 2025 10:00:00 +0000\n"
        b"Message-ID: <dinner-1@example.com>\n"
        + thread.encode()
        + b"\n\nAt eight?\n\n"
        + extra.encode()
    )


def test_a_mails_id_does_not_depend_on_its_conversation() -> None:
    record = MessageRecord(
        timestamp=datetime(2025, 1, 6, tzinfo=timezone.utc), sender="a@example.com", body="hi",
        content_type="email", source_id="dinner-1@example.com",
    )  # fmt: skip
    first = assign_ids(ConversationRecord("Mail", "msgid:a"), [record])[0]
    second = assign_ids(ConversationRecord("Mail", "gmail:123"), [record])[0]
    assert first.id == second.id and first.id.startswith("mail:")
    other = MessageRecord(
        timestamp=datetime(2025, 1, 6, tzinfo=timezone.utc), sender="a", body="hi", source_id="g1"
    )
    assert (
        assign_ids(ConversationRecord("iMessage", "c1"), [other])[0].id
        != assign_ids(ConversationRecord("iMessage", "c2"), [other])[0].id
    )


def test_a_mail_threaded_differently_later_moves_to_its_new_thread(
    chattr_root: Path, tmp_path: Path
) -> None:
    settings = Settings.load(chattr_root)
    early, later = tmp_path / "early.mbox", tmp_path / "later.mbox"
    early.write_bytes(_mail("References: <root-1@example.com>"))
    later.write_bytes(_mail("X-GM-THRID: 1799"))
    commands.convert(settings, "mail", early)
    commands.convert(settings, "mail", later)
    with sqlite3.connect(commands.central_database(settings)) as db:
        rows = db.execute(
            "SELECT m.id, c.source_id FROM messages m JOIN conversations c "
            "ON c.id = m.conversation_id"
        ).fetchall()
    assert len(rows) == 1 and rows[0][1] == "gmail:1799"


def test_the_account_is_kept_with_each_mail(chattr_root: Path, tmp_path: Path) -> None:
    settings = Settings.load(chattr_root)
    mbox = tmp_path / "one.mbox"
    mbox.write_bytes(_mail("References: <root-1@example.com>"))
    commands.convert(settings, "mail", mbox, parser_options={"account": "Gmail"})
    with sqlite3.connect(commands.central_database(settings)) as db:
        (specific,) = db.execute("SELECT service_specific FROM messages").fetchone()
    assert json.loads(specific)["account"] == "Gmail"


def test_one_or_three_workers_build_the_same_records(tmp_path: Path) -> None:
    noisy = build_noisy_mbox(tmp_path / "noisy")
    one = MboxParser(attachments_dir=tmp_path / "files-1", workers=1).parse(noisy.gmail)
    three = MboxParser(attachments_dir=tmp_path / "files-3", workers=3).parse(noisy.gmail)
    assert [(b.conversation, b.records) for b in one] == [
        (b.conversation, b.records) for b in three
    ]
    stored = lambda root: sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )  # noqa: E731
    assert stored(tmp_path / "files-1") == stored(tmp_path / "files-3") != []


def test_the_parser_keeps_content_ids_and_the_header_block(tmp_path: Path) -> None:
    noisy = build_noisy_mbox(tmp_path / "noisy")
    batches = MboxParser(attachments_dir=tmp_path / "files", account="Gmail").parse(noisy.gmail)
    records = {r.source_id: r for b in batches for r in b.records}
    logo = records["beatriz-1@example.net"]
    ids = logo.service_specific["content_ids"]
    assert ids == {"logo.png.beatriz-1@noisy.example": logo.attachments[0].sha256}
    headers = logo.service_specific["headers"]
    assert "X-Gmail-Labels: Inbox" in headers and "Subject: Book club in March" in headers
    assert "content_ids" not in records["joao-attic-1@example.org"].service_specific


def test_the_folder_a_mail_came_from_is_kept(tmp_path: Path) -> None:
    noisy = build_noisy_mbox(tmp_path / "noisy")
    for workers in (1, 2):
        batches = MboxParser(account="Work", folder="Family", workers=workers).parse(noisy.work)
        records = [r for b in batches for r in b.records]
        assert records and all(r.service_specific["folder"] == "Family" for r in records)
    plain = MboxParser(account="Work").parse(noisy.work)
    assert all("folder" not in r.service_specific for b in plain for r in b.records)
