"""The Documents ▸ PDF view (ticket 20261124-17): the index's link to it, and the page itself."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa.box import Box
from caixa.documents.view import VIEW, index_links


def test_a_box_without_documents_has_no_link(tmp_path: Path) -> None:
    assert index_links(Box.create(tmp_path / "Box", name="Our box")) == []


def test_a_box_with_documents_links_to_the_view(tmp_path: Path, pdf_family: Any) -> None:
    from caixa import settings
    from caixa.collectors.pdfImport import PdfCollector

    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.ocr": False, "documents.enrich": False})
    source = tmp_path / "pdfs"
    source.mkdir()
    shutil.copyfile(pdf_family.root / "scan_00482.pdf", source / "scan_00482.pdf")
    PdfCollector().run(box, source, {"workers": 1}, lambda step: None)
    assert index_links(box) == [
        {"group": "Documents", "links": [{"label": "PDF", "href": VIEW, "count": 1}]}
    ]


def test_the_box_index_shows_the_link(tmp_path: Path, pdf_family: Any, fixture_family: Any) -> None:
    """Messages and documents in one box: Chattr's index carries Caixa's link."""
    from caixa import settings
    from caixa.collectors.pdfImport import PdfCollector
    from caixa.collectors.registry import discover

    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.ocr": False, "documents.enrich": False})
    source = tmp_path / "pdfs"
    source.mkdir()
    shutil.copyfile(pdf_family.root / "scan_00482.pdf", source / "scan_00482.pdf")
    PdfCollector().run(box, source, {"workers": 1}, lambda step: None)
    whatsapp = discover().get("whatsapp")
    chat = fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt"
    whatsapp.run(box, chat, {}, lambda step: None)
    index = (box.root / "index.html").read_text(encoding="utf-8")
    assert '<div class="sep">Documents</div>' in index
    assert f'<a class="out" href="{VIEW}">' in index


# --- The view page (T02) -------------------------------------------------------------------------

import re  # noqa: E402
from html.parser import HTMLParser  # noqa: E402
from urllib.parse import unquote  # noqa: E402

from caixa.documents.pdf import ocr  # noqa: E402

needs_ocr = pytest.mark.skipif(not ocr.tools().ready, reason="OCR tools missing here")


@pytest.fixture(scope="module")
def viewed(pdf_family: Any, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Box]:
    from caixa import settings
    from caixa.collectors.pdfImport import PdfCollector
    from stand_in_documents import DocumentModel
    from stub_server import StubServer

    server = StubServer()
    server.respond = DocumentModel(pdf_family).respond
    base = tmp_path_factory.mktemp("view")
    source = base / "pdfs"
    shutil.copytree(pdf_family.root, source)
    box = Box.create(base / "Box", name="Our box")
    settings.save(box, {"summaries.provider": "endpoint", "summaries.endpoint": server.endpoint,
                        "summaries.model": "stand-in-documents"})  # fmt: skip
    PdfCollector().run(box, source, {"workers": 2}, lambda step: None)
    server.close()
    yield box


class _Hrefs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        href = dict(attrs).get("href")
        if tag == "a" and href:
            self.hrefs.append(href)


def _view(box: Box) -> str:
    return (box.root / VIEW).read_text(encoding="utf-8")


@needs_ocr
def test_the_view_is_drawn_with_the_other_pages(viewed: Box) -> None:
    page = _view(viewed)
    assert "<title>PDF documents</title>" in page and "documents, from" in page


@needs_ocr
def test_years_newest_first_with_their_authors(viewed: Box) -> None:
    page = _view(viewed)
    years = re.findall(r'<section class="year-block" data-year-block="(\d{4})"', page)
    assert years == sorted(set(years), reverse=True) and years[0] == "2024"
    assert 'href="2024/Banco%20Atl%C3%A2ntico/Banco%20Atl%C3%A2ntico.html"' in page
    tile = re.search(
        r'<a class="tile"[^>]*href="2024/Banco%20Atl%C3%A2ntico/[^"]*"[^>]*>.*?</a>', page, re.S
    )
    assert tile and ">3<" in tile.group(0)  # three documents of Banco Atlântico in 2024


@needs_ocr
def test_unrecognized_and_to_review(viewed: Box) -> None:
    page = _view(viewed)
    assert 'href="Unrecognized/Unrecognized.html"' in page
    review = page.split('class="review"', 1)[1].split("</section>", 1)[0]
    assert "2022 Car Insurance.pdf" in review and "The file name says another year" in review
    assert "Probably the same as another document" in review


@needs_ocr
def test_the_heat_map_links_days_to_cards(viewed: Box) -> None:
    page = _view(viewed)
    day = re.search(r'<a href="([^"]+)" class="d l\d" title="\d+ documents?">30</a>', page)
    assert day and day.group(1).startswith(
        "2024/Banco%20Atl%C3%A2ntico/Banco%20Atl%C3%A2ntico.html#d-"
    )


@needs_ocr
def test_every_document_has_an_entry_that_opens_it(viewed: Box) -> None:
    page = _view(viewed)
    assert page.count('class="entry-doc"') == 15
    assert page.count('class="open-document"') == 15
    assert 'data-words="' in page


@needs_ocr
def test_every_link_is_relative_and_lands(viewed: Box) -> None:
    hrefs = _Hrefs()
    hrefs.feed(_view(viewed))
    folder = (viewed.root / VIEW).parent
    for href in hrefs.hrefs:
        assert not href.startswith(("/", "http")), href
        target = folder / unquote(href.split("#", 1)[0])
        assert target.exists(), href


@needs_ocr
def test_the_controls_wait_for_their_script(viewed: Box) -> None:
    page = _view(viewed)
    assert re.search(r'<div class="controls" hidden>', page)
    assert "/* The documents' index" in page and "/* Documents, over the page" in page


def test_the_view_script_is_in_the_policy() -> None:
    from caixa import web

    assert [name for name, *_ in web.PAGE_SCRIPTS][-1] == "documents-index.js"
    assert len(web.page_script_hashes()) == 5


def test_a_box_of_documents_alone_gets_an_index(tmp_path: Path, pdf_family: Any) -> None:
    from caixa import settings
    from caixa.collectors.pdfImport import PdfCollector

    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.ocr": False, "documents.enrich": False})
    source = tmp_path / "pdfs"
    source.mkdir()
    shutil.copyfile(pdf_family.root / "scan_00482.pdf", source / "scan_00482.pdf")
    PdfCollector().run(box, source, {"workers": 1}, lambda step: None)
    index = (box.root / "index.html").read_text(encoding="utf-8")
    assert f'href="{VIEW}"' in index and "Our box" in index


# --- Search in the window (ticket 20261124-18) ---------------------------------------------------


@needs_ocr
def test_the_search_form_waits_for_caixa(viewed: Box) -> None:
    page = _view(viewed)
    form = re.search(r'<form class="search" hidden[^>]*>.*?</form>', page, re.S)
    assert form, "the search form is drawn, hidden"
    assert 'aria-label="Search every page"' in form.group(0)
    types = re.findall(r'<option value="(\w+)">', form.group(0))
    assert {"statement", "bill", "invoice"} <= set(types) and "spaceship" not in types
    assert 'class="hits"' in page and "documents.search" in page
