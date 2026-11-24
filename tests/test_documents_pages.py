"""The document pages (ticket 20261124-16): one page of cards per year and author, and one for the
documents waiting in Unrecognized, drawn by Caixa with its own templates on Chattr's base."""

from __future__ import annotations

import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote

import pytest

from caixa import settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import records
from caixa.documents.pages import draw_documents
from caixa.documents.pdf import ocr
from pdf_family import PdfFamily

pytestmark = pytest.mark.skipif(not ocr.tools().ready, reason="OCR tools missing here")

STATEMENT_PAGE = "Documents/PDF/2024/Banco Atlântico/Banco Atlântico.html"
UNRECOGNIZED_PAGE = "Documents/PDF/Unrecognized/Unrecognized.html"


@pytest.fixture(scope="module")
def stand_in(pdf_family: PdfFamily) -> Iterator[Any]:
    from stand_in_documents import DocumentModel
    from stub_server import StubServer

    server = StubServer()
    server.model = DocumentModel(pdf_family)  # type: ignore[attr-defined]
    server.respond = server.model.respond  # type: ignore[attr-defined]
    yield server
    server.close()


def _make(base: Path, pdf_family: PdfFamily, stand_in: Any) -> Box:
    source = base / "pdfs"
    shutil.copytree(pdf_family.root, source)
    box = Box.create(base / "Box", name="Our box")
    settings.save(
        box,
        {
            "summaries.provider": "endpoint",
            "summaries.endpoint": stand_in.endpoint,
            "summaries.model": "stand-in-documents",
        },
    )
    PdfCollector().run(box, source, {"workers": 2}, lambda step: None)
    return box


@pytest.fixture(scope="module")
def box(pdf_family: PdfFamily, stand_in: Any, tmp_path_factory: pytest.TempPathFactory) -> Box:
    made = _make(tmp_path_factory.mktemp("pages"), pdf_family, stand_in)
    draw_documents(made)
    return made


@pytest.fixture
def own_box(pdf_family: PdfFamily, stand_in: Any, tmp_path: Path) -> Box:
    made = _make(tmp_path, pdf_family, stand_in)
    draw_documents(made)
    return made


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.opens: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = dict(attrs)
        if tag == "a" and "open-document" in (found.get("class") or ""):
            self.opens.append({k: v or "" for k, v in found.items()})


def _page(box: Box, relative: str) -> str:
    return (box.root / relative).read_text(encoding="utf-8")


def test_an_author_page_has_a_card_for_each_document(box: Box) -> None:
    page = _page(box, STATEMENT_PAGE)
    assert "<title>Banco Atlântico, 2024</title>" in page
    assert page.count('class="card"') == 3  # November, March and the statement downloaded again
    for words in (
        "Checking Statement", "30 November 2024", "Banco Atlântico", "Statement", "Financial",
        "(2024-11-30) Checking Statement - Banco Atlântico.pdf",
        "2024-11 Banco Atlântico Checking Statement.pdf", "statement", "family papers",
        "Summary by stand-in-documents",
    ):  # fmt: skip
        assert words in page, words


def test_cards_are_in_date_order(box: Box) -> None:
    page = _page(box, STATEMENT_PAGE)
    dates = re.findall(r'<time[^>]*datetime="([\d-]+)"', page)
    assert dates == sorted(dates) and len(dates) == 3


def test_statuses_are_said_in_words(box: Box) -> None:
    page = _page(box, STATEMENT_PAGE)
    assert "Probably the same as another document" in page  # the statement downloaded twice
    march = _page(box, "Documents/PDF/2024/Banco Atlântico/Banco Atlântico.html")
    assert "Text read by OCR" in march  # the March statement, whose text was broken


def test_the_unrecognized_page_lists_what_waits(box: Box) -> None:
    page = _page(box, UNRECOGNIZED_PAGE)
    assert "2022 Car Insurance.pdf" in page and "old_ocr_contract.pdf" in page
    assert "The file name says another year" in page and "No author" in page
    assert "2024-11 Banco Atlântico" not in page


