"""Reading documents with a model on this computer (ticket 20261124-10).

Only stand-ins are ever asked: Chattr's `StubServer` answering through `DocumentModel` (from the
PDF family's known answers), and `stand_in_apple.py` for Apple Intelligence.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterator

import pymupdf
import pytest

from caixa import settings
from caixa.box import Box
from caixa.documents import enrich
from caixa.documents.enrich import DocumentInput, EnrichUnavailable
from pdf_family import PdfFamily
from stand_in_documents import DocumentModel
from stub_server import StubServer

STAND_IN_APPLE = Path(__file__).with_name("stand_in_apple.py")


@pytest.fixture
def server(pdf_family: PdfFamily) -> Iterator[StubServer]:
    made = StubServer()
    model = DocumentModel(pdf_family)
    made.respond = model.respond
    made.model = model  # type: ignore[attr-defined]
    yield made
    made.close()


def _values(server: StubServer, **more: Any) -> dict[str, Any]:
    return {
        "summaries.provider": "endpoint",
        "summaries.endpoint": server.endpoint,
        "summaries.model": "stand-in-documents",
        "documents.enrich": True,
        **more,
    }


def _input(pdf_family: PdfFamily, name: str) -> DocumentInput:
    path = pdf_family.root / pdf_family.get(name).path
    with pymupdf.open(path) as doc:
        pages = [(i + 1, page.get_text()) for i, page in enumerate(doc)]
        properties = {k: v for k, v in (doc.metadata or {}).items() if isinstance(v, str) and v}
    return DocumentInput(name, properties, pages, len(pages), ["Banco Atlântico"])


# --- The provider --------------------------------------------------------------------------------


def test_an_endpoint_on_the_internet_is_refused_even_when_allowed() -> None:
    values = {
        "summaries.provider": "endpoint",
        "summaries.endpoint": "https://api.example.com/v1",
        "summaries.model": "big",
        "summaries.allow_remote": True,
        "documents.enrich": True,
    }
    with pytest.raises(EnrichUnavailable) as refused:
        enrich.provider(values)
    assert refused.value.reason == "remote"


def test_reading_can_be_turned_off(server: StubServer) -> None:
    with pytest.raises(EnrichUnavailable) as off:
        enrich.provider(_values(server, **{"documents.enrich": False}))
    assert off.value.reason == "off"


def test_without_a_model_there_is_nothing_to_ask() -> None:
    with pytest.raises(EnrichUnavailable) as missing:
        enrich.provider({"summaries.provider": "endpoint", "documents.enrich": True})
    assert missing.value.reason == "no_model"


def test_a_local_endpoint_is_used(server: StubServer) -> None:
    client, info = enrich.provider(_values(server))
    assert info["provider"] == "endpoint" and info["model"] == "stand-in-documents"
    assert info["budget"] == enrich.BUDGET


def test_apple_intelligence_first_under_automatic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAIXA_APPLE_INTELLIGENCE", f"{sys.executable} {STAND_IN_APPLE}")
    monkeypatch.setattr("caixa.apple_intelligence.available", lambda: True)
    client, info = enrich.provider({"summaries.provider": "auto", "documents.enrich": True})
    try:
        assert info["provider"] == "apple" and info["budget"] == enrich.APPLE_BUDGET
    finally:
        enrich.close(client)


# --- What is sent --------------------------------------------------------------------------------


def test_what_is_sent_holds_the_name_the_properties_and_the_pages(pdf_family: PdfFamily) -> None:
    sent = enrich.prepare(
        _input(pdf_family, "2024-11 Banco Atlântico Checking Statement.pdf"), 12_000
    )
    assert "File name: 2024-11 Banco Atlântico Checking Statement.pdf" in sent
    assert "date 2024-11 (month)" in sent and "type words: statement" in sent
    assert "author: Banco Atlântico" in sent  # from the properties
    assert "Authors already in the box named in the text: Banco Atlântico" in sent
    assert "--- Page 1 ---" in sent and "--- Page 2 (last) ---" in sent
    assert "Supermercado Sol" in sent


def test_a_long_document_is_cut_to_its_first_and_last_pages() -> None:
    pages = [(n, f"Page {n} words " * 400) for n in range(1, 11)]
    sent = enrich.prepare(DocumentInput("long.pdf", {}, pages, 10, []), 6_000)
    assert len(sent) <= 6_000
    assert (
        "--- Page 1 ---" in sent and "--- Page 2 ---" in sent and "--- Page 10 (last) ---" in sent
    )
    assert "--- Page 5" not in sent and "10 pages" in sent


def test_the_request_carries_the_schema(server: StubServer, pdf_family: PdfFamily) -> None:
    client, info = enrich.provider(_values(server))
    enrich.classify(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    sent = server.requests[0]["json"]
    schema = sent["response_format"]["json_schema"]["schema"]
    assert sent["response_format"]["type"] == "json_schema"
    assert {"type", "category", "title", "author", "date", "filename_conflicts"} <= set(
        schema["properties"]
    )
    assert "statement" in schema["properties"]["type"]["enum"]
    assert (
        sent["messages"][0]["role"] == "system"
        and "only what the document" in sent["messages"][0]["content"]
    )


# --- The answer ----------------------------------------------------------------------------------


def test_a_good_answer_with_evidence(server: StubServer, pdf_family: PdfFamily) -> None:
    client, info = enrich.provider(_values(server))
    found = enrich.classify(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    assert found.ok and found.attempts == 1
    answer = found.answer
    assert answer["type"] == "bill" and answer["category"] == "financial"
    assert answer["author"]["name"] == "Energia do Norte" and answer["author"]["verified"] is True
    assert answer["date"]["value"] == "2024-01-10" and answer["date"]["kind"] == "issue"
    assert answer["date"]["verified"] is True and answer["date"]["page"] == 1
    assert set(answer["filename_conflicts"]) == {"year", "type"}


def test_evidence_that_is_not_on_its_page_is_not_verified() -> None:
    pages = {1: "Banco Atlântico\nConta 4821", 2: "Saldo final 1.000,00"}
    assert enrich.verify_quote("banco atlantico", 1, pages) == (True, 1)
    assert enrich.verify_quote("Saldo final", 1, pages) == (False, 1)  # on page 2, not 1
    assert enrich.verify_quote("Saldo  final", None, pages) == (True, 2)  # any page, found on 2
    assert enrich.verify_quote("Banco Central", None, pages) == (False, None)
    assert enrich.verify_quote("", 1, pages) == (False, 1)


def test_an_answer_that_is_not_json_is_asked_again_once(
    server: StubServer, pdf_family: PdfFamily
) -> None:
    server.model.misbehave["2022 Car Insurance.pdf"] = "twice"  # type: ignore[attr-defined]
    client, info = enrich.provider(_values(server))
    found = enrich.classify(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    assert found.ok and found.attempts == 2
    retry = server.requests[1]["json"]["messages"][-1]["content"]
    assert retry.startswith("That answer") and "JSON" in retry


def test_an_answer_that_breaks_the_schema_twice_is_given_up(
    server: StubServer, pdf_family: PdfFamily
) -> None:
    server.model.misbehave["2022 Car Insurance.pdf"] = "schema"  # type: ignore[attr-defined]
    client, info = enrich.provider(_values(server))
    found = enrich.classify(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    assert not found.ok and found.attempts == 2 and "type" in (found.error or "")


@pytest.mark.parametrize(
    "reply",
    [
        '```json\n{"type": "bill"}\n```',
        'Here it is: {"type": "bill"} I hope it helps.',
    ],
)
def test_json_inside_other_text_is_found(reply: str) -> None:
    assert enrich.parse_answer(reply) == {"type": "bill"}


def test_checking_an_answer_names_what_is_wrong() -> None:
    good = {
        "category": "financial", "type": "bill", "title": "Electricity Bill",
        "author": {"name": "Energia do Norte", "evidence": "Energia do Norte", "page": 1},
        "date": {"value": "2024-01-10", "precision": "day", "kind": "issue", "evidence": "x", "page": 1},
        "other_dates": [], "people": [], "organizations": [], "tags": [], "summary": "s",
        "filename_conflicts": [],
    }  # fmt: skip
    assert enrich.problems(good) == []
    assert "type" in " ".join(enrich.problems({**good, "type": "spaceship"}))
    assert "date" in " ".join(
        enrich.problems({**good, "date": {**good["date"], "value": "10/01/2024"}})
    )
    assert "tags" in " ".join(enrich.problems({**good, "tags": ["a", "b", "c", "d", "e"]}))
    assert "title" in " ".join(enrich.problems({k: v for k, v in good.items() if k != "title"}))
    assert enrich.problems({**good, "author": None, "date": None}) == []  # unknown is allowed


def test_evidence_and_pages_of_the_wrong_kind_are_problems() -> None:
    """20261125-03: a real model gave an author's evidence as a list, and it crashed the import."""
    good = {
        "category": "financial", "type": "bill", "title": "Electricity Bill",
        "author": {"name": "Energia do Norte", "evidence": "Energia do Norte", "page": 1},
        "date": {"value": "2024-01-10", "precision": "day", "kind": "issue", "evidence": "x", "page": 1},
        "other_dates": [{"value": "2024-02-01", "kind": "due", "evidence": "x", "page": 1}],
        "people": [], "organizations": [], "tags": [], "summary": "s", "filename_conflicts": [],
    }  # fmt: skip
    assert enrich.problems(good) == []
    listed = {**good, "author": {**good["author"], "evidence": ["Energia do Norte", "Rua"]}}
    assert "author.evidence" in " ".join(enrich.problems(listed))
    paged = {**good, "date": {**good["date"], "page": "1"}}
    assert "date.page" in " ".join(enrich.problems(paged))
    unknown = {**good, "author": {**good["author"], "evidence": None, "page": None}}
    assert enrich.problems(unknown) == []


