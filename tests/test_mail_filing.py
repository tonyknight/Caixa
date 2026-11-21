"""Where mail goes: each conversation with its person, in its account's folder, with its files."""

from __future__ import annotations

from pathlib import Path

import pytest
from fixtures import family
from fixtures.builders.noisy_mbox import NoisyMail

from caixa.box import Box
from caixa.collectors.chattr import collectors


@pytest.fixture(scope="module")
def box(tmp_path_factory: pytest.TempPathFactory, noisy_mail: NoisyMail) -> Box:
    made = Box.create(tmp_path_factory.mktemp("mail-box") / "Box", name="Mail box")
    with made.master() as master:
        master.add_person(family.OWNER.name, is_owner=True)
        for person in (family.ANA, family.JOAO, family.RUI):
            master.add_alias(master.add_person(person.name), person.emails[0], "email")
        master.commit()
    mail = next(c for c in collectors() if c.info.id == "mail")
    mail.run(made, noisy_mail.gmail, {"account": "Gmail"}, lambda step: None)
    return made


def _names(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def test_conversations_go_to_their_person_in_the_accounts_folder(box: Box) -> None:
    joao = box.root / "People" / "João Costa" / "Mail" / "Gmail"
    assert "(2019-11-02) Fotos de São Martinho.html" in _names(joao)
    assert "(2019-12-20) The attic boxes.html" in _names(joao)
    rui = box.root / "People" / "Rui Pereira" / "Mail" / "Gmail"
    assert any("Lunch next week" in n for n in _names(rui))  # the owner's unanswered mail
    beatriz = box.root / "People" / "Beatriz Lima" / "Mail" / "Gmail"
    assert "(2023-02-01) Book club in March.html" in _names(beatriz)
    assert not (box.root / "Mail").exists()  # no top-level Mail folder for account mail


def test_attachments_are_dated_and_kept_once(box: Box) -> None:
    joao = box.root / "People" / "João Costa" / "Mail" / "Gmail" / "Attachments"
    assert _names(joao) == ["(2019-11-02) image001 (2).png", "(2019-11-02) image001.png"]
    beatriz = box.root / "People" / "Beatriz Lima" / "Mail" / "Gmail" / "Attachments"
    assert _names(beatriz) == ["(2023-02-01) logo.png"]  # a signature, sent three times


def test_tracking_pixels_are_not_filed(box: Box) -> None:
    gifs = [p for p in (box.root / "People").rglob("*.gif")]
    assert gifs == []


# --- The conversation page (T03) ------------------------------------------------------------------

import html as html_text  # noqa: E402
import re  # noqa: E402


def _page(box: Box, person: str, name: str) -> str:
    return (box.root / "People" / person / "Mail" / "Gmail" / name).read_text(encoding="utf-8")


def test_a_conversation_page_is_a_stack_of_cards(box: Box) -> None:
    page = _page(box, "Beatriz Lima", "(2023-02-01) Book club in March.html")
    assert page.count('class="card') == 3
    assert page.count('class="subject"') == 3 and "Re: Book club in March" in page
    assert "beatriz.lima@example.net" in page and "maria.costa@example.com" in page
    assert "2023-02-01" in page and "\u221205:00" in page  # (the minus sign the pages use)
    assert page.count('sandbox=""') == 2  # Beatriz's two HTML mails, in frames that run nothing
    assert "data:image/png;base64," in html_text.unescape(page)  # her logo, embedded
    assert page.count("All headers") == 3 and "X-Gmail-Labels" in page
    assert "../../../../index.html" in page  # back to the box's index


def test_plain_mail_is_text_and_files_are_listed(box: Box) -> None:
    attic = _page(box, "João Costa", "(2019-12-20) The attic boxes.html")
    assert "<iframe" not in attic and "From the attic I brought down three boxes" in attic
    photos = _page(box, "João Costa", "(2019-11-02) Fotos de São Martinho.html")
    assert 'src="Attachments/(2019-11-02)%20image001.png"' in photos


def test_no_page_runs_a_script_or_loads_from_the_internet(box: Box) -> None:
    for page in (box.root / "People").rglob("Mail/Gmail/*.html"):
        text = html_text.unescape(html_text.unescape(page.read_text(encoding="utf-8"))).lower()
        body = text.split('<script type="application/json"', 1)[0]  # (the page's data island)
        assert "<script>" not in body.replace("<script>/* pictures", ""), page.name
        assert not re.search(r"src\s*=\s*[\"']?\s*https?://", body), page.name
        assert not re.search(r"\son(load|click|error)\s*=", body), page.name
