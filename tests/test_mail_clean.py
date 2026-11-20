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