def test_other_dates_of_the_wrong_shape_are_left_out() -> None:
    """Supporting dates do not decide anything: one of the wrong shape is dropped, not retried."""
    pages = {1: "Issued 10 January 2024. Pay by 1 February 2024."}
    answer = {
        "author": None, "date": None,
        "other_dates": [
            {"value": "2024-02-01", "kind": "due", "evidence": "1 February 2024", "page": 1},
            {"value": "2024-01-10", "kind": "issue", "evidence": ["10 January"], "page": 1},
            "2024-03-01",
        ],
    }  # fmt: skip
    checked = enrich._checked(answer, pages)
    assert [d["value"] for d in checked["other_dates"]] == ["2024-02-01"]
    assert checked["other_dates"][0]["verified"] is True


def test_a_quote_that_is_not_text_is_not_verified() -> None:
    pages = {1: "Energia do Norte\nRua das Flores 12"}
    assert enrich.verify_quote(["Energia do Norte", "Rua"], 1, pages) == (False, None)  # type: ignore[arg-type]
    assert enrich.verify_quote({"text": "Energia"}, None, pages) == (False, None)  # type: ignore[arg-type]


def test_list_shaped_evidence_is_asked_again(server: StubServer, pdf_family: PdfFamily) -> None:
    server.model.misbehave["2022 Car Insurance.pdf"] = "list_evidence_once"  # type: ignore[attr-defined]
    client, info = enrich.provider(_values(server))
    found = enrich.classify(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    assert found.ok and found.attempts == 2
    assert found.answer["author"]["verified"] is True
    retry = server.requests[1]["json"]["messages"][-1]["content"]
    assert "author.evidence" in retry


def test_a_provider_that_fails_is_an_error(server: StubServer, pdf_family: PdfFamily) -> None:
    from chattr.translation import TranslationError

    server.status = 500
    client, info = enrich.provider(_values(server))
    client.retries = 0
    with pytest.raises(TranslationError):
        enrich.classify(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])