def test_open_links_are_relative_and_reach_their_pdf(box: Box) -> None:
    for relative in (STATEMENT_PAGE, UNRECOGNIZED_PAGE):
        links = _Links()
        links.feed(_page(box, relative))
        assert links.opens, relative
        folder = (box.root / relative).parent
        for link in links.opens:
            assert not link["href"].startswith(("/", "http"))
            target = folder / unquote(link["href"].split("#", 1)[0])
            assert target.is_file() and target.suffix == ".pdf", link["href"]
            assert link["data-title"]


def test_the_page_carries_the_overlay_and_reads_without_it(box: Box) -> None:
    page = _page(box, STATEMENT_PAGE)
    assert "/* Documents, over the page" in page and ".document-overlay" in page
    assert re.search(r'<a class="home-button" href="\.\./\.\./\.\./\.\./index\.html"', page)


def test_drawing_again_writes_nothing(box: Box) -> None:
    page = box.root / STATEMENT_PAGE
    before = page.stat().st_mtime_ns
    drawn = draw_documents(box)
    assert drawn.written == [] and drawn.removed == []
    assert page.stat().st_mtime_ns == before


def test_renaming_an_author_moves_its_page(own_box: Box) -> None:
    from caixa.documents import authors

    with own_box.master() as master:
        banco = records.find_author(master, "Banco Atlântico")
        authors.rename(own_box, master, banco, "Banco Atlântico Português")
    drawn = draw_documents(own_box)
    assert STATEMENT_PAGE in drawn.removed
    assert (
        own_box.root / "Documents/PDF/2024/Banco Atlântico Português/Banco Atlântico Português.html"
    ).is_file()
    assert not (own_box.root / STATEMENT_PAGE).exists()


def test_reset_takes_the_pages(own_box: Box) -> None:
    from caixa.reset import reset_box

    reset_box(own_box)
    assert not (own_box.root / "Documents").exists() or not any(
        (own_box.root / "Documents").rglob("*.html")
    )


def test_chattrs_templates_know_nothing_of_documents() -> None:
    import chattr

    templates = Path(chattr.__file__).resolve().parent / "templates"
    for template in templates.glob("*.html"):
        assert "open-document" not in template.read_text(encoding="utf-8"), template.name


# --- Drawn when documents change (T02) -----------------------------------------------------------


def test_an_import_draws_the_pages(own_box: Box) -> None:
    (own_box.root / STATEMENT_PAGE).unlink()
    drawn = draw_documents(own_box)
    assert (
        STATEMENT_PAGE in drawn.written
    )  # (the import itself drew it: drawing again puts it back)


def test_the_import_itself_drew_them(pdf_family: PdfFamily, stand_in: Any, tmp_path: Path) -> None:
    made = _make(tmp_path, pdf_family, stand_in)  # no draw_documents here
    assert (made.root / STATEMENT_PAGE).is_file() and (made.root / UNRECOGNIZED_PAGE).is_file()


@pytest.fixture
def service(own_box: Box) -> Iterator[Any]:
    from caixa.service import Service

    made = Service(roots=[own_box.root.parent])
    made.box_open(str(own_box.root))
    yield made
    made.close()


def test_a_rename_through_the_service_redraws(service: Any, own_box: Box) -> None:
    listed = service.call("documents.authors", {})["authors"]
    banco = next(a["id"] for a in listed if a["name"] == "Banco Atlântico")
    service.call("documents.authors.rename", {"author_id": banco, "name": "Banco do Atlântico"})
    assert (
        own_box.root / "Documents/PDF/2024/Banco do Atlântico/Banco do Atlântico.html"
    ).is_file()
    assert not (own_box.root / STATEMENT_PAGE).exists()


def test_a_tag_shows_on_its_card(service: Any, own_box: Box) -> None:
    with own_box.master() as master:
        statement = next(
            d for d in records.list_documents(master)
            if d["original_filename"] == "2024-11 Banco Atlântico Checking Statement.pdf"
        )  # fmt: skip
    service.call("documents.tags", {"item_id": statement["item_id"], "add": ["checking account"]})
    assert "checking account" in _page(own_box, STATEMENT_PAGE)


def test_update_the_pages_draws_them_again(service: Any, own_box: Box) -> None:
    (own_box.root / UNRECOGNIZED_PAGE).unlink()
    job = service._refresh_job("pages")  # what Update the pages starts when changes wait
    done = service.wait(job["id"], 300)
    assert done["status"] == "done", done["error"]
    assert (own_box.root / UNRECOGNIZED_PAGE).is_file()
