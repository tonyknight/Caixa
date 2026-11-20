"""The master's record of imported mail (`accounts`, `mail`, `mail_accounts`, `mail_threads`).

After the Mail collector has brought a working mbox into Chattr's store and the master's items,
`record_mail` reads Chattr's mail (read-only) and records, for every mail that came with an
account: its facts (Message-ID, thread, date and offset, sender, recipients, subject; its plain text
is its item's `text`), the account, and its conversation with its counts. A mail met again in a
second account keeps its first account; the second is added to `mail_accounts`. What later steps
add to a conversation (its page, its home person, its summary) is never overwritten here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from chattr import commands
from chattr.config import Settings

from caixa.box import Box
from caixa.master import Master


def chattr_database(box: Box) -> Path:
    """Where the box's Chattr store is (the Chattr collectors' working folder)."""
    return Path(commands.central_database(Settings.load(box.work_dir("chattr"))))


def _account(master: Master, name: str) -> int:
    db = master.connection
    db.execute("INSERT OR IGNORE INTO accounts (name) VALUES (?)", (name,))
    return int(db.execute("SELECT id FROM accounts WHERE name = ?", (name,)).fetchone()[0])


def record_mail(
    master: Master,
    chattr_db: Path,
    account: Optional[str] = None,
    seen: Optional[set[str]] = None,
) -> dict[str, int]:
    """Record every mail of Chattr's store that has an account; returns how many mails were
    recorded (`mails`), how many were new (`new`) and how many conversations were touched.

    `account` and `seen` (the Message-IDs of the mbox just imported) say which mails this import
    held: a mail Chattr already had keeps the account it came with first, and this one is added to
    the accounts it was seen in."""
    db = master.connection
    db.execute("ATTACH DATABASE ? AS chattr", (f"{Path(chattr_db).resolve().as_uri()}?mode=ro",))
    try:
        rows = db.execute(
            "SELECT m.id, m.source_id, m.timestamp_utc, m.tz_offset_minutes, m.mail_headers, "
            "m.service_specific, h.normalized, h.display_name, c.source_id, c.name, "
            "(SELECT COUNT(*) FROM chattr.attachments a WHERE a.message_id = m.id) "
            "FROM chattr.messages m JOIN chattr.conversations c ON c.id = m.conversation_id "
            "LEFT JOIN chattr.handles h ON h.id = m.sender_handle_id "
            "WHERE m.content_type = 'email' AND c.service = 'Mail' "
            "AND m.id IN (SELECT id FROM main.items)"
        ).fetchall()
        recorded = new = 0
        threads: dict[str, dict[str, Any]] = {}
        for (item, message_id, when, offset, headers_json, specific_json, address, name,
             thread, conversation_name, files) in rows:  # fmt: skip
            specific = json.loads(specific_json or "{}")
            first = specific.get("account")
            if not first:
                continue  # imported before the mail workflow, without an account
            headers = json.loads(headers_json or "{}")
            account_id = _account(master, str(first))
            recipients = [
                [field, p.get("name", ""), p.get("address", "")]
                for field in ("to", "cc")
                for p in headers.get(field, [])
            ]
            known = db.execute("SELECT account_id FROM mail WHERE item_id = ?", (item,)).fetchone()
            if known is None:
                db.execute(
                    "INSERT INTO mail (item_id, account_id, message_id, thread_key, date_utc, "
                    "tz_offset_minutes, sender_address, sender_name, recipients, subject) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (item, account_id, message_id, thread, when, offset, address, name,
                     json.dumps(recipients, ensure_ascii=False), headers.get("subject") or ""),
                )  # fmt: skip
                new += 1
            else:
                db.execute(
                    "UPDATE mail SET thread_key = ?, recipients = ?, subject = ? WHERE item_id = ?",
                    (thread, json.dumps(recipients, ensure_ascii=False),
                     headers.get("subject") or "", item),
                )  # fmt: skip
            held = [account_id]
            if account and seen is not None and message_id in seen:
                held.append(_account(master, account))
            db.executemany(
                "INSERT OR IGNORE INTO mail_accounts (item_id, account_id) VALUES (?, ?)",
                [(item, a) for a in held],
            )
            entry = threads.setdefault(thread, {"name": conversation_name or "", "files": 0})
            entry["files"] += int(files)
            recorded += 1
        for thread, entry in threads.items():
            first, last, mails, account_id = db.execute(
                "SELECT MIN(date_utc), MAX(date_utc), COUNT(*), "
                "(SELECT account_id FROM mail WHERE thread_key = ? ORDER BY date_utc LIMIT 1) "
                "FROM mail WHERE thread_key = ?",
                (thread, thread),
            ).fetchone()
            db.execute(
                "INSERT INTO mail_threads (thread_key, account_id, subject, first_utc, last_utc, "
                "mails, files) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (thread_key) DO UPDATE SET "
                "account_id = excluded.account_id, subject = excluded.subject, "
                "first_utc = excluded.first_utc, last_utc = excluded.last_utc, "
                "mails = excluded.mails, files = excluded.files",
                (thread, account_id, entry["name"], first, last, mails, entry["files"]),
            )
        master.commit()
    finally:
        db.execute("DETACH DATABASE chattr")
    return {"mails": recorded, "new": new, "threads": len(threads)}