# --- The enrich stage (T02) ----------------------------------------------------------------------


@pytest.fixture
def family(pdf_family: PdfFamily, tmp_path: Path) -> Path:
    copy = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, copy)
    return copy


def _box(tmp_path: Path, server: StubServer | None, **more: Any) -> Box:
    box = Box.create(tmp_path / "Box", name="Our box")
    values: dict[str, Any] = {"documents.ocr": False, **more}
    if server is not None:
        values.update(_values(server))
    settings.save(box, values)
    return box


def _documents(box: Box) -> dict[str, dict[str, Any]]:
    from caixa.documents import records

    with box.master() as master:
        return {
            d["original_filename"]: records.get_document(master, d["item_id"])
            for d in records.list_documents(master)
        }


def _import(box: Box, family: Path) -> Any:
    from caixa.collectors.pdfImport import PdfCollector

    return PdfCollector().run(box, family, {"workers": 1}, lambda step: None)


def test_an_import_reads_every_document(server: StubServer, family: Path, tmp_path: Path) -> None:
    box = _box(tmp_path, server)
    result = _import(box, family)
    documents = _documents(box)
    readable = [d for name, d in documents.items() if name != "extrato_protegido.pdf"]
    assert all(d["ai_status"] == "completed" for d in readable), [
        (d["original_filename"], d["ai_status"]) for d in readable if d["ai_status"] != "completed"
    ]
    bill = documents["2022 Car Insurance.pdf"]
    fields = {(f["field"], f["source"]): f for f in bill["fields"]}
    assert fields[("type", "ai_inference")]["value"] == "bill"
    assert fields[("author", "ai_inference")]["verified"] == 1
    assert fields[("author", "ai_inference")]["evidence"] == "Energia do Norte"
    assert fields[("date", "ai_inference")]["value"] == "2024-01-10"
    run = next(r for r in bill["runs"] if r["stage"] == "enrich")
    assert run["model"] == "stand-in-documents" and run["provider"] == "endpoint"
    assert (
        run["prompt_version"] == enrich.PROMPT_VERSION
        and run["schema_version"] == enrich.SCHEMA_VERSION
    )
    assert not any("read by a model" in w for w in result.warnings)


