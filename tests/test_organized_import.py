"""Organized file names in the PDF import (ticket 20261128-05, D31 and D30): the `organized` option
keeps the owner's names through filing, reading, reading again and corrections."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from caixa import settings
from caixa.box import Box
from caixa.collectors.pdfImport import PdfCollector
from caixa.documents import author_knowledge, records
from organized_family import OrganizedFamily, build_organized

PDF = "Documents/PDF"


@pytest.fixture
def organized(tmp_path: Path) -> OrganizedFamily:
    return build_organized(tmp_path / "organized")


def _import(family: OrganizedFamily, tmp_path: Path, organized: bool = True, **more: Any) -> Box:
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {"documents.ocr": False, "documents.enrich": False, **more})
    options = {"workers": 1, **({"organized": True} if organized else {})}
    PdfCollector().run(box, family.root, options, lambda step: None)
    return box


def _documents(box: Box) -> dict[str, dict[str, Any]]:
    with box.master() as master:
        return {
            d["original_filename"]: records.get_document(master, d["item_id"])
            for d in records.list_documents(master)
        }


def _organized_field(document: dict[str, Any]) -> list[str]:
    return [f["value"] for f in document["fields"] if f["field"] == "organized"]


# --- The option and filing at import (T01) --------------------------------------------------------


def test_the_option_is_declared() -> None:
    option = PdfCollector().info.options_schema["properties"]["organized"]
    assert option["type"] == "boolean" and option.get("default") is False
    assert "(date) Subject (Author) [Tag]" in option["title"]


@pytest.mark.parametrize(
    ("name", "filed"),
    [
        ("(2024-03-12) Water bill (Águas do Vale) [Utilities].pdf", "2024/Águas do Vale"),
        ("(2024-03) Statement (Banco Atlântico) [Banking] [Joint].pdf", "2024/Banco Atlântico"),
        ("(2021-05-10) Insurance renewal (Seguradora Horizonte) [Insurance].pdf",
         "2021/Seguradora Horizonte"),  # no model here: nothing to contradict it
        ("(2024-02-30) Electricity bill (Energia do Norte) [Utilities].pdf", "Unrecognized"),
        ("(2023-11-05) Letter from João [Family].pdf", "Unrecognized"),  # no author yet
    ],
)  # fmt: skip
def test_organized_names_are_kept_at_filing(
    organized: OrganizedFamily, tmp_path: Path, name: str, filed: str
) -> None:
    box = _import(organized, tmp_path)
    document = _documents(box)[name]
    assert document["file_path"] == f"{PDF}/{filed}/{name}"
    assert (box.root / document["file_path"]).is_file()
    assert _organized_field(document) == [name]


def test_the_owners_tags_are_caixas(organized: OrganizedFamily, tmp_path: Path) -> None:
    box = _import(organized, tmp_path)
    statement = _documents(box)["(2024-03) Statement (Banco Atlântico) [Banking] [Joint].pdf"]
    with box.master() as master:
        tags = master.connection.execute(
            "SELECT tag, source FROM document_tags WHERE item_id = ? ORDER BY tag",
            (statement["item_id"],),
        ).fetchall()
    assert [tuple(row) for row in tags] == [
        ("banking", "user_verified"),
        ("joint", "user_verified"),
    ]


def test_the_whitelist_learns_at_import(organized: OrganizedFamily, tmp_path: Path) -> None:
    box = _import(organized, tmp_path)
    known = author_knowledge.load(box)
    assert {"Águas do Vale", "Banco Atlântico", "Energia do Norte"} <= set(known.accepted)
    assert {"Utilities", "Banking", "Family"} <= set(known.tags)


def test_a_name_that_does_not_match_is_imported_as_before(
    organized: OrganizedFamily, tmp_path: Path
) -> None:
    scan = _documents(_import(organized, tmp_path))["scan_00482.pdf"]
    assert scan["file_path"] == f"{PDF}/Unrecognized/scan_00482.pdf" and not _organized_field(scan)


def test_without_the_option_organized_names_are_not_trusted(
    organized: OrganizedFamily, tmp_path: Path
) -> None:
    box = _import(organized, tmp_path, organized=False)
    water = _documents(box)["(2024-03-12) Water bill (Águas do Vale) [Utilities].pdf"]
    assert not _organized_field(water)
    assert not water["file_path"].startswith(f"{PDF}/2024/Águas do Vale/(2024-03-12) Water bill (")
    assert author_knowledge.load(box).tags == []


# --- Reading keeps the name (T02) -----------------------------------------------------------------

from organized_family import FIXTURES, respond  # noqa: E402
from stub_server import StubServer  # noqa: E402


@pytest.fixture
def read_box(organized: OrganizedFamily, tmp_path: Path):
    server = StubServer()
    server.respond = respond
    box = _import(organized, tmp_path, **{
        "documents.enrich": True, "summaries.provider": "endpoint",
        "summaries.endpoint": server.endpoint, "summaries.model": "stand-in",
    })  # fmt: skip
    yield box
    server.close()


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
def test_each_name_ends_where_its_known_answer_says(read_box: Box, fixture: Any) -> None:
    document = _documents(read_box)[fixture.name]
    assert document["file_path"] == f"{PDF}/{fixture.filed}", document["review"]


def test_the_model_adds_its_facts_beside_the_owners(read_box: Box) -> None:
    water = _documents(read_box)["(2024-03-12) Water bill (Águas do Vale) [Utilities].pdf"]
    assert (water["type"], water["category"]) == ("bill", "financial")
    assert water["title"] == "Water bill" and water["author"] == "Águas do Vale"
    assert water["summary"]
    with read_box.master() as master:
        tags = dict(master.connection.execute(
            "SELECT tag, source FROM document_tags WHERE item_id = ?", (water["item_id"],)
        ).fetchall())  # fmt: skip
    assert tags == {"utilities": "user_verified", "model tag": "ai_inference"}


def test_reading_again_keeps_every_name(read_box: Box) -> None:
    from caixa.documents.enrich import enrich_documents

    before = {name: d["file_path"] for name, d in _documents(read_box).items()}
    enrich_documents(read_box, every=True)
    assert {name: d["file_path"] for name, d in _documents(read_box).items()} == before


@pytest.mark.parametrize(
    ("change", "filed"),
    [
        ({"title": "Water invoice"},
         "2024/Águas do Vale/(2024-03-12) Water invoice (Águas do Vale) [Utilities].pdf"),
        ({"author": "AdV"}, "2024/AdV/(2024-03-12) Water bill (AdV) [Utilities].pdf"),
        ({"date": "2024-03-13"},
         "2024/Águas do Vale/(2024-03-13) Water bill (Águas do Vale) [Utilities].pdf"),
    ],
)  # fmt: skip
def test_a_correction_rewrites_that_part_of_the_name(
    read_box: Box, change: dict[str, str], filed: str
) -> None:
    from caixa.documents.corrections import correct

    water = _documents(read_box)["(2024-03-12) Water bill (Águas do Vale) [Utilities].pdf"]
    with read_box.master() as master:
        correct(read_box, master, water["item_id"], **change)
    assert _documents(read_box)[water["original_filename"]]["file_path"] == f"{PDF}/{filed}"


def test_a_name_with_no_author_takes_the_models_and_a_correction_names_it(read_box: Box) -> None:
    from caixa.documents.corrections import correct

    letter = _documents(read_box)["(2023-11-05) Letter from João [Family].pdf"]
    assert (
        letter["file_path"] == f"{PDF}/2023/João Costa/(2023-11-05) Letter from João [Family].pdf"
    )
    with read_box.master() as master:
        correct(read_box, master, letter["item_id"], author="João Costa")
    moved = _documents(read_box)[letter["original_filename"]]["file_path"]
    assert moved == f"{PDF}/2023/João Costa/(2023-11-05) Letter from João (João Costa) [Family].pdf"
