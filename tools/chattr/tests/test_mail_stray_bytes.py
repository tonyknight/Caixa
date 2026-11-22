"""Mail whose bytes its declared encoding cannot explain imports instead of stopping the import.

Python's mail parser keeps each such byte as a stand-in character that SQLite and UTF-8 refuse.
The byte is recovered when it makes sense (UTF-8, else Windows-1252: 0xF1 is "ñ") and becomes
"�" only when nothing fits.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from chattr import commands
from chattr.config import Settings
from chattr.database_manager import DatabaseManager
from chattr.parsers.mbox_parser import MboxParser
from chattr.records import ConversationRecord, MessageRecord
from chattr.surrogates import repair, repair_text

# A mail from an old client: an undeclared Latin-1 "ñ" (0xF1) in the subject, a header and the
# body, and a UTF-8 "ã" left raw in an extra header.
MAIL = (
    b"From ana.costa@example.com Mon Jan  6 10:00:00 2025\n"
    b"From: Ana Costa <ana.costa@example.com>\nTo: Maria Costa <maria.costa@example.com>\n"
    b"Subject: Ma\xf1ana\nDate: Mon, 06 Jan 2025 10:00:00 +0000\n"
    b"Message-ID: <manana-1@example.com>\n"
    b"X-Note: S\xc3\xa3o Paulo, a\xf1o \x81\n"
    b"Content-Type: text/plain\n"
    b"\nNos vemos ma\xf1ana.\n\n"
)

NO_ID = MAIL.replace(b"Message-ID: <manana-1@example.com>\n", b"")


def test_a_stray_byte_is_recovered_when_it_makes_sense() -> None:
    assert repair_text("ma\udcf1ana") == "mañana"  # Windows-1252
    assert repair_text("S\udcc3\udca3o") == "São"  # UTF-8 split into stand-ins
    assert repair_text("x\udc81y") == "x�y"  # nothing fits
    assert repair_text("plain ñ") == "plain ñ"


def test_repair_reaches_into_records_and_their_fields() -> None:
    record = MessageRecord(
        timestamp=datetime(2025, 1, 6, tzinfo=timezone.utc), sender="a@example.com",
        body="ma\udcf1ana", mail_headers={"subject": "a\udcf1o", "to": [{"name": "Pe\udcf1a"}]},
        service_specific={"headers": "X: \udcf1\n"},
    )  # fmt: skip
    fixed = repair(record)
    assert fixed.body == "mañana"
    assert fixed.mail_headers == {"subject": "año", "to": [{"name": "Peña"}]}
    assert fixed.service_specific == {"headers": "X: ñ\n"}
    assert fixed.timestamp == record.timestamp
    assert repair(record.timestamp) is record.timestamp


def test_the_parser_hands_on_text_utf_8_can_hold(tmp_path: Path) -> None:
    for data in (MAIL, NO_ID):
        mbox = tmp_path / "old.mbox"
        mbox.write_bytes(data)
        (batch,) = MboxParser().parse(mbox)
        (record,) = batch.records
        assert record.mail_headers["subject"] == "Mañana"
        assert record.body == "Nos vemos mañana."
        headers = record.service_specific["headers"]
        assert "São Paulo, año �" in headers
        json.dumps(record.service_specific, ensure_ascii=False).encode("utf-8")
        assert batch.conversation.name == "Mañana"


def test_a_mbox_with_stray_bytes_imports(chattr_root: Path, tmp_path: Path) -> None:
    settings = Settings.load(chattr_root)
    mbox = tmp_path / "old.mbox"
    mbox.write_bytes(MAIL)
    commands.convert(settings, "mail", mbox)
    with sqlite3.connect(commands.central_database(settings)) as db:
        body, headers, specific = db.execute(
            "SELECT body, mail_headers, service_specific FROM messages"
        ).fetchone()
        (name,) = db.execute("SELECT name FROM conversations").fetchone()
    assert body == "Nos vemos mañana."
    assert json.loads(headers)["subject"] == "Mañana"
    assert "año" in json.loads(specific)["headers"]
    assert name == "Mañana"


def test_the_database_repairs_what_any_parser_hands_it(tmp_path: Path) -> None:
    conversation = ConversationRecord("Mail", "t:1", name="Ma\udcf1ana")
    record = MessageRecord(
        timestamp=datetime(2025, 1, 6, tzinfo=timezone.utc), sender="a@example.com",
        sender_name="Pe\udcf1a", body="a\udcf1o", source_id="x@example.com",
        service_specific={"headers": "\udcf1"},
    )  # fmt: skip
    with DatabaseManager(tmp_path / "chattr.db") as manager:
        manager.upsert(conversation, [record])
        row = manager._db.execute("SELECT body, service_specific FROM messages").fetchone()
    assert row["body"] == "año" and json.loads(row["service_specific"]) == {"headers": "ñ"}
