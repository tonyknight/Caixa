"""caixa documents prepare: the PDF import's dry run (ticket 20261128-06, D31; D28 and D30 as
amended). It runs the import itself, for Apple Intelligence and the local model, in throwaway boxes,
and writes `(YYYY-MM-DD) PDF Import Preview.json` at the box's root. Synthetic files and stand-in
models only."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterator

import pymupdf
import pytest

from caixa import settings
from caixa.box import Box
from caixa.documents import prepare
from caixa.documents.pdf import ocr
from organized_family import FIXTURES, OrganizedFamily, build_organized
from organized_family import respond as organized_respond
from pdf_family import PdfFamily
from stand_in_documents import DocumentModel
from stub_server import StubServer

STATEMENT = "2024-11 Banco Atlântico Checking Statement.pdf"


@pytest.fixture
def servers() -> Iterator[tuple[StubServer, StubServer]]:
    made = (StubServer(), StubServer())
    yield made
    for server in made:
        server.close()


def _endpoint(server: StubServer) -> dict[str, Any]:
    return {"summaries.provider": "endpoint", "summaries.endpoint": server.endpoint,
            "summaries.model": "stand-in"}  # fmt: skip


def _models(servers: tuple[StubServer, StubServer]) -> dict[str, Any]:
    return {"apple": _endpoint(servers[0]), "local": _endpoint(servers[1])}


@pytest.fixture
def box(tmp_path: Path) -> Box:
    made = Box.create(tmp_path / "Box", name="Our box")
    settings.save(made, {"documents.ocr": False})
    return made


@pytest.fixture
def throwaway(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Where the throwaway boxes go, so a test can see they are gone."""
    folder = tmp_path / "tmp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


def _folder(tmp_path: Path, pdf_family: PdfFamily, *names: str) -> Path:
    folder = tmp_path / "pdfs"
    folder.mkdir(exist_ok=True)
    for name in names:
        shutil.copyfile(pdf_family.root / name, folder / name)
    return folder


def _files(box: Box) -> dict[str, bytes]:
    return {
        str(path.relative_to(box.root)): path.read_bytes()
        for path in sorted(box.root.rglob("*"))
        if path.is_file()
        and "PDF Import Preview" not in path.name
        and not path.name.endswith(("-wal", "-shm"))  # SQLite's own, as any reader makes them
    }


def _record(run: prepare.Prepared, name: str) -> dict[str, Any]:
    return next(f for f in run.preview["report"]["files"] if f["from"] == name)


def _author_said(model: DocumentModel, author: dict[str, Any] | None) -> Callable:
    def respond(request: dict[str, Any]) -> dict[str, Any]:
        reply = model.respond(request)
        content = json.loads(reply["choices"][0]["message"]["content"])
        if "type" in content and "author" in content:
            content["author"] = author
        return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}

    return respond


# --- The dry run, through the import (T01) --------------------------------------------------------


def test_the_sources_and_the_box_are_unchanged_and_nothing_is_left(
    pdf_family: PdfFamily, box: Box, tmp_path: Path, servers: Any, throwaway: Path
) -> None:
    for server in servers:
        server.respond = DocumentModel(pdf_family).respond
    folder = _folder(tmp_path, pdf_family, STATEMENT)
    source = (folder / STATEMENT).read_bytes()
    before = _files(box)
    prepare.prepare(folder, box.root, models=_models(servers))
    assert (folder / STATEMENT).read_bytes() == source
    assert sorted(p.name for p in folder.iterdir()) == [STATEMENT]  # no .caixa beside them
    assert _files(box) == before
    assert list(throwaway.iterdir()) == []


def test_two_models_that_disagree_give_two_places(
    pdf_family: PdfFamily, box: Box, tmp_path: Path, servers: Any
) -> None:
    servers[0].respond = DocumentModel(pdf_family).respond
    servers[1].respond = _author_said(
        DocumentModel(pdf_family), {"name": "Maria Costa", "evidence": "Maria Costa", "page": 1}
    )
    run = prepare.prepare(
        _folder(tmp_path, pdf_family, STATEMENT), box.root, models=_models(servers)
    )
    record = _record(run, STATEMENT)
    assert record["outcome"] == "different"
    assert record["apple"]["place"].startswith("Documents/PDF/2024/Banco Atlântico/")
    assert record["local"]["place"].startswith("Documents/PDF/2024/Maria Costa/")


