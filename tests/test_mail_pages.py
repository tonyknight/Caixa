"""A conversation on the person pages: one entry for each box person in it, linking to its page."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest
from fixtures import family
from fixtures.builders.noisy_mbox import NoisyMail

from caixa.box import Box
from caixa.collectors.chattr import collectors


@pytest.fixture(scope="module")
def box(tmp_path_factory: pytest.TempPathFactory, noisy_mail: NoisyMail) -> Box:
    made = Box.create(tmp_path_factory.mktemp("mail-pages") / "Box", name="Mail box")
    with made.master() as master:
        master.add_person(family.OWNER.name, is_owner=True)
        for person in (family.ANA, family.JOAO, family.RUI):
            master.add_alias(master.add_person(person.name), person.emails[0], "email")
        master.commit()
    mail = next(c for c in collectors() if c.info.id == "mail")
    mail.run(made, noisy_mail.gmail, {"account": "Gmail"}, lambda step: None)
    return made


def _person(box: Box, name: str) -> str:
    return (box.root / "People" / name / f"{name}.html").read_text(encoding="utf-8")


def _entries(page: str) -> list[str]:
    return re.findall(r'<article class="entry [^"]*k-conversation".*?</article>', page, re.S)


def test_a_person_page_has_one_entry_per_conversation(box: Box) -> None:
    page = _person(box, "João Costa")
    entries = _entries(page)
    photos = next(e for e in entries if "Fotos de São Martinho" in e)
    assert "@Gmail" in photos and ">João Costa<" in photos
    assert "As fotos da festa de São Martinho estão prontas." in html.unescape(photos)
    assert "4 mails" in photos and "2 files" in photos
    assert 'href="Mail/Gmail/(2019-11-02)%20Fotos%20de%20S%C3%A3o%20Martinho.html"' in photos
    assert "Read the conversation" in photos
    assert 'id="date-2019-11-02"' in page and 'href="#date-2019-11-02"' in page  # in the calendar


def test_every_box_person_in_it_gets_the_entry_linking_to_the_one_page(box: Box) -> None:
    sintra = [e for e in _entries(_person(box, "João Costa")) if "Sintra walk" in e]
    assert len(sintra) == 1  # João wrote in the hikers' thread, filed with Pedro
    assert (
        'href="../Pedro%20Alves/Mail/Gmail/(2023-05-01)%20Sintra%20walk%20on%20Saturday.html"'
        in sintra[0]
    )
    assert ">Pedro Alves<" in sintra[0]  # who began it


def test_unanswered_mail_from_the_owner_shows_as_sent(box: Box) -> None:
    (lunch,) = [e for e in _entries(_person(box, "Rui Pereira")) if "Lunch next week" in e]
    assert 'class="entry sent k-conversation"' in lunch and ">Me<" in lunch


def test_someone_met_only_in_mail_has_a_page(box: Box) -> None:
    page = _person(box, "Beatriz Lima")
    assert len(_entries(page)) == 2  # March and April
    assert "Book club in March" in page and "Book club in April" in page


def _template(name: str) -> str:
    import chattr

    text = (Path(chattr.__file__).resolve().parent / "templates" / name).read_text(encoding="utf-8")
    return text.removesuffix("\n")


def test_a_page_with_conversations_carries_the_overlay_script_unchanged(box: Box) -> None:
    scripts = re.findall(r"<script>(.*?)</script>", _person(box, "João Costa"), re.S)
    assert scripts == [_template("lightbox.js"), _template("conversation.js")]
    conversation = (
        box.root / "People" / "João Costa" / "Mail" / "Gmail" / "(2019-12-20) The attic boxes.html"
    )
    assert 'target="_top"' in conversation.read_text(
        encoding="utf-8"
    )  # back to the index, whole window
