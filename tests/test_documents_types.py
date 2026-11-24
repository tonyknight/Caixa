"""The fields of each type of document, and amounts read as people write them
(ticket 20261124-11)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterator

import pytest

from caixa.documents.types import AMOUNTS, TYPE_SCHEMAS, parse_amount, type_problems

FIELDS = {
    "statement": {"institution", "account_type", "account_suffix", "period_start", "period_end",
                  "opening_balance", "closing_balance"},
    "cheque": {"number", "date", "payee", "amount"},
    "bill": {"provider", "service_address", "period_start", "period_end", "amount_due", "due_date"},
    "invoice": {"vendor", "number", "date", "total"},
    "insurance": {"insurer", "policy_number", "coverage_start", "coverage_end"},
    "tax": {"issuer", "tax_year", "form"},
    "agreement": {"parties", "subject", "execution_date"},
    "correspondence": {"sender", "recipient", "date", "subject"},
}  # fmt: skip


def test_every_type_has_its_fields() -> None:
    assert set(TYPE_SCHEMAS) == set(FIELDS)
    for kind, fields in FIELDS.items():
        schema = TYPE_SCHEMAS[kind]
        assert set(schema["properties"]) == fields, kind
        assert set(schema["required"]) == fields and schema["additionalProperties"] is False


def test_money_fields_are_named() -> None:
    assert {"opening_balance", "closing_balance", "amount", "amount_due", "total"} <= AMOUNTS


@pytest.mark.parametrize(
    ("written", "number"),
    [
        ("2,310.55", 2310.55),
        ("1,987.20 EUR", 1987.20),
        ("2.104,33", 2104.33),
        ("23,40", 23.40),
        ("450.00", 450.0),
        ("€ 1 200,00", 1200.0),
        ("$450", 450.0),
        ("-54.10", -54.10),
        ("+1,820.00", 1820.0),
        ("312", 312.0),
    ],
)
def test_amounts_as_people_write_them(written: str, number: float) -> None:
    assert parse_amount(written) == pytest.approx(number)


@pytest.mark.parametrize("written", ["", "n/a", "four hundred", "12/03/2024", None])
def test_what_is_not_an_amount(written: Any) -> None:
    assert parse_amount(written) is None


def _field(value: Any) -> dict[str, Any]:
    return {"value": value, "evidence": None, "page": None}


def test_a_good_answer_has_no_problems() -> None:
    answer = {name: _field("x") for name in FIELDS["invoice"]}
    assert type_problems("invoice", answer) == []
    assert type_problems("invoice", {**answer, "total": None}) == []  # unknown is allowed


def test_answers_that_break_a_schema_are_named() -> None:
    answer = {name: _field("x") for name in FIELDS["invoice"]}
    assert "total is missing" in type_problems(
        "invoice", {k: v for k, v in answer.items() if k != "total"}
    )
    assert "vendor" in " ".join(type_problems("invoice", {**answer, "vendor": "Livraria"}))
    assert "parties" in " ".join(
        type_problems(
            "agreement", {**{n: _field("x") for n in FIELDS["agreement"]}, "parties": "Maria"}
        )
    )
    assert type_problems("invoice", "nonsense")


# --- Asking for a type's fields (T02) ----------------------------------------------------------


@pytest.fixture
def stand_in(pdf_family: Any) -> Iterator[Any]:
    from stand_in_documents import DocumentModel
    from stub_server import StubServer

    server = StubServer()
    server.model = DocumentModel(pdf_family)  # type: ignore[attr-defined]
    server.respond = server.model.respond  # type: ignore[attr-defined]
    yield server
    server.close()


def _imported(pdf_family: Any, tmp_path: Path, server: Any) -> dict[str, dict[str, Any]]:
    from caixa import settings
    from caixa.box import Box
    from caixa.collectors.pdfImport import PdfCollector
    from caixa.documents import records

    source = tmp_path / "pdfs"
    shutil.copytree(pdf_family.root, source)
    box = Box.create(tmp_path / "Box", name="Our box")
    settings.save(
        box,
        {
            "documents.ocr": False,
            "summaries.provider": "endpoint",
            "summaries.endpoint": server.endpoint,
            "summaries.model": "stand-in-documents",
        },
    )
    PdfCollector().run(box, source, {"workers": 1}, lambda step: None)
    with box.master() as master:
        return {
            d["original_filename"]: records.get_document(master, d["item_id"])
            for d in records.list_documents(master)
        }


def _model_fields(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["field"]: f for f in document["fields"] if f["source"] == "ai_inference"}


def test_a_statements_fields(pdf_family: Any, tmp_path: Path, stand_in: Any) -> None:
    found = _imported(pdf_family, tmp_path, stand_in)
    fields = _model_fields(found["2024-11 Banco Atlântico Checking Statement.pdf"])
    assert fields["institution"]["value"] == "Banco Atlântico"
    assert fields["account_suffix"]["value"] == "4821" and fields["account_suffix"]["verified"] == 1
    assert fields["opening_balance"]["number"] == pytest.approx(2310.55)
    assert fields["closing_balance"]["number"] == pytest.approx(1987.20)
    assert (
        fields["closing_balance"]["evidence"] == "1,987.20"
        and fields["closing_balance"]["page"] == 1
    )
    assert fields["period_start"]["value"] == "2024-11-01"


def test_a_bill_an_invoice_and_a_tax_document(
    pdf_family: Any, tmp_path: Path, stand_in: Any
) -> None:
    found = _imported(pdf_family, tmp_path, stand_in)
    bill = _model_fields(found["2022 Car Insurance.pdf"])
    assert bill["provider"]["value"] == "Energia do Norte"
    assert bill["amount_due"]["number"] == pytest.approx(88.15)
    invoice = _model_fields(found["download.pdf"])
    assert invoice["number"]["value"] == "FT 2024/118" and invoice["total"][
        "number"
    ] == pytest.approx(37.80)
    tax = _model_fields(found["2023 Property Tax Bill.pdf"])
    assert tax["tax_year"]["value"] == "2022" and tax["tax_year"]["verified"] == 1


def test_a_type_without_fields_asks_nothing_more(
    pdf_family: Any, tmp_path: Path, stand_in: Any
) -> None:
    _imported(pdf_family, tmp_path, stand_in)
    assert stand_in.model.asked["Exame Ana Costa 2020.pdf"] == 1  # classified, nothing more
    assert stand_in.model.asked["2022 Car Insurance.pdf"] == 2  # classified, then its bill fields


def test_a_type_answer_never_valid_keeps_the_classification(
    pdf_family: Any, tmp_path: Path, stand_in: Any
) -> None:
    stand_in.model.misbehave["type:2022 Car Insurance.pdf"] = "schema"
    found = _imported(pdf_family, tmp_path, stand_in)
    bill = found["2022 Car Insurance.pdf"]
    assert bill["ai_status"] == "completed"
    assert "provider" not in _model_fields(bill) and _model_fields(bill)["type"]["value"] == "bill"
    run = next(r for r in bill["runs"] if r["stage"] == "enrich")
    assert "provider" in (run["report"] or {}).get("type_error", "")
