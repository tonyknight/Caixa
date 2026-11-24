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
