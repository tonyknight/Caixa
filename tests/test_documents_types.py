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
