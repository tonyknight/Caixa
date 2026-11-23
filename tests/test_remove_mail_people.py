"""Deleting someone met in mail: their mail goes with them and they do not come back as a number
or an address in Unrecognized (the bug: mail was left out of removal, so their threads stayed and
were filed under their address)."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family
from fixtures.builders.noisy_mbox import NoisyMail

from caixa.box import Box
from caixa.collectors.chattr import collectors
from caixa.service import Service

BEATRIZ, BEATRIZ_MAIL = "Beatriz Lima", "beatriz.lima@example.net"
PEDRO, PEDRO_MAIL = "Pedro Alves", "pedro.alves@example.net"


@pytest.fixture
def service(tmp_path: Path, noisy_mail: NoisyMail) -> Iterator[Service]:
    box = Box.create(tmp_path / "Box", name="Mail box")
    with box.master() as master:
        master.add_person(family.OWNER.name, is_owner=True)
        for person in (family.ANA, family.JOAO, family.RUI):
            master.add_alias(master.add_person(person.name), person.emails[0], "email")
        master.commit()
    mail = next(c for c in collectors() if c.info.id == "mail")
    mail.run(box, noisy_mail.gmail, {"account": "Gmail"}, lambda step: None)
    opened = Service(roots=[tmp_path])
    opened.box_open(str(box.root))
    yield opened
    opened.close()


def _index(service: Service) -> str:
    assert service.box is not None
    return html.unescape((service.box.root / "index.html").read_text(encoding="utf-8"))


def _tiles(service: Service) -> list[str]:
    return re.findall(r'<a class="tile[^"]*".*?</a>', _index(service), re.S)


def _named(service: Service, name: str, address: str) -> None:
    """Kept as a person, as sorting their tile or typing their name does."""
    done = service.people_link("Mail", address, name)
    assert service.wait(done["job"]["id"], 120)["status"] == "done"


def _deleted(service: Service, **chosen: object) -> None:
    done = service.people_delete(**chosen)
    assert service.wait(done["job"]["id"], 120)["status"] == "done"


@pytest.mark.parametrize(
    "chosen",
    [
        {"people": [BEATRIZ]},  # from her tile
        {"handles": [{"service": "Mail", "identifier": BEATRIZ_MAIL}]},  # as in Unrecognized
    ],
    ids=["by-name", "by-address"],
)
def test_someone_met_only_in_mail_is_deleted_with_their_mail(
    service: Service, chosen: dict[str, object]
) -> None:
    assert service.box is not None
    _named(service, BEATRIZ, BEATRIZ_MAIL)
    folder = service.box.root / "People" / BEATRIZ
    assert (folder / f"{BEATRIZ}.html").is_file()
    assert any(f'data-name="{BEATRIZ}"' in t for t in _tiles(service))
    _deleted(service, **chosen)
    index = _index(service)
    assert not any(BEATRIZ in t or BEATRIZ_MAIL in t for t in _tiles(service)), "a tile came back"
    assert "Book club in March" not in index  # nor in the Mail ▸ Gmail list
    assert not folder.exists()
    assert BEATRIZ_MAIL not in {h["identifier"] for h in service.people_unresolved()["handles"]}

    service.box_open(str(folder.parent.parent))  # opening the box again draws nobody back
    assert not any(BEATRIZ_MAIL in t for t in _tiles(service))


def test_a_shared_thread_stays_and_is_filed_with_someone_still_in_the_box(
    service: Service,
) -> None:
    assert service.box is not None
    _named(service, PEDRO, PEDRO_MAIL)
    _deleted(service, people=[PEDRO])
    tiles = _tiles(service)
    assert not any(PEDRO in t or PEDRO_MAIL in t for t in tiles), "a tile came back"
    joao = (service.box.root / "People" / "João Costa" / "João Costa.html").read_text(
        encoding="utf-8"
    )
    assert "Sintra walk on Saturday" in joao  # what the others wrote stays
    assert not (service.box.root / "People" / PEDRO).exists()
    assert not (service.box.root / "People" / PEDRO_MAIL).exists()


def test_a_box_where_people_were_deleted_before_this_fix_is_cleaned_when_opened(
    service: Service,
) -> None:
    """The maintainer's box: people on the removed list whose mail stayed, drawn by the version
    before; opening the box once is enough."""
    import json

    from chattr.pages import templates_fingerprint

    from caixa import owner

    assert service.box is not None
    root = service.box.root
    _named(service, BEATRIZ, BEATRIZ_MAIL)
    owner.add_removed(service.box, [{"person": BEATRIZ}])  # as the earlier delete left it
    settings_file = root / ".caixa" / "box.yaml"
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    data["pages"] = "drawn before the fix"
    settings_file.write_text(json.dumps(data), encoding="utf-8")

    service.box_open(str(root))
    redraws = [j for j in service.call("jobs.list") if j["kind"] == "refresh"]
    assert redraws and all(service.wait(j["id"], 120)["status"] == "done" for j in redraws)
    assert not any(BEATRIZ in t or BEATRIZ_MAIL in t for t in _tiles(service))
    assert "Book club in March" not in _index(service)
    assert json.loads(settings_file.read_text(encoding="utf-8"))["pages"] == templates_fingerprint()