def test_a_locked_document_is_not_read(server: StubServer, family: Path, tmp_path: Path) -> None:
    box = _box(tmp_path, server)
    _import(box, family)
    assert _documents(box)["extrato_protegido.pdf"]["ai_status"] == "pending"
    assert "extrato_protegido.pdf" not in server.model.asked  # type: ignore[attr-defined]


def test_without_a_model_documents_wait(family: Path, tmp_path: Path) -> None:
    box = _box(tmp_path, None, **{"summaries.provider": "endpoint"})
    result = _import(box, family)
    assert all(d["ai_status"] == "pending" for d in _documents(box).values())
    assert any("not read by a model" in w for w in result.warnings)


def test_a_failing_provider_marks_failed(server: StubServer, family: Path, tmp_path: Path) -> None:
    server.status = 500
    box = _box(tmp_path, server)
    _import(box, family)
    statuses = [d["ai_status"] for d in _documents(box).values()]
    assert _documents(box)["2022 Car Insurance.pdf"]["ai_status"] == "failed"
    assert statuses.count("failed") == 2  # then it stops: the others wait for a model that answers
    assert statuses.count("pending") == len(statuses) - 2


def test_an_answer_never_valid_needs_review(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    server.model.misbehave["2022 Car Insurance.pdf"] = "schema"  # type: ignore[attr-defined]
    box = _box(tmp_path, server)
    _import(box, family)
    bill = _documents(box)["2022 Car Insurance.pdf"]
    assert bill["ai_status"] == "needs_review"
    assert next(r for r in bill["runs"] if r["stage"] == "enrich")["result"] == "needs_review"


def test_reading_again_replaces_the_models_fields_and_keeps_the_owners(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    from caixa.documents import records

    box = _box(tmp_path, server)
    _import(box, family)
    bill = _documents(box)["2022 Car Insurance.pdf"]
    with box.master() as master:
        records.add_field(
            master, bill["item_id"], "author", "Energia do Norte, S.A.", "user_verified"
        )
    before = len(bill["fields"])
    done = enrich.enrich_documents(box, item_ids=[bill["item_id"]], progress=lambda s: None)
    assert done["enriched"] == 1
    again = _documents(box)["2022 Car Insurance.pdf"]
    assert len(again["fields"]) == before + 1  # the owner's, and the model's once
    assert any(f["source"] == "user_verified" for f in again["fields"])
    assert len([r for r in again["runs"] if r["stage"] == "enrich"]) == 2


def test_list_shaped_evidence_every_time_goes_to_review_and_the_import_ends(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    """The maintainer's crash (20261125-03), replayed: the import ends, the rest are read."""
    server.model.misbehave["2022 Car Insurance.pdf"] = "list_evidence"  # type: ignore[attr-defined]
    box = _box(tmp_path, server)
    _import(box, family)
    documents = _documents(box)
    assert documents["2022 Car Insurance.pdf"]["ai_status"] == "needs_review"
    assert "ai_unusable" in documents["2022 Car Insurance.pdf"]["review"]
    others = [
        d
        for n, d in documents.items()
        if n not in ("2022 Car Insurance.pdf", "extrato_protegido.pdf")
    ]
    assert all(d["ai_status"] == "completed" for d in others)


def test_an_unexpected_error_on_one_document_does_not_stop_the_others(
    server: StubServer, family: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = enrich.classify

    def classify(client: Any, document: DocumentInput, budget: int) -> Any:
        if document.filename == "2022 Car Insurance.pdf":
            raise TypeError("normalize() argument 2 must be str, not list")
        return real(client, document, budget)

    monkeypatch.setattr(enrich, "classify", classify)
    box = _box(tmp_path, server)
    _import(box, family)
    documents = _documents(box)
    bill = documents["2022 Car Insurance.pdf"]
    assert bill["ai_status"] == "failed"
    run = next(r for r in bill["runs"] if r["stage"] == "enrich")
    assert "TypeError" in json.dumps(run["report"])
    others = [
        d
        for n, d in documents.items()
        if n not in ("2022 Car Insurance.pdf", "extrato_protegido.pdf")
    ]
    assert all(d["ai_status"] == "completed" for d in others)


def test_cancelling_while_documents_are_read_still_cancels(
    server: StubServer, family: Path, tmp_path: Path
) -> None:
    from caixa.collectors.pdfImport import PdfCollector
    from caixa.service import JobCancelled

    def progress(step: Any) -> None:
        if step.stage == "enriching" and step.current == 2:
            raise JobCancelled()

    box = _box(tmp_path, server)
    with pytest.raises(JobCancelled):
        PdfCollector().run(box, family, {"workers": 1}, progress)


@pytest.fixture
def service(server: StubServer, family: Path, tmp_path: Path) -> Iterator[Any]:
    from caixa.service import Service

    box = _box(tmp_path, None, **{"summaries.provider": "endpoint"})
    _import(box, family)  # no model yet: everything waits
    settings.save(box, _values(server))
    made = Service(roots=[tmp_path])
    made.box_open(str(box.root))
    yield made
    made.close()


def test_the_job_reads_the_waiting_documents(service: Any) -> None:
    job = service.call("documents.enrich", {})
    done = service.wait(job["id"], 300)
    assert done["status"] == "done", done["error"]
    assert done["result"]["enriched"] == 14  # every readable document but the locked one
    statuses = {d["ai_status"] for d in service.call("documents.list", {})["documents"]}
    assert statuses == {"completed", "pending"}


def test_the_command_reads_named_documents(
    service: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from caixa import cli

    listing = service.call("documents.list", {})["documents"]
    item = next(d["item_id"] for d in listing if d["original_filename"] == "download.pdf")
    service.close()
    assert cli.main(["documents", "enrich", item, "--box", str(tmp_path / "Box")]) == 0
    assert "1 read" in capsys.readouterr().out


# --- What the model reads and is told (20261128-03, D31) ------------------------------------------


def test_a_cover_sheet_is_left_out_of_what_is_sent() -> None:
    pages = [(1, "FAX COVER SHEET"), (2, "Valley Water invoice"), (3, "Details"), (4, "Total 9")]
    document = DocumentInput("fax.pdf", {}, pages, 4, [])
    assert enrich.pages_sent(document) == [2, 3, 4]
    sent = enrich.prepare(document, 12_000)
    assert "FAX COVER" not in sent and "--- Page 2 ---" in sent
    assert "cover sheet (page 1) left out" in sent


def test_a_one_page_document_is_sent_whole() -> None:
    document = DocumentInput("short.pdf", {}, [(1, "Receipt")], 1, [])
    assert enrich.pages_sent(document) == [1]  # a one-page document has no cover sheet


def test_the_bottom_of_a_long_last_page_is_kept() -> None:
    last = "filler words " * 900 + "Issued by Valley Water, 12 March 2024"
    pages = [(1, "Letterhead " * 600), (2, last)]
    sent = enrich.prepare(DocumentInput("long.pdf", {}, pages, 2, []), 6_000)
    assert len(sent) <= 6_000
    assert sent.startswith("File name") and "Letterhead" in sent
    assert "Issued by Valley Water, 12 March 2024" in sent


def test_the_instruction_names_software() -> None:
    assert "Brite:Bill" in enrich.INSTRUCTION and "program" in enrich.INSTRUCTION


@pytest.mark.parametrize(
    ("name", "program"),
    [("Brite:Bill", True), ("brite bill", True), ("Microsoft Word", True), ("Pro API", True),
     ("Microsoft", False), ("Canon", False), ("Valley Water", False), ("HP Inc.", False)],
)  # fmt: skip
def test_is_program_matches_whole_names(name: str, program: bool) -> None:
    from caixa.documents.evidence import is_program

    assert is_program(name) is program


def test_a_program_author_in_the_properties_is_filtered() -> None:
    from caixa.documents.evidence import read_properties

    assert read_properties({"author": "Brite:Bill"}).author is None


def _answering_author(server: StubServer, pdf_family: PdfFamily, author: str) -> None:
    model = DocumentModel(pdf_family)

    def respond(request: dict[str, Any]) -> dict[str, Any]:
        reply = model.respond(request)
        content = json.loads(reply["choices"][0]["message"]["content"])
        if "type" in content and "author" in content:  # the classification, not a type's fields
            content["author"] = {"name": author, "evidence": None, "page": None}
        return {"choices": [{"message": {"content": json.dumps(content)}}]}

    server.respond = respond


def test_a_program_named_by_the_model_is_dropped(server: StubServer, pdf_family: PdfFamily) -> None:
    _answering_author(server, pdf_family, "Brite:Bill")
    client, info = enrich.provider(_values(server))
    found = enrich.classify(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    assert found.ok and found.answer["author"] is None


def test_a_company_that_makes_software_is_kept(server: StubServer, pdf_family: PdfFamily) -> None:
    _answering_author(server, pdf_family, "Microsoft")
    client, info = enrich.provider(_values(server))
    found = enrich.classify(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    assert found.answer["author"]["name"] == "Microsoft"


# --- The second look (20261128-03 T02) ------------------------------------------------------------


def _looking(
    server: StubServer, pdf_family: PdfFamily, second: dict[str, Any] | None, **first: Any
) -> list[str]:
    """The stand-in model, with its classification's author (and anything in `first`) taken away on
    the first look, and `second` given on the second. Returns each prompt it was sent."""
    model = DocumentModel(pdf_family)
    prompts: list[str] = []

    def respond(request: dict[str, Any]) -> dict[str, Any]:
        reply = model.respond(request)
        content = json.loads(reply["choices"][0]["message"]["content"])
        asked = next(m["content"] for m in request["messages"] if m["role"] == "user")
        if "type" in content and "author" in content:
            prompts.append(asked)
            if "Second look" in asked:
                content.update(second or {"author": None})
            else:
                content["author"] = None
                content.update(first)
        return {"choices": [{"message": {"content": json.dumps(content)}}]}

    server.respond = respond
    return prompts


SENDER = {"author": {"name": "Energia do Norte", "evidence": "Energia do Norte", "page": 1}}


def test_an_author_missing_at_first_is_found_on_the_second_look(
    server: StubServer, pdf_family: PdfFamily
) -> None:
    prompts = _looking(server, pdf_family, SENDER)
    client, info = enrich.provider(_values(server))
    found = enrich.read(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    assert found.answer["author"]["name"] == "Energia do Norte"
    assert found.answer["author"]["verified"] is True
    assert found.looks == {"author": "bottom", "date": "first"}
    assert len(prompts) == 2 and "Second look" in prompts[1]
    assert "--- Page 1 (last), its end ---" in prompts[1]
    assert [t["look"] for t in found.tries] == ["first", "bottom"]


def test_a_complete_answer_asks_no_second_time(server: StubServer, pdf_family: PdfFamily) -> None:
    client, info = enrich.provider(_values(server))
    found = enrich.read(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    classifications = [r for r in server.requests if "Second look" in json.dumps(r["json"])]
    assert classifications == [] and found.looks == {"author": "first", "date": "first"}


def test_the_second_look_fills_only_what_is_missing(
    server: StubServer, pdf_family: PdfFamily
) -> None:
    other = {"value": "2019-01-01", "kind": "issue", "evidence": None, "page": None}
    _looking(server, pdf_family, {**SENDER, "date": other})
    client, info = enrich.provider(_values(server))
    found = enrich.read(client, _input(pdf_family, "2022 Car Insurance.pdf"), info["budget"])
    assert found.answer["date"]["value"] == "2024-01-10"  # the first look's, kept
    assert found.answer["author"]["name"] == "Energia do Norte"


def test_what_is_still_missing_waits_in_unrecognized_and_the_log_says_so(
    server: StubServer, pdf_family: PdfFamily, tmp_path: Path
) -> None:
    from caixa import session_log
    from caixa.collectors.pdfImport import PdfCollector
    from caixa.documents import records

    _looking(server, pdf_family, None)  # no author on either look
    source = tmp_path / "pdfs"
    source.mkdir()
    shutil.copyfile(pdf_family.root / "2022 Car Insurance.pdf", source / "2022 Car Insurance.pdf")
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(box, {**_values(server), "documents.ocr": False})
    with session_log.opened(box, 1, "PDF import") as log:
        PdfCollector().run(box, source, {"workers": 1}, lambda step: None)
    with box.master() as master:
        (document,) = records.list_documents(master)
    assert document["file_path"].startswith("Documents/PDF/Unrecognized/")
    events = [json.loads(line) for line in log.events_path.read_text().splitlines()]
    proposed = next(e for e in events if e["event"] == "propose")
    assert proposed["author_look"] is None and proposed["date_look"] == "first"
    read = next(e for e in events if e["event"] == "read" and e.get("attempts"))
    assert [a["look"] for a in read["attempts"]] == ["first", "bottom"]