def test_two_models_that_agree_give_one_place(
    pdf_family: PdfFamily, box: Box, tmp_path: Path, servers: Any
) -> None:
    for server in servers:
        server.respond = DocumentModel(pdf_family).respond
    run = prepare.prepare(
        _folder(tmp_path, pdf_family, STATEMENT), box.root, models=_models(servers)
    )
    record = _record(run, STATEMENT)
    assert record["outcome"] == "same" and record["apple"]["place"] == record["local"]["place"]


def test_a_model_that_cannot_run_is_not_run(
    pdf_family: PdfFamily, box: Box, tmp_path: Path, servers: Any
) -> None:
    servers[1].respond = DocumentModel(pdf_family).respond
    run = prepare.prepare(_folder(tmp_path, pdf_family, STATEMENT), box.root,
                          models={"apple": None, "local": _endpoint(servers[1])})  # fmt: skip
    assert run.preview["apple"] is None and run.preview["report"]["apple"]["state"] == "not run"
    assert run.preview["report"]["local"]["state"] == "ran"
    assert _record(run, STATEMENT)["apple"] is None


def test_a_file_already_in_the_box_is_shown_where_it_is(
    pdf_family: PdfFamily, box: Box, tmp_path: Path, servers: Any
) -> None:
    from caixa.collectors.pdfImport import PdfCollector
    from caixa.documents import records

    for server in servers:
        server.respond = DocumentModel(pdf_family).respond
    settings.save(box, _endpoint(servers[0]))
    folder = _folder(tmp_path, pdf_family, STATEMENT)
    PdfCollector().run(box, folder, {"workers": 1}, lambda step: None)
    with box.master() as master:
        (filed,) = [d["file_path"] for d in records.list_documents(master)]
    record = _record(prepare.prepare(folder, box.root, models=_models(servers)), STATEMENT)
    assert record["apple"] == {"place": filed, "why": "already in the box", "look": None}


@pytest.fixture
def organized(tmp_path: Path) -> OrganizedFamily:
    return build_organized(tmp_path / "organized")


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.name for f in FIXTURES])
def test_each_organized_name_is_where_its_known_answer_says(
    organized: OrganizedFamily, box: Box, servers: Any, fixture: Any
) -> None:
    for server in servers:
        server.respond = organized_respond
    run = prepare.prepare(organized.root, box.root, organized=True, models=_models(servers))
    record = _record(run, fixture.name)
    for label in ("apple", "local"):
        assert record[label]["place"] == f"Documents/PDF/{fixture.filed}", label
        assert record[label]["name"] == (
            fixture.outcome if fixture.outcome != "no author" else "no author"
        )


def test_the_imports_preprocessing_is_reported(
    pdf_family: PdfFamily, box: Box, tmp_path: Path, servers: Any
) -> None:
    folder = _folder(tmp_path, pdf_family, STATEMENT)
    fax = pymupdf.open()
    fax.new_page().insert_text((72, 72), "FAX COVER SHEET")
    fax.new_page().insert_text(
        (72, 72), "Banco Atlântico, a letter of more than forty letters long"
    )
    fax.save(folder / "Fax.pdf")
    fax.close()
    model = DocumentModel(pdf_family)

    def first_without_author(request: dict[str, Any]) -> dict[str, Any]:
        asked = next(m["content"] for m in request["messages"] if m["role"] == "user")
        if "Second look" in asked:
            return model.respond(request)
        return _author_said(model, None)(request)

    servers[0].respond = first_without_author
    servers[1].respond = model.respond
    run = prepare.prepare(folder, box.root, models=_models(servers))
    assert _record(run, "Fax.pdf")["cover"] is True
    statement = _record(run, STATEMENT)
    assert statement["cover"] is False
    assert statement["apple"]["look"] == "bottom" and statement["local"]["look"] == "first"


def test_a_scanned_page_is_reported_as_read_by_ocr(
    pdf_family: PdfFamily, box: Box, tmp_path: Path, servers: Any
) -> None:
    if not ocr.tools().ready:
        pytest.skip("OCR tools missing here")
    settings.save(box, {"documents.ocr": True})
    for server in servers:
        server.respond = DocumentModel(pdf_family).respond
    run = prepare.prepare(_folder(tmp_path, pdf_family, "scan_00482.pdf"), box.root,
                          models=_models(servers))  # fmt: skip
    assert _record(run, "scan_00482.pdf")["ocr_pages"] == [1]
