"""Cleaning: junk found by its headers, labels, senders and wording, without losing what matters."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fixtures.builders.noisy_mbox import NoisyMail

from caixa.mail.index import MailIndex

UNSUBSCRIBE = {
    *(f"fold-{n}" for n in range(1, 7)),
    "ana-forward",
    "deals-en",
    "deals-pt",
    "deals-es",
    "order-en",
    "invoice-pt",
    "booking-es",
}
RECEIPTS = {"order-en", "receipt-en", "invoice-pt", "booking-es", "eticket-en"}


@pytest.fixture
def index(tmp_path: Path) -> MailIndex:
    return MailIndex(tmp_path / "index.sqlite")


def _keyed(index: MailIndex, source_id: int, column: str) -> set[str]:
    """The catalogue keys (from `<key@domain>` Message-IDs) of the mails with `column` set."""
    rows = index.connection.execute(
        f"SELECT message_id FROM mails WHERE source_id = ? AND {column} = 1", (source_id,)
    )
    return {str(r[0]).split("@")[0] for r in rows}


def test_unsubscribe_links_and_receipts_are_found_in_the_read(
    index: MailIndex, noisy_mail: NoisyMail
) -> None:
    (result,) = index.read(noisy_mail.gmail, account="Gmail", workers=2, range_size=8192)
    assert _keyed(index, result.source_id, "unsubscribe") == UNSUBSCRIBE
    assert _keyed(index, result.source_id, "receipt") == RECEIPTS


def test_an_index_of_an_earlier_version_is_read_again(
    tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    path = tmp_path / "index.sqlite"
    MailIndex(path).read(noisy_mail.work, account="Work")
    with sqlite3.connect(path) as db:
        db.execute("UPDATE meta SET value = '1' WHERE key = 'schema'")
    again = MailIndex(path)
    assert again.sources() == []
    (result,) = again.read(noisy_mail.work, account="Work")
    assert not result.reused and result.mails == 4


# --- Flags, protections, groups (T02) -------------------------------------------------------------

from fixtures import family  # noqa: E402
from fixtures.builders.noisy_mbox import OWNER_WORK  # noqa: E402

from caixa.mail.clean import (  # noqa: E402
    GROUPS,
    classify,
    groups,
    outcome,
    owner_addresses_from_sent,
)

KNOWN = {p.emails[0] for p in (family.ANA, family.JOAO, family.RUI)}
NAMES = {p.name for p in (family.ANA, family.JOAO, family.RUI)}


def _read_both(index: MailIndex, noisy_mail: NoisyMail) -> tuple[int, int]:
    (gmail,) = index.read(noisy_mail.gmail, account="Gmail")
    (work,) = index.read(noisy_mail.work, account="Work")
    return gmail.source_id, work.source_id


def _outcomes(index: MailIndex, source_id: int) -> dict[str, str]:
    import json

    found = {}
    for message_id, subject, flags, protections in index.connection.execute(
        "SELECT message_id, subject, flags, protections FROM mails WHERE source_id = ?",
        (source_id,),
    ):
        key = str(message_id).split("@")[0] if message_id else f"subject:{subject}"
        found[key] = outcome(json.loads(flags), json.loads(protections))
    return found


def test_the_owners_addresses_come_from_their_sent_mail(
    index: MailIndex, noisy_mail: NoisyMail
) -> None:
    _read_both(index, noisy_mail)
    assert owner_addresses_from_sent(index) == {family.OWNER.emails[0], OWNER_WORK}


def test_every_mail_gets_the_catalogues_outcome(index: MailIndex, noisy_mail: NoisyMail) -> None:
    sources = _read_both(index, noisy_mail)
    owner = owner_addresses_from_sent(index)
    for source_id in sources:
        classify(index, source_id, owner, KNOWN, NAMES)
    found = {**_outcomes(index, sources[0]), **_outcomes(index, sources[1])}
    expected = {
        (m.key if m.has_message_id else f"subject:{m.subject}"): m.clean
        for m in noisy_mail.catalogue.values()
    }
    wrong = {k: (found.get(k), v) for k, v in expected.items() if found.get(k) != v}
    assert not wrong, wrong


def test_groups_carry_senders_mails_and_size(index: MailIndex, noisy_mail: NoisyMail) -> None:
    gmail, _ = _read_both(index, noisy_mail)
    classify(index, gmail, owner_addresses_from_sent(index), KNOWN, NAMES)
    found = groups(index, gmail)
    assert [g.key for g in found] == list(GROUPS)
    assert [g.label for g in found] == [
        "Lists and newsletters",
        "Notices and no-reply",
        "Unsubscribe links",
        "Spam and Trash",
        "Receipts and orders (kept)",
    ]
    by_key = {g.key: g for g in found}
    assert (by_key["lists"].senders, by_key["lists"].mails) == (5, 11)
    assert (by_key["notices"].senders, by_key["notices"].mails) == (4, 7)
    assert (by_key["unsubscribe"].senders, by_key["unsubscribe"].mails) == (3, 3)
    assert (by_key["spam_trash"].senders, by_key["spam_trash"].mails) == (2, 2)
    assert (by_key["receipts"].senders, by_key["receipts"].mails) == (4, 5)
    fold = by_key["lists"].rows[0]
    assert (fold.name, fold.address, fold.mails) == (
        "The Daily Fold",
        "news@dailyfold.example.com",
        6,
    )
    lengths = dict(
        index.connection.execute(
            "SELECT sender_address, SUM(length) FROM mails WHERE source_id = ? "
            "GROUP BY sender_address",
            (gmail,),
        ).fetchall()
    )
    assert fold.size == lengths["news@dailyfold.example.com"]
    for group in found:
        assert group.senders == len(group.rows)
        assert group.mails == sum(r.mails for r in group.rows)
        assert group.size == sum(r.size for r in group.rows)
    removable = index.connection.execute(
        "SELECT COUNT(*) FROM mails WHERE source_id = ? AND flags != '[]' AND protections = '[]'",
        (gmail,),
    ).fetchone()[0]
    assert removable == sum(g.mails for g in found if g.key != "receipts")


def test_a_kept_sender_loses_its_junk(index: MailIndex, noisy_mail: NoisyMail) -> None:
    gmail, _ = _read_both(index, noisy_mail)
    owner = owner_addresses_from_sent(index)
    classify(index, gmail, owner, KNOWN, NAMES, kept={"news@dailyfold.example.com"})
    lists = {g.key: g for g in groups(index, gmail)}["lists"]
    assert "news@dailyfold.example.com" not in {r.address for r in lists.rows}
    assert lists.mails == 5
    outcomes = _outcomes(index, gmail)
    assert {outcomes[f"fold-{n}"] for n in range(1, 7)} == {"kept:protected"}


def test_one_sender_in_a_junk_group_and_under_receipts(index: MailIndex, tmp_path: Path) -> None:
    mbox = tmp_path / "shop.mbox"
    mbox.write_bytes(
        b"From shop@example.com Mon Jan  1 00:00:00 2024\n"
        b"From: Shop <shop@example.com>\nSubject: Spring sale\nList-Id: <sale.example.com>\n"
        b"Message-ID: <a@example.com>\n\nEverything half price.\n\n"
        b"From shop@example.com Tue Jan  2 00:00:00 2024\n"
        b"From: Shop <shop@example.com>\nSubject: Your order #77 has shipped\n"
        b"List-Id: <sale.example.com>\nMessage-ID: <b@example.com>\n\nOn its way.\n\n"
    )
    (result,) = index.read(mbox, account="Gmail")
    classify(index, result.source_id, set(), set(), set())
    by_key = {g.key: g for g in groups(index, result.source_id)}
    assert [(r.address, r.mails) for r in by_key["lists"].rows] == [("shop@example.com", 1)]
    assert [(r.address, r.mails) for r in by_key["receipts"].rows] == [("shop@example.com", 1)]
