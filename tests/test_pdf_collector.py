"""The PDF collector (ticket 20261124-04): finding, examining, previewing and importing PDFs.

The originals are never changed: every test that imports checks the sources' bytes and times.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa.box import Box
from caixa.collectors.base import Collector, Progress
from caixa.collectors.inputs import InputError
from caixa.collectors.pdfImport import PdfCollector, collectors, examine
from caixa.collectors.registry import discover
from caixa.documents import records
from pdf_family import PASSWORD, PdfFamily, zip_family

#: Every distinct PDF of the family that opens: 12 documents, the locked one, the restricted one
#: and the statement saved again (the exact copy in `Arquivo/2024/` is the same file).
READABLE = 15
UNREADABLE = {"damaged_scan.pdf", "not_really.pdf"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(folder: Path) -> dict[str, tuple[str, int]]:
    return {
        p.relative_to(folder).as_posix(): (_sha(p), p.stat().st_mtime_ns)
        for p in sorted(folder.rglob("*"))
        if p.is_file() and not p.name.endswith(("-wal", "-shm"))  # SQLite's own, even to read
    }


@pytest.fixture
def family(pdf_family: PdfFamily, tmp_path: Path) -> Path:
    """A private copy of the family, so imports can be checked against it."""
    copy = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, copy)
    (copy / "answers.json").unlink()
    return copy


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box.create(tmp_path / "Box", name="Our box")


def _quiet(step: Progress) -> None:
    pass


# --- Declaration, locating and examining (T01) -----------------------------------------------


def test_the_collector_is_registered() -> None:
    registry = discover()
    collector = registry.get("pdf")
    assert isinstance(collector, Collector) and isinstance(collector, PdfCollector)
    described = next(d for d in registry.describe() if d["id"] == "pdf")
    assert described["name"] == "PDF documents"
    assert set(described["inputs"]) == {"file", "folder", "zip"}
    assert "stay where they are" in described["how_to_export"]
    assert [c.info.id for c in collectors()] == ["pdf"]


def test_every_pdf_in_a_folder_is_found_with_its_subfolders(family: Path, box: Box) -> None:
    found = PdfCollector().locate(family, box.work_dir("documents"))
    names = {p.name for p in found}
    assert "statement copy.pdf" in names  # in Arquivo/2024/
    assert "notes.txt" not in names
    assert len(found) == READABLE + len(UNREADABLE) + 1  # and the exact copy


def test_pdfs_are_found_in_a_zip_and_as_one_file(family: Path, box: Box, tmp_path: Path) -> None:
    archive = zip_family(family, tmp_path / "pdfs.zip")
    from_zip = PdfCollector().locate(archive, box.work_dir("documents"))
    assert {p.name for p in from_zip} == {
        p.name for p in PdfCollector().locate(family, box.work_dir("documents"))
    }
    one = family / "scan_00482.pdf"
    assert PdfCollector().locate(one, box.work_dir("documents")) == [one]


def test_a_folder_without_pdfs_says_so(tmp_path: Path, box: Box) -> None:
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty" / "notes.txt").write_text("nothing here")
    with pytest.raises(InputError):
        PdfCollector().locate(tmp_path / "empty", box.work_dir("documents"))


def test_examining_a_pdf(family: Path) -> None:
    seen = examine(family / "2024-11 Banco Atlântico Checking Statement.pdf")
    assert seen.error is None and seen.pages == 2 and not seen.locked
    assert seen.sha256 == _sha(family / "2024-11 Banco Atlântico Checking Statement.pdf")
    assert (
        seen.properties["title"] == "Statement" and seen.properties["author"] == "Banco Atlântico"
    )


def test_examining_a_locked_pdf(family: Path) -> None:
    seen = examine(family / "extrato_protegido.pdf")
    assert seen.error is None and seen.locked and seen.pages == 1
    assert not examine(family / "apolice_restrita.pdf").locked  # an owner password only


@pytest.mark.parametrize("name", sorted(UNREADABLE))
def test_examining_a_file_that_is_not_a_usable_pdf(family: Path, name: str) -> None:
    seen = examine(family / name)
    assert seen.error and seen.pages is None


def test_a_preview_counts_and_writes_nothing(family: Path, box: Box) -> None:
    before = _snapshot(box.root)
    preview = PdfCollector().preview(family, {}, box)
    assert preview.items == READABLE  # each new document once (the exact copy is the same file)
    joined = "\n".join(preview.warnings)
    assert "1 locked with a password" in joined
    assert "damaged_scan.pdf" in joined and "not_really.pdf" in joined
    assert "1 copy of a file found twice" in joined
    assert _snapshot(box.root) == before


# --- Importing (T02) ---------------------------------------------------------------------------


def _documents(box: Box) -> list[dict[str, Any]]:
    with box.master() as master:
        return records.list_documents(master)


def test_an_import_archives_every_readable_pdf_byte_for_byte(family: Path, box: Box) -> None:
    before = _snapshot(family)
    result = PdfCollector().run(box, family, {}, _quiet)
    assert result.inserted == READABLE and result.unchanged == 1  # the exact copy
    assert _snapshot(family) == before  # the originals are untouched
    documents = _documents(box)
    assert len(documents) == READABLE
    for document in documents:
        archived = box.root / document["file_path"]
        assert archived.is_file()
        assert document["file_path"].startswith("Documents/PDF/")
        with box.master() as master:
            found = records.get_document(master, document["item_id"])
        assert _sha(archived) == found["archived_sha256"]
        if found["ocr_status"] in ("not_needed", "needs_ocr"):  # OCR did not change it
            assert found["archived_sha256"] == found["source_sha256"]
    names = {Path(d["file_path"]).name for d in documents}
    assert "scan_00482.pdf" in names and "Document1.pdf" in names  # kept their own names
    unrecognized = [d for d in documents if "/Unrecognized/" in d["file_path"]]
    assert len(unrecognized) == READABLE - 2  # the statement and the renewal were filed by name
    with sqlite3.connect(box.master_path) as db:
        (imports,) = db.execute("SELECT COUNT(*) FROM imports WHERE collector = 'pdf'").fetchone()
    assert imports == 1


def test_unreadable_files_are_named_and_left_alone(family: Path, box: Box) -> None:
    result = PdfCollector().run(box, family, {}, _quiet)
    joined = "\n".join(result.warnings)
    for name in UNREADABLE:
        assert name in joined
    archived = {p.name for p in (box.root / "Documents").rglob("*.pdf")}
    assert not archived & UNREADABLE


def test_a_locked_pdf_is_kept_and_waits_for_review(family: Path, box: Box) -> None:
    PdfCollector().run(box, family, {}, _quiet)
    locked = next(d for d in _documents(box) if d["original_filename"] == "extrato_protegido.pdf")
    assert locked["processing_status"] == "needs_review" and locked["review"] == ["locked"]
    import pymupdf

    with pymupdf.open(box.root / locked["file_path"]) as doc:
        assert doc.needs_pass and doc.authenticate(PASSWORD)


def test_importing_again_adds_only_new_places(family: Path, box: Box, tmp_path: Path) -> None:
    PdfCollector().run(box, family, {}, _quiet)
    files = _snapshot(box.root / "Documents")
    moved = tmp_path / "elsewhere"
    shutil.copytree(family, moved)
    again = PdfCollector().run(box, moved, {}, _quiet)
    assert again.inserted == 0 and again.unchanged == READABLE + 1
    assert _snapshot(box.root / "Documents") == files
    with box.master() as master:
        statement = records.find_by_source(
            master, _sha(family / "2024-11 Banco Atlântico Checking Statement.pdf")
        )
        assert statement is not None
        sources = records.get_document(master, statement)["sources"]
    assert len(sources) == 4  # two folders, each with the file and its exact copy


def test_a_different_file_with_a_name_already_used_gets_a_number(
    family: Path, box: Box, tmp_path: Path
) -> None:
    import pymupdf

    PdfCollector().run(box, family, {}, _quiet)
    other = tmp_path / "other"
    other.mkdir()
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Another document altogether")
    doc.save(other / "Document1.pdf")
    doc.close()
    PdfCollector().run(box, other, {}, _quiet)
    unrecognized = box.root / "Documents" / "PDF" / "Unrecognized"
    assert _sha(unrecognized / "Document1.pdf") == _sha(family / "Document1.pdf")
    assert _sha(unrecognized / "Document1 (2).pdf") == _sha(other / "Document1.pdf")


def test_one_and_four_workers_give_the_same_box(family: Path, tmp_path: Path) -> None:
    boxes = []
    for workers in (1, 4):
        box = Box.create(tmp_path / f"Box{workers}", name="Our box")
        PdfCollector().run(box, family, {"workers": workers}, _quiet)
        boxes.append(
            sorted((d["file_path"], d["original_filename"], d["pages"]) for d in _documents(box))
        )
    assert boxes[0] == boxes[1]


def test_placing_a_document_whose_date_and_author_are_known(box: Box) -> None:
    from caixa.documents.archive import Facts, place

    relative = place(
        box,
        "2024-11 Banco Atlântico Checking Statement.pdf",
        "a" * 64,
        Facts(date="2024-11-30", title="Checking Statement", author="Banco Atlântico"),
    )
    assert relative == (
        "Documents/PDF/2024/Banco Atlântico/(2024-11-30) Checking Statement - Banco Atlântico.pdf"
    )
    assert place(box, "scan.pdf", "a" * 64, Facts(date="2024", title="Scan")) == (
        "Documents/PDF/Unrecognized/scan.pdf"  # an author is needed too
    )
    assert place(box, "scan.pdf", "a" * 64, None) == "Documents/PDF/Unrecognized/scan.pdf"


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Any]:
    from caixa.service import Service

    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Our box", owner="Maria Costa")
    yield made
    made.close()


def test_undo_takes_the_documents_out_again(service: Any, family: Path, tmp_path: Path) -> None:
    job = service.import_start("pdf", str(family))
    done = service.wait(job["id"], 120)
    assert done["status"] == "done", done["error"]
    assert done["result"]["inserted"] == READABLE
    documents = tmp_path / "Box" / "Documents"
    assert any(documents.rglob("*.pdf"))
    undone = service.wait(service.import_undo()["id"], 120)
    assert undone["status"] == "done", undone["error"]
    assert not any(documents.rglob("*.pdf"))
    assert service.call("documents.list", {})["documents"] == []


def test_reset_takes_the_documents_and_keeps_what_the_owner_added(family: Path, box: Box) -> None:
    from caixa.reset import reset_box

    PdfCollector().run(box, family, {}, _quiet)
    mine = box.root / "Documents" / "PDF" / "my own note.txt"
    mine.write_text("mine")
    result = reset_box(box)
    assert not any((box.root / "Documents").rglob("*.pdf"))
    assert mine.is_file() and "Documents/PDF/my own note.txt" in result.left


# --- Packages checked first (20261125-04) --------------------------------------------------------


@pytest.mark.parametrize("step", ["preview", "run"])
def test_a_missing_package_stops_the_import_before_any_file_is_read(
    step: str, family: Path, box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from caixa import requirements

    monkeypatch.setattr(requirements, "_found", lambda module: module != "numpy")

    def never(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a file was looked for before the packages were checked")

    monkeypatch.setattr(PdfCollector, "locate", never)
    collector = PdfCollector()
    with pytest.raises(InputError) as raised:
        if step == "preview":
            collector.preview(family, {}, box)
        else:
            collector.run(box, family, {}, _quiet)
    assert "numpy" in raised.value.summary
    assert f"{sys.executable} -m pip install numpy" in str(raised.value)


# --- One file or one stage cannot end the import (20261125-03) -----------------------------------


def _without_ocr(box: Box) -> Box:
    from caixa import settings

    settings.save(box, {"documents.ocr": False, "documents.enrich": False})
    return box


def test_a_file_that_breaks_examination_is_reported_and_the_rest_are_filed(
    family: Path, box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caixa.collectors import pdfImport

    real = pdfImport.inspect_pdf

    def inspect(doc: Any) -> Any:
        if Path(doc.name).name == "2022 Car Insurance.pdf":
            raise TypeError("an unexpected error")
        return real(doc)

    monkeypatch.setattr(pdfImport, "inspect_pdf", inspect)
    result = PdfCollector().run(_without_ocr(box), family, {"workers": 1}, _quiet)
    assert result.inserted == READABLE - 1
    warning = next(w for w in result.warnings if "2022 Car Insurance.pdf" in w)
    assert "could not be examined" in warning and "TypeError" in warning


@pytest.mark.parametrize("stage", ["enrich", "embed"])
def test_a_later_stage_that_fails_leaves_a_warning_and_the_pages_drawn(
    stage: str, family: Path, box: Box, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caixa.documents import embeddings, enrich

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("something unexpected")

    if stage == "enrich":
        monkeypatch.setattr(enrich, "enrich_documents", broken)
    else:
        monkeypatch.setattr(embeddings, "model_name", lambda values: "stand-in-embeddings")
        monkeypatch.setattr(embeddings, "embed_documents", broken)
    result = PdfCollector().run(_without_ocr(box), family, {"workers": 1}, _quiet)
    assert result.inserted == READABLE
    named = "Reading" if stage == "enrich" else "Embedding"
    warning = next(w for w in result.warnings if w.startswith(named))
    assert "RuntimeError" in warning and f"caixa documents {stage}" in warning
    assert result.pages > 0 and (box.root / "Documents" / "PDF" / "PDF.html").is_file()


# --- Identical files, and one filing error (20261128-08) ------------------------------------------


def _ocr_box(tmp_path: Path) -> Box:
    from caixa import settings

    made = Box.create(tmp_path / "OcrBox", name="Our box")
    settings.save(made, {"documents.enrich": False})
    return made


def test_two_copies_of_one_scan_import_as_one_document(
    pdf_family: PdfFamily, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caixa.documents.pdf import ocr, process

    if not ocr.tools().ready:
        pytest.skip("OCR tools missing here")
    source = tmp_path / "twice"
    source.mkdir()
    shutil.copyfile(pdf_family.root / "scan_00482.pdf", source / "scan_00482.pdf")
    shutil.copyfile(pdf_family.root / "scan_00482.pdf", source / "scan again.pdf")
    ocrd: list[str] = []
    real = process.ocr_and_validate

    def counting(path: Path, *args: Any, **kwargs: Any) -> Any:
        ocrd.append(Path(path).name)
        return real(path, *args, **kwargs)

    monkeypatch.setattr("caixa.collectors.pdfImport.ocr_and_validate", counting)
    box = _ocr_box(tmp_path)
    result = PdfCollector().run(box, source, {"workers": 1}, lambda step: None)
    assert result.inserted == 1 and result.unchanged == 1
    assert len(ocrd) == 1  # the second copy is not OCR'd again
    with box.master() as master:
        (document,) = records.list_documents(master)
        sources = master.connection.execute(
            "SELECT COUNT(*) FROM document_sources WHERE item_id = ?", (document["item_id"],)
        ).fetchone()[0]
    assert sources == 2 and document["ocr_status"] == "done"


def test_each_file_has_its_own_working_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caixa.documents.pdf import process

    outputs: list[Path] = []

    def remember(source: Path, output: Path, *args: Any) -> Any:
        outputs.append(output)
        from caixa.documents.pdf.ocr import OcrOutcome

        return OcrOutcome("not_needed")

    monkeypatch.setattr(process, "ocr_document", remember)
    for name in ("a.pdf", "b.pdf"):
        process.ocr_and_validate(tmp_path / name, "f" * 64, [], {"workdir": str(tmp_path)})
    assert len(set(outputs)) == 2 and all(o.name.startswith("f" * 64 + "-") for o in outputs)


def test_one_file_that_cannot_be_filed_does_not_stop_the_import(
    family: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caixa.documents import importing

    real = importing.copy_into

    def failing(box: Box, source: Path, relative: str, sha256: str) -> None:
        real(box, source, relative, sha256)
        if "scan_00482" in relative:
            raise OSError("The copy of scan_00482.pdf does not match it; nothing was filed.")

    monkeypatch.setattr(importing, "copy_into", failing)
    box = Box.create(tmp_path / "Box2", name="Our box")
    from caixa import settings

    settings.save(box, {"documents.ocr": False, "documents.enrich": False})
    result = PdfCollector().run(box, family, {"workers": 1}, lambda step: None)
    assert any("scan_00482.pdf: could not be filed (OSError" in w for w in result.warnings)
    with box.master() as master:
        names = {d["original_filename"] for d in records.list_documents(master)}
    assert "scan_00482.pdf" not in names and len(names) >= 10
    assert not list((box.root / "Documents").rglob("scan_00482*"))
