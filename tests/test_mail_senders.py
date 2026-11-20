"""Sorting: who is known, who is to sort, what the owner chose and ignored, and what a choice brings."""

from __future__ import annotations

from pathlib import Path

import pytest
from fixtures import family
from fixtures.builders.noisy_mbox import NoisyMail

from caixa.mail.index import MailIndex
from caixa.mail.senders import KEYS, LABELS, listing

OWNER = {family.OWNER.emails[0]}
KNOWN = {p.emails[0]: p.name for p in (family.ANA, family.JOAO, family.RUI)}
NAMES = {p.name.casefold(): p.name for p in (family.ANA, family.JOAO, family.RUI)}


@pytest.fixture
def source(tmp_path: Path, noisy_mail: NoisyMail) -> tuple[MailIndex, int]:
    index = MailIndex(tmp_path / "index.sqlite")
    (read,) = index.read(noisy_mail.gmail, account="Gmail")
    return index, read.source_id


def _listing(source: tuple[MailIndex, int], **decisions: set[str]):  # type: ignore[no-untyped-def]
    index, source_id = source
    return {
        c.key: c
        for c in listing(
            index,
            source_id,
            OWNER,
            KNOWN,
            NAMES,
            chosen=decisions.get("chosen", set()),
            ignored=decisions.get("ignored", set()),
            imported=decisions.get("imported", set()),
        )
    }


def test_categories_and_labels(source: tuple[MailIndex, int]) -> None:
    found = listing(source[0], source[1], OWNER, KNOWN, NAMES, set(), set(), set())
    assert (
        [c.key for c in found]
        == list(KEYS)
        == ["known", "to_sort", "to_import", "ignored", "imported"]
    )
    assert [c.label for c in found] == [LABELS[k] for k in KEYS] == [
        "Known", "To sort", "To import", "Ignored", "Imported"
    ]  # fmt: skip


def test_known_people_by_address_are_chosen_and_by_name_wait(source: tuple[MailIndex, int]) -> None:
    found = _listing(source)
    known = {r.address: r for r in found["known"].rows}
    assert set(known) == {
        "ana.costa@example.com",
        "joao.costa@example.org",
        "rui.pereira@example.org",
        "rui.home@example.net",
    }
    assert (known["ana.costa@example.com"].known_by, known["ana.costa@example.com"].chosen) == (
        "address",
        True,
    )
    home = known["rui.home@example.net"]
    assert (home.known_by, home.person, home.chosen) == ("name", "Rui Pereira", False)
    rui = known["rui.pereira@example.org"]
    assert (rui.mails, rui.owner_wrote, rui.chosen) == (0, 1, True)  # the owner's unanswered mail
    assert {r.address for r in found["to_import"].rows} == {
        "ana.costa@example.com",
        "joao.costa@example.org",
        "rui.pereira@example.org",
    }
    everyone = {r.address for c in found.values() for r in c.rows}
    assert family.OWNER.emails[0] not in everyone


def test_to_sort_starts_with_the_owners_correspondents(source: tuple[MailIndex, int]) -> None:
    rows = _listing(source)["to_sort"].rows
    assert [r.address for r in rows[:3]] == [
        "beatriz.lima@example.net",
        "news@escola.example.org",
        "hikers@lists.example.org",
    ]
    assert rows[3].address == "news@dailyfold.example.com" and rows[3].mails == 6
    assert all(r.known_by is None and not r.chosen for r in rows)


def test_choosing_ignoring_and_which_wins(source: tuple[MailIndex, int]) -> None:
    found = _listing(
        source,
        chosen={"beatriz.lima@example.net", "carlos.mendes@example.net"},
        ignored={"carlos.mendes@example.net", "ana.costa@example.com"},
        imported={"joao.costa@example.org"},
    )
    to_import = {r.address for r in found["to_import"].rows}
    assert "beatriz.lima@example.net" in to_import
    assert "carlos.mendes@example.net" not in to_import  # ignoring wins over choosing
    assert {r.address for r in found["ignored"].rows} == {
        "carlos.mendes@example.net",
        "ana.costa@example.com",
    }
    assert "ana.costa@example.com" not in {r.address for r in found["known"].rows}
    assert {r.address for r in found["imported"].rows} == {"joao.costa@example.org"}
    assert "joao.costa@example.org" not in to_import
    sort = {r.address for r in found["to_sort"].rows}
    assert not sort & (to_import | {"carlos.mendes@example.net", "joao.costa@example.org"})


def test_counts_add_up(source: tuple[MailIndex, int]) -> None:
    for category in _listing(source).values():
        assert category.senders == len(category.rows)
        assert category.mails == sum(r.mails for r in category.rows)
        assert category.size == sum(r.size for r in category.rows)
