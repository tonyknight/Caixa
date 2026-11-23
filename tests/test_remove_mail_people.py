"""Removing someone met in mail ends them as a person, not their mail.

They get no tile (by name, nor by address in Unrecognized), and the bug was that they came back
there. Their mail stays whole: a thread with nobody else in it is kept under People/Removed (with
its files), still listed under Mail with the name the mail gives; a thread shared with someone
still in the box is filed with them. (Texts are still deleted with them, as before.)"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family
from fixtures.builders.noisy_mbox import NoisyMail

from chattr.pages import templates_fingerprint

from caixa import owner
from caixa.box import Box
from caixa.collectors.chattr import collectors
from caixa.service import Service

BEATRIZ, BEATRIZ_MAIL = "Beatriz Lima", "beatriz.lima@example.net"
PEDRO, PEDRO_MAIL = "Pedro Alves", "pedro.alves@example.net"
BOOK_CLUB = "(2023-02-01) Book club in March.html"


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


def _root(service: Service) -> Path:
    assert service.box is not None
    return service.box.root


def _index(service: Service) -> str:
    return html.unescape((_root(service) / "index.html").read_text(encoding="utf-8"))


def _tiles(service: Service) -> list[str]:
    return re.findall(r'<a class="tile[^"]*".*?</a>', _index(service), re.S)


def _mail_row(service: Service, subject: str) -> str:
    (row,) = [r for r in re.findall(r"<li data-account=.*?</li>", _index(service)) if subject in r]
    return row


def _named(service: Service, name: str, address: str) -> None:
    """Kept as a person, as sorting their tile or typing their name does."""
    done = service.people_link("Mail", address, name)
    assert service.wait(done["job"]["id"], 120)["status"] == "done"


def _removed(service: Service, **chosen: object) -> None:
    done = service.people_delete(**chosen)
    assert service.wait(done["job"]["id"], 120)["status"] == "done"


def _kept_whole(service: Service) -> None:
    """Beatriz's thread: no tile, the page and its files under People/Removed, listed under Mail."""
    root = _root(service)
    assert not any(BEATRIZ in t or BEATRIZ_MAIL in t for t in _tiles(service)), "a tile came back"
    assert not (root / "People" / BEATRIZ).exists()
    kept = root / "People" / "Removed" / "Mail" / "Gmail"
    page = html.unescape((kept / BOOK_CLUB).read_text(encoding="utf-8"))
    assert "we meet on the 9th" in page and "Lovely, thank you." in page
    assert BEATRIZ in page and BEATRIZ_MAIL in page  # as the mail names her
    assert list((kept / "Attachments").iterdir())  # her signature logos stay with it
    row = _mail_row(service, "Book club in March")
    assert "People/Removed/Mail/Gmail/" in row and BEATRIZ in row
    assert BEATRIZ_MAIL not in {h["identifier"] for h in service.people_unresolved()["handles"]}


@pytest.mark.parametrize(
    "chosen",
    [
        {"people": [BEATRIZ]},  # from her tile
        {"handles": [{"service": "Mail", "identifier": BEATRIZ_MAIL}]},  # as in Unrecognized
    ],
    ids=["by-name", "by-address"],
)
def test_someone_met_only_in_mail_loses_their_tile_and_keeps_their_mail(
    service: Service, chosen: dict[str, object]
) -> None:
    _named(service, BEATRIZ, BEATRIZ_MAIL)
    assert any(f'data-name="{BEATRIZ}"' in t for t in _tiles(service))
    items = service.box_status()["items"]
    _removed(service, **chosen)
    _kept_whole(service)
    assert service.box_status()["items"] == items  # not one mail less
    service.box_open(str(_root(service)))  # opening the box again draws nobody back
    _kept_whole(service)


def test_a_shared_thread_is_filed_with_someone_still_in_the_box(service: Service) -> None:
    _named(service, PEDRO, PEDRO_MAIL)
    _removed(service, people=[PEDRO])
    root = _root(service)
    assert not any(PEDRO in t or PEDRO_MAIL in t for t in _tiles(service)), "a tile came back"
    assert not (root / "People" / PEDRO).exists()
    sintra = "(2023-05-01) Sintra walk on Saturday.html"
    assert (root / "People" / "Sofia Reis" / "Mail" / "Gmail" / sintra).is_file()  # wrote next
    assert not (root / "People" / "Removed" / "Mail" / "Gmail" / sintra).exists()
    joao = (root / "People" / "João Costa" / "João Costa.html").read_text(encoding="utf-8")
    assert "Sintra walk on Saturday" in joao


def test_a_box_where_people_were_removed_before_this_fix_is_put_right_when_opened(
    service: Service,
) -> None:
    """The maintainer's box: people on the removed list, drawn by the version before (their mail
    under their address, an Unrecognized tile each). Opening the box once is enough."""
    root = _root(service)
    _named(service, BEATRIZ, BEATRIZ_MAIL)
    assert service.box is not None
    owner.add_removed(service.box, [{"person": BEATRIZ}])  # as the earlier removal left it
    settings_file = root / ".caixa" / "box.yaml"
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    data["pages"] = "drawn before the fix"
    settings_file.write_text(json.dumps(data), encoding="utf-8")

    service.box_open(str(root))
    redraws = [j for j in service.call("jobs.list") if j["kind"] == "refresh"]
    assert redraws and all(service.wait(j["id"], 120)["status"] == "done" for j in redraws)
    _kept_whole(service)
    assert json.loads(settings_file.read_text(encoding="utf-8"))["pages"] == templates_fingerprint()
