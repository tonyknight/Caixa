"""The master records mail: each mail's facts, its account, and its conversation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fixtures import family
from fixtures.builders.noisy_mbox import NoisyMail

from caixa.box import Box
from caixa.collectors.chattr import collectors
from caixa.mail.index import MailIndex
from caixa.mail.records import chattr_database, record_mail


@pytest.fixture
def box(tmp_path: Path) -> Box:
    made = Box.create(tmp_path / "Box", name="Mail box")
    with made.master() as master:
        master.add_person(family.OWNER.name, is_owner=True)
        master.commit()
    return made


def _import(box: Box, mbox: Path, account: str) -> dict[str, int]:
    mail = next(c for c in collectors() if c.info.id == "mail")
    mail.run(box, mbox, {"account": account}, lambda step: None)
    index = MailIndex(box.caixa_dir / "test-index.sqlite")
    (read,) = index.read(mbox, account=account)
    seen = {r[0] for r in index.connection.execute(
        "SELECT message_id FROM mails WHERE source_id = ? AND message_id IS NOT NULL",
        (read.source_id,))}  # fmt: skip
    with box.master() as master:
        return record_mail(master, chattr_database(box), account, seen)


def test_every_mail_is_recorded_with_its_facts_and_account(box: Box, noisy_mail: NoisyMail) -> None:
    counts = _import(box, noisy_mail.gmail, "Gmail")
    assert counts["mails"] == 56
    with box.master() as master:
        db = master.connection
        (accounts,) = db.execute("SELECT COUNT(*) FROM accounts").fetchone()
        row = db.execute(
            "SELECT m.message_id, m.sender_address, m.sender_name, m.subject, m.recipients, "
            "m.date_utc, m.tz_offset_minutes, a.name, i.text FROM mail m "
            "JOIN accounts a ON a.id = m.account_id JOIN items i ON i.id = m.item_id "
            "WHERE m.message_id = 'joao-photos-1@example.org'"
        ).fetchone()
    assert accounts == 1
    message_id, sender, name, subject, recipients, date, offset, account, text = row
    assert (sender, name, subject, account) == (
        "joao.costa@example.org", "João Costa", "Fotos de São Martinho", "Gmail"
    )  # fmt: skip
    assert date.startswith("2019-11-02T09:30") and offset == 0
    assert ["Maria Costa", "maria.costa@example.com"] in [r[1:] for r in json.loads(recipients)]
    assert "fotos da festa" in text


def test_conversations_are_recorded_with_their_counts(box: Box, noisy_mail: NoisyMail) -> None:
    _import(box, noisy_mail.gmail, "Gmail")
    with box.master() as master:
        rows = {
            r[0]: r[1:]
            for r in master.connection.execute(
                "SELECT subject, mails, files, first_utc < last_utc FROM mail_threads"
            )
        }
    assert rows["Fotos de São Martinho"] == (4, 2, 1)
    assert rows["The attic boxes"][0] == 3
    assert rows["Book club in March"][:2] == (3, 2)


def test_a_mail_in_a_second_account_stays_with_the_first(box: Box, noisy_mail: NoisyMail) -> None:
    _import(box, noisy_mail.gmail, "Gmail")
    _import(box, noisy_mail.work, "Work")
    with box.master() as master:
        db = master.connection
        (account,) = db.execute(
            "SELECT a.name FROM mail m JOIN accounts a ON a.id = m.account_id "
            "WHERE m.message_id = 'ana-wedding-1@example.com'"
        ).fetchone()
        seen = sorted(
            r[0]
            for r in db.execute(
                "SELECT a.name FROM mail_accounts x JOIN accounts a ON a.id = x.account_id "
                "JOIN mail m ON m.item_id = x.item_id WHERE m.message_id = 'ana-wedding-1@example.com'"
            )
        )
        (total,) = db.execute("SELECT COUNT(*) FROM mail").fetchone()
    assert account == "Gmail" and seen == ["Gmail", "Work"]
    assert total == 56 + 3  # the Work account's other three mails


def test_importing_again_adds_nothing(box: Box, noisy_mail: NoisyMail) -> None:
    _import(box, noisy_mail.gmail, "Gmail")
    with box.master() as master:
        before = master.connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    again = _import(box, noisy_mail.gmail, "Gmail")
    with box.master() as master:
        after = master.connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        mails = master.connection.execute("SELECT COUNT(*) FROM mail").fetchone()[0]
    assert before == after and mails == 56 and again["new"] == 0
