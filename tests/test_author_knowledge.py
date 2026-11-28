"""What the owner teaches Caixa about authors (20261127-02). Synthetic names only."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pymupdf

from caixa import settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import author_knowledge, authors, records
from caixa.documents.corrections import correct


def test_a_missing_file_is_empty(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    found = author_knowledge.load(box)
    assert found.accepted == [] and found.rejected == [] and found.instead == []


def test_the_file_keeps_accepted_rejected_and_instead_and_is_owner_only(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    known = author_knowledge.Knowledge(
        accepted=["PG&E", "T-Mobile"],
        rejected=["City of Springfield", "null"],
        instead=[{"said": "Anthony D. Knight", "use": "T-Mobile", "kind": "bill"}],
    )
    author_knowledge.save(box, known)
    path = box.caixa_dir / "author-knowledge.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text()) == {
        "accepted": ["PG&E", "T-Mobile"],
        "rejected": ["City of Springfield", "null"],
        "instead": [{"said": "Anthony D. Knight", "use": "T-Mobile", "kind": "bill"}],
    }
    assert "page" not in path.read_text()
    again = author_knowledge.load(box)
    assert again.accepted == known.accepted
    assert again.rejected == known.rejected
    assert again.instead == known.instead


def test_the_owner_is_never_rejected(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    known = author_knowledge.Knowledge()
    author_knowledge.learn_correction(
        known, said="Maria Costa", use="PG&E", kind="bill", owner="Maria Costa"
    )
    assert "Maria Costa" not in known.rejected
    assert "PG&E" in known.accepted
    assert known.instead == [{"said": "Maria Costa", "use": "PG&E", "kind": "bill"}]
    author_knowledge.save(box, known)
    os.chmod(box.caixa_dir / "author-knowledge.json", 0o600)


def _box_with_a_bill(tmp_path: Path) -> tuple[Box, str]:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Amount due")
    doc.save(folder / "bill.pdf")
    doc.close()
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.ocr": False, "documents.enrich": False})
    with box.master() as master:
        master.add_person("Maria Costa", is_owner=True)
    PdfCollector().run(box, folder, {"workers": 1}, lambda step: None)
    with box.master() as master:
        item = records.list_documents(master)[0]["item_id"]
    return box, item


def test_correcting_one_document_records_the_kind(tmp_path: Path) -> None:
    box, item = _box_with_a_bill(tmp_path)
    with box.master() as master:
        records.add_field(master, item, "author", "City of Springfield", "ai_inference")
        correct(box, master, item, author="PG&E", type="bill")
    known = author_knowledge.load(box)
    assert "PG&E" in known.accepted
    assert "City of Springfield" in known.rejected
    assert {"said": "City of Springfield", "use": "PG&E", "kind": "bill"} in known.instead


def test_correcting_away_from_the_owner_does_not_reject_the_owner(tmp_path: Path) -> None:
    box, item = _box_with_a_bill(tmp_path)
    with box.master() as master:
        records.add_field(master, item, "author", "Maria Costa", "ai_inference")
        correct(box, master, item, author="PG&E", type="bill")
    known = author_knowledge.load(box)
    assert "Maria Costa" not in known.rejected
    assert {"said": "Maria Costa", "use": "PG&E", "kind": "bill"} in known.instead


def test_renaming_and_merging_apply_to_every_kind(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    with box.master() as master:
        master.add_person("Maria Costa", is_owner=True)
        first = records.author_id(master, "PG & E")
        authors.rename(box, master, first, "PG&E")
        second = records.author_id(master, "Pacific Gas")
        kept = records.author_id(master, "PG&E")
        authors.merge(box, master, second, kept)
    known = author_knowledge.load(box)
    assert "PG&E" in known.accepted
    assert {"said": "PG & E", "use": "PG&E"} in known.instead
    assert {"said": "Pacific Gas", "use": "PG&E"} in known.instead
    assert "PG & E" not in known.rejected and "Pacific Gas" not in known.rejected
