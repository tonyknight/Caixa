"""Merging people by dropping one (or several) onto another, anywhere on the people page.

The bug: a person with imported mail could be neither merged nor deleted (their mail threads
still named them as their home, and the box refused to forget them). And a drop onto someone with
no name did nothing. Now the one dropped onto keeps their name (a tile with no name becomes a
person under the name it shows) and takes everyone dropped on them."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family
from fixtures.builders.noisy_mbox import NoisyMail

from caixa.box import Box
from caixa.collectors.chattr import collectors
from caixa.mail.index import MailIndex
from caixa.mail.records import chattr_database, record_mail
from caixa.service import Service, ServiceError

BEATRIZ, BEATRIZ_MAIL = "Beatriz Lima", "beatriz.lima@example.net"
PEDRO, PEDRO_MAIL = "Pedro Alves", "pedro.alves@example.net"


@pytest.fixture
def service(tmp_path: Path, noisy_mail: NoisyMail) -> Iterator[Service]:
    """A box with mail imported as the mail window does: each thread recorded with its home."""
    box = Box.create(tmp_path / "Box", name="Mail box")
    with box.master() as master:
        master.add_person(family.OWNER.name, is_owner=True)
        for person in (family.ANA, family.JOAO, family.RUI):
            master.add_alias(master.add_person(person.name), person.emails[0], "email")
        master.commit()
    mail = next(c for c in collectors() if c.info.id == "mail")
    mail.run(box, noisy_mail.gmail, {"account": "Gmail"}, lambda step: None)
    index = MailIndex(box.caixa_dir / "test-index.sqlite")
    (read,) = index.read(noisy_mail.gmail, account="Gmail")
    seen = {r[0] for r in index.connection.execute(
        "SELECT message_id FROM mails WHERE source_id = ? AND message_id IS NOT NULL",
        (read.source_id,))}  # fmt: skip
    with box.master() as master:
        record_mail(master, chattr_database(box), "Gmail", seen)
        homes = master.connection.execute(
            "SELECT COUNT(*) FROM mail_threads WHERE home_person_id IS NOT NULL"
        ).fetchone()[0]
    assert homes > 0  # (what made merging fail)
    opened = Service(roots=[tmp_path])
    opened.box_open(str(box.root))
    yield opened
    opened.close()


def _id(service: Service, name: str) -> int:
    return next(p["id"] for p in service.people_list()["people"] if p["name"] == name)


def _names(service: Service) -> set[str]:
    return {p["name"] for p in service.people_list()["people"]}


def _waited(service: Service, done: dict) -> dict:  # type: ignore[type-arg]
    assert service.wait(done["job"]["id"], 120)["status"] == "done"
    return done


def _home(service: Service, subject: str) -> str | None:
    with service._require_box().master() as master:
        row = master.connection.execute(
            "SELECT p.name FROM mail_threads t LEFT JOIN people p ON p.id = t.home_person_id "
            "WHERE t.subject = ?",
            (subject,),
        ).fetchone()
    return row[0] if row else None


def test_people_with_mail_can_be_merged(service: Service) -> None:
    rui, joao = _id(service, family.RUI.name), _id(service, family.JOAO.name)
    assert _home(service, "Lunch next week?") == family.RUI.name
    _waited(service, service.people_merge(source=rui, target=joao))
    assert family.RUI.name not in _names(service)
    assert _home(service, "Lunch next week?") == family.JOAO.name


def test_people_with_mail_can_be_deleted(service: Service) -> None:
    _waited(service, service.people_delete(people=[family.RUI.name]))
    assert family.RUI.name not in _names(service)
    assert _home(service, "Lunch next week?") is None


def test_named_people_dropped_on_a_named_person_join_them(service: Service) -> None:
    done = _waited(
        service,
        service.call(
            "people.join",
            {"target": family.JOAO.name, "people": [family.RUI.name, family.ANA.name]},
        ),
    )
    assert done["person"]["name"] == family.JOAO.name and done["joined"] == 2
    assert not {family.RUI.name, family.ANA.name} & _names(service)
    with service._require_box().master() as master:
        joao = master.person_id(family.JOAO.name)
        assert master.find_person(family.RUI.emails[0]) == joao
        assert master.find_person(family.ANA.emails[0]) == joao


def test_a_tile_with_no_name_dropped_on_takes_the_name_it_shows(service: Service) -> None:
    """In Unrecognized: Beatriz's address onto Pedro's. Pedro (as his mail names him) becomes a
    person with both addresses."""
    done = _waited(
        service,
        service.call(
            "people.join",
            {
                "name": PEDRO,
                "target_handles": [{"service": "Mail", "identifier": PEDRO_MAIL}],
                "handles": [{"service": "Mail", "identifier": BEATRIZ_MAIL}],
            },
        ),
    )
    assert done["person"]["name"] == PEDRO
    with service._require_box().master() as master:
        pedro = master.person_id(PEDRO)
        assert master.find_person(PEDRO_MAIL) == pedro == master.find_person(BEATRIZ_MAIL)
    unresolved = {h["identifier"] for h in service.people_unresolved()["handles"]}
    assert not {PEDRO_MAIL, BEATRIZ_MAIL} & unresolved
    index = (service._require_box().root / "index.html").read_text(encoding="utf-8")
    assert f'data-name="{PEDRO}"' in index


def test_a_person_dropped_on_a_tile_with_no_name_joins_it(service: Service) -> None:
    _waited(
        service,
        service.call(
            "people.join",
            {
                "name": PEDRO,
                "target_handles": [{"service": "Mail", "identifier": PEDRO_MAIL}],
                "people": [family.RUI.name],
            },
        ),
    )
    assert family.RUI.name not in _names(service) and PEDRO in _names(service)
    assert _home(service, "Lunch next week?") == PEDRO


def test_what_cannot_be_joined_is_explained(service: Service) -> None:
    owner = _id(service, family.OWNER.name)
    with pytest.raises(ServiceError, match="owner"):
        service.call("people.join", {"target": family.JOAO.name, "people": [owner]})
    with pytest.raises(ServiceError) as missing:
        service.call("people.join", {"target": "Nobody Atall", "people": [family.RUI.name]})
    assert missing.value.kind == "not_found"
    with pytest.raises(ServiceError) as nobody:
        service.call("people.join", {"target": family.JOAO.name})
    assert nobody.value.kind == "invalid_params"
    with pytest.raises(ServiceError) as unnamed:
        service.call("people.join", {"target_handles": [{"service": "Mail", "identifier": PEDRO_MAIL}], "people": [family.RUI.name]})  # fmt: skip
    assert unnamed.value.kind == "invalid_params"
    assert {family.RUI.name, family.JOAO.name} <= _names(service)  # nothing half done
