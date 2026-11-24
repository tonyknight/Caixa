"""The master's record of documents (ticket 20261124-03): `caixa.documents.records`, the
`documents.list`/`documents.get` methods and `caixa documents list|show`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pytest

from caixa import cli, undo
from caixa.box import Box
from caixa.documents import records
from caixa.documents.records import DocumentRecord, PageText
from caixa.master import Master
from caixa.service import Service, ServiceError

SHA = "a" * 64


def _record(**changes: object) -> DocumentRecord:
    values: dict[str, object] = dict(
        format="pdf",
        original_filename="2024-11 Banco Atlântico Checking Statement.pdf",
        source_sha256=SHA,
        size=1234,
        file_path="Documents/PDF/2024/Banco Atlântico/(2024-11-30) Checking Statement - "
        "Banco Atlântico.pdf",
        archived_sha256=SHA,
        pages=2,
        title="Checking Statement",
        author="Banco Atlântico",
        type="statement",
        category="financial",
        date="2024-11-30",
        date_precision="day",
        date_kind="statement_end",
    )
    values.update(changes)
    return DocumentRecord(**values)  # type: ignore[arg-type]


@pytest.fixture
def master(tmp_path: Path) -> Iterator[Master]:
    with Master(tmp_path / "caixa.sqlite") as opened:
        yield opened


def test_an_item_id_names_the_format_and_the_source(master: Master) -> None:
    assert records.item_id_for("pdf", SHA) == f"pdf:{SHA}"


def test_a_new_document_is_inserted_with_its_item(master: Master) -> None:
    item_id, outcome = records.save_document(master, _record(), import_id=None)
    assert outcome == "inserted" and item_id == f"pdf:{SHA}"
    row = master.connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    assert row["type"] == "document" and row["collector"] == "pdf"
    assert row["timestamp_utc"].startswith("2024-11-30T00:00:00") and row["time_precision"] == "day"
    assert row["file_path"].endswith("Banco Atlântico.pdf") and row["content_hash"] == SHA
    assert [c.operation for c in master.changes()] == ["insert"]


def test_saving_the_same_again_changes_nothing(master: Master) -> None:
    records.save_document(master, _record(), import_id=None)
    assert records.save_document(master, _record(), import_id=None)[1] == "unchanged"
    assert len(master.changes()) == 1


def test_a_change_updates_and_raises_the_version(master: Master) -> None:
    item_id, _ = records.save_document(master, _record(), import_id=None)
    _, outcome = records.save_document(master, _record(title="Statement of Account"), None)
    assert outcome == "updated"
    row = master.connection.execute("SELECT version FROM items WHERE id = ?", (item_id,)).fetchone()
    assert row[0] == 2 and [c.operation for c in master.changes()] == ["insert", "update"]
    assert records.get_document(master, item_id)["title"] == "Statement of Account"


@pytest.mark.parametrize(
    ("date", "precision", "stamp"),
    [("2024-11", "month", "2024-11-01T00:00:00"), ("2022", "year", "2022-01-01T00:00:00")],
)
def test_a_partial_date_is_stored_at_its_precision(
    master: Master, date: str, precision: str, stamp: str
) -> None:
    item_id, _ = records.save_document(master, _record(date=date, date_precision=precision), None)
    row = master.connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    assert row["timestamp_utc"].startswith(stamp) and row["time_precision"] == precision


def test_an_undated_document_has_no_time(master: Master) -> None:
    item_id, _ = records.save_document(
        master, _record(date=None, date_precision=None, author=None), None
    )
    row = master.connection.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    assert row["timestamp_utc"] == "" and row["time_precision"] == "unknown"
    assert records.get_document(master, item_id)["author"] is None


def test_a_source_is_recorded_once_per_place(master: Master) -> None:
    item_id, _ = records.save_document(master, _record(), None)
    assert records.add_source(master, item_id, "/in/a.pdf", 1234, "2024-12-01T10:00:00", None)
    assert not records.add_source(master, item_id, "/in/a.pdf", 1234, "2024-12-01T10:00:00", None)
    assert records.add_source(master, item_id, "/other/copy.pdf", 1234, None, None)
    sources = records.get_document(master, item_id)["sources"]
    assert [s["filename"] for s in sources] == ["a.pdf", "copy.pdf"]
    assert records.find_by_source(master, SHA) == item_id
    assert records.find_by_source(master, "b" * 64) is None


def test_pages_are_replaced_and_searchable(master: Master) -> None:
    item_id, _ = records.save_document(master, _record(), None)
    records.set_pages(master, item_id, [PageText(1, "Conta 4821", "pdf", "text")])
    records.set_pages(
        master,
        item_id,
        [PageText(1, "Banco Atlântico conta 4821", "pdf", "text"), PageText(2, "77812", "ocr")],
    )
    pages = master.connection.execute(
        "SELECT page, source, class FROM document_pages WHERE item_id = ? ORDER BY page",
        (item_id,),
    ).fetchall()
    assert [tuple(p) for p in pages] == [(1, "pdf", "text"), (2, "ocr", None)]
    hits = master.connection.execute(
        "SELECT COUNT(*) FROM documents_fts WHERE documents_fts MATCH 'atlantico'"
    ).fetchone()[0]
    assert hits == 1


def test_fields_keep_their_sources(master: Master) -> None:
    item_id, _ = records.save_document(master, _record(), None)
    run = records.add_run(master, item_id, "enrich", "ok", model="stand-in", provider="endpoint")
    records.add_field(master, item_id, "author", "Banco Atlântico", "original_filename")
    records.add_field(
        master, item_id, "author", "Banco Atlântico", "ai_inference",
        evidence="Banco Atlântico", page=1, run_id=run, state="applied",
    )  # fmt: skip
    records.add_field(master, item_id, "closing_balance", "1,987.20", "pdf_content", number=1987.2)
    fields = records.get_document(master, item_id)["fields"]
    author = [f for f in fields if f["field"] == "author"]
    assert {f["source"] for f in author} == {"original_filename", "ai_inference"}
    assert next(f for f in fields if f["field"] == "closing_balance")["number"] == 1987.2
    runs = records.get_document(master, item_id)["runs"]
    assert runs[0]["stage"] == "enrich" and runs[0]["model"] == "stand-in"


def test_tags_keep_who_gave_them(master: Master) -> None:
    item_id, _ = records.save_document(master, _record(), None)
    records.set_tags(master, item_id, ["Banking", "statement"], "ai_inference")
    records.set_tags(master, item_id, ["checking"], "user_verified")
    tags = records.get_document(master, item_id)["tags"]
    assert tags == [
        {"tag": "banking", "source": "ai_inference"},
        {"tag": "checking", "source": "user_verified"},
        {"tag": "statement", "source": "ai_inference"},
    ]
    names = {r[0] for r in master.connection.execute("SELECT name FROM tags")}
    assert "checking" in names  # a new tag joins the list


def test_setting_the_models_tags_again_keeps_the_owners(master: Master) -> None:
    item_id, _ = records.save_document(master, _record(), None)
    records.set_tags(master, item_id, ["checking"], "user_verified")
    records.set_tags(master, item_id, ["banking"], "ai_inference")
    records.set_tags(master, item_id, ["bill"], "ai_inference")
    tags = {t["tag"] for t in records.get_document(master, item_id)["tags"]}
    assert tags == {"checking", "bill"}


def test_authors_are_found_by_alias_without_accents_or_case(master: Master) -> None:
    first = records.author_id(master, "Banco Atlântico")
    assert records.author_id(master, "BANCO ATLANTICO") == first
    records.add_author_alias(master, first, "Banco Atlântico, S.A.")
    assert records.author_id(master, "banco atlântico, s.a.") == first
    assert records.find_author(master, "Energia do Norte") is None
    assert records.author_id(master, "Energia do Norte", kind="organization") != first


def test_listing_filters_documents(master: Master) -> None:
    records.save_document(master, _record(), None)
    records.save_document(
        master,
        _record(
            source_sha256="b" * 64, title="Electricity Bill", author="Energia do Norte",
            type="bill", date="2024-01-10", file_path="Documents/PDF/2024/x.pdf",
        ),
        None,
    )  # fmt: skip
    records.save_document(
        master,
        _record(
            source_sha256="c" * 64, title=None, author=None, type=None, date=None,
            date_precision=None, file_path="Documents/PDF/Unrecognized/scan.pdf",
            processing_status="needs_review",
        ),
        None,
    )  # fmt: skip
    every = records.list_documents(master)
    assert [d["title"] for d in every] == ["Electricity Bill", "Checking Statement", None]
    assert [d["title"] for d in records.list_documents(master, type="bill")] == ["Electricity Bill"]
    assert len(records.list_documents(master, author="Banco Atlântico")) == 1
    assert len(records.list_documents(master, year=2024)) == 2
    assert len(records.list_documents(master, status="needs_review")) == 1
    records.set_tags(master, f"pdf:{'b' * 64}", ["utilities"], "ai_inference")
    assert len(records.list_documents(master, tag="utilities")) == 1


def test_getting_a_document_that_is_not_there(master: Master) -> None:
    with pytest.raises(KeyError):
        records.get_document(master, "pdf:none")


# --- Service and command line ------------------------------------------------------------------


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Service]:
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Our box", owner="Maria Costa")
    with Box.open(tmp_path / "Box").master() as opened:
        records.save_document(opened, _record(), None)
    yield made
    made.close()


def test_the_service_lists_and_gets_documents(service: Service) -> None:
    listing = service.call("documents.list", {})
    assert [d["title"] for d in listing["documents"]] == ["Checking Statement"]
    found = service.call("documents.get", {"item_id": listing["documents"][0]["item_id"]})
    assert found["author"] == "Banco Atlântico" and found["sources"] == []
    with pytest.raises(ServiceError) as missing:
        service.call("documents.get", {"item_id": "pdf:none"})
    assert missing.value.kind == "not_found"


def test_the_commands_list_and_show(
    service: Service, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    box = str(tmp_path / "Box")
    assert cli.main(["documents", "list", "--box", box]) == 0
    out = capsys.readouterr().out
    assert "2024-11-30" in out and "Checking Statement" in out and "Banco Atlântico" in out
    assert cli.main(["documents", "list", "--box", box, "--json"]) == 0
    listing = json.loads(capsys.readouterr().out)
    item_id = listing["documents"][0]["item_id"]
    assert cli.main(["documents", "show", item_id, "--box", box, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["type"] == "statement"


def test_an_undo_snapshot_brings_document_rows_back(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    undo.begin(box, 1, "pdf", "/in")
    with box.master() as master:
        records.save_document(master, _record(), None)
    undo.finish(box, 1)
    undo.restore(box, 1)
    with box.master() as master:
        assert records.list_documents(master) == []
