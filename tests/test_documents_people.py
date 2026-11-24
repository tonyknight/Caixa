"""Documents and people (ticket 20261124-22): authors and people named in a document matched to
the box's people, recorded in `item_people`, and the documents shown on their person pages."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa import settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import records
from caixa.documents.people import link_documents, match
from stub_server import StubServer

LETTER = "Document1.pdf"  # "Carta de João Costa", by João Costa
LEASE_PARTY = "Rui Pereira"  # named in the lease


@pytest.fixture(scope="module")
def model(pdf_family: Any) -> Iterator[StubServer]:
    from stand_in_documents import DocumentModel

    server = StubServer()
    server.respond = DocumentModel(pdf_family).respond
    yield server
    server.close()


def _people(box: Box) -> dict[str, int]:
    with box.master() as master:
        return {
            "Maria Costa": master.add_person("Maria Costa", is_owner=True),
            "João Costa": master.add_person("João Costa"),
            "Rui Pereira": master.add_person("Rui Pereira"),
        }


def _import(box: Box, pdf_family: Any, model: StubServer, base: Path) -> None:
    source = base / "pdfs"
    shutil.copytree(pdf_family.root, source)
    settings.save(box, {"documents.ocr": False, "summaries.provider": "endpoint",
                        "summaries.endpoint": model.endpoint, "summaries.model": "stand-in"})  # fmt: skip
    PdfCollector().run(box, source, {"workers": 1}, lambda step: None)


@pytest.fixture
def box(pdf_family: Any, model: StubServer, tmp_path: Path) -> Box:
    made = Box.create(tmp_path / "Box", name="Our box")
    _people(made)
    _import(made, pdf_family, model, tmp_path)
    return made


def _links(box: Box) -> set[tuple[str, str, str]]:
    """(the document's original file name, the person, the role) for every document link."""
    with box.master() as master:
        rows = master.connection.execute(
            "SELECT d.original_filename, p.name, ip.role FROM item_people ip "
            "JOIN documents d ON d.item_id = ip.item_id JOIN people p ON p.id = ip.person_id"
        ).fetchall()
    return {(str(a), str(b), str(c)) for a, b, c in rows}


def _item(box: Box, name: str) -> str:
    with box.master() as master:
        return next(
            d["item_id"] for d in records.list_documents(master) if d["original_filename"] == name
        )


def test_an_author_of_the_box_is_linked_as_sender(box: Box) -> None:
    assert (LETTER, "João Costa", "sender") in _links(box)


def test_people_named_are_linked_as_mentioned(box: Box) -> None:
    named = {(d, r) for d, p, r in _links(box) if p == LEASE_PARTY}
    assert named and all(role == "mentioned" for _, role in named)


def test_the_owner_is_not_linked(box: Box) -> None:
    assert not any(p == "Maria Costa" for _, p, _ in _links(box))


def test_an_author_is_not_also_mentioned(box: Box) -> None:
    assert (LETTER, "João Costa", "mentioned") not in _links(box)


def test_an_alias_matches_with_accents_aside(box: Box) -> None:
    with box.master() as master:
        joao = master.person_id("João Costa")
        master.add_alias(joao, "Joãozinho", "name")
        assert match(master, "joaozinho") == joao
        assert match(master, "  JOAO   costa ") == joao
        assert match(master, "Nobody Here") is None


def test_a_shared_name_matches_neither(box: Box) -> None:
    with box.master() as master:
        joao, rui = master.person_id("João Costa"), master.person_id("Rui Pereira")
        master.add_alias(joao, "Zé", "name")
        master.add_alias(rui, "Ze", "name")  # the same name, accents aside
        assert match(master, "Zé") is None and match(master, "ze") is None


def test_a_correction_of_the_author_moves_the_link(box: Box) -> None:
    from caixa.documents.corrections import correct

    letter = _item(box, LETTER)
    with box.master() as master:
        correct(box, master, letter, author="Rui Pereira")
    link_documents(box)
    links = _links(box)
    assert (LETTER, "Rui Pereira", "sender") in links
    assert (LETTER, "João Costa", "sender") not in links
    assert (LETTER, "João Costa", "mentioned") in links  # still named in it


def test_other_roles_are_left_alone(box: Box) -> None:
    letter = _item(box, LETTER)
    with box.master() as master:
        rui = master.person_id("Rui Pereira")
        master.connection.execute(
            "INSERT INTO item_people (item_id, person_id, role) VALUES (?, ?, 'depicted')",
            (letter, rui),
        )
    link_documents(box)
    assert (LETTER, "Rui Pereira", "depicted") in _links(box)


def test_people_added_later_are_linked(pdf_family: Any, model: StubServer, tmp_path: Path) -> None:
    made = Box.create(tmp_path / "Box", name="Our box")
    _import(made, pdf_family, model, tmp_path)
    assert _links(made) == set()
    _people(made)
    changed = link_documents(made)
    assert changed and (LETTER, "João Costa", "sender") in _links(made)
    assert link_documents(made) == set()  # nothing more to do


def test_a_change_waits_for_update_the_pages(box: Box) -> None:
    chattr = box.work_dir("chattr") / "Database"
    chattr.mkdir(parents=True, exist_ok=True)
    (chattr / "chattr.sqlite").touch()  # (as if the box had person pages)
    before = box.pending()["changes"]
    with box.master() as master:
        master.add_person("Ana Costa")
    link_documents(box)
    after = box.pending()
    assert after["changes"] == before + 1 and after["scope"] == "pages"


# --- On person pages (T02) ------------------------------------------------------------------------


@pytest.fixture
def family_box(pdf_family: Any, fixture_family: Any, model: StubServer, tmp_path: Path) -> Box:
    """João Costa's messages, then the documents: his letter is his."""
    from caixa.collectors.chattr import collectors
    from caixa.collectors.options import validate

    made = Box.create(tmp_path / "Box", name="Our box")
    messenger = next(c for c in collectors() if c.info.id == "messenger")
    messenger.run(made, fixture_family.paths["messenger"],
                  validate(messenger.info.options_schema, {}), lambda step: None)  # fmt: skip
    _people(made)
    _import(made, pdf_family, model, tmp_path)
    return made


def _person_page(box: Box, name: str) -> Path:
    return box.root / "People" / name / f"{name}.html"


def test_update_the_pages_puts_documents_on_person_pages(family_box: Box) -> None:
    from caixa.service import Service

    page = _person_page(family_box, "João Costa")
    assert page.is_file() and 'class="page-links"' not in page.read_text(encoding="utf-8")
    assert family_box.pending()["scope"] == "pages"  # the links wait to be drawn
    service = Service(roots=[family_box.root.parent])
    try:
        service.box_open(str(family_box.root))
        job = service.call("people.update", {})["job"]
        done = service.wait(job["id"], 300)
        assert done["status"] == "done", done["error"]
    finally:
        service.close()
    text = page.read_text(encoding="utf-8")
    assert "Documents (1)" in text and "Carta de João Costa" in text and "by them" in text
    import re
    from urllib.parse import unquote

    href = re.search(r'<a class="out" href="([^"]+)">Open</a>', text).group(1)
    target = (page.parent / unquote(href)).resolve()
    assert target.is_file() and target.suffix == ".pdf"
    with family_box.master() as master:
        letter = next(d for d in records.list_documents(master) if d["original_filename"] == LETTER)
    assert target == (family_box.root / letter["file_path"]).resolve()


def test_person_links_are_newest_first_and_never_the_owner(box: Box) -> None:
    from caixa.documents.people import person_links

    found = person_links(box)
    assert "Maria Costa" not in found
    assert found["João Costa"][0]["group"] == "Documents"
    links = found["Rui Pereira"][0]["links"]
    assert all(link["note"] == "names them" for link in links)
    assert all(link["href"].startswith("Documents/PDF/") for link in links)
