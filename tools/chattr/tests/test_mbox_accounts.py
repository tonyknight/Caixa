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
