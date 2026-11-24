"""Reconciling what the filename, the properties, the text, the model and the owner say, and
deciding whether a document can be named and filed (ticket 20261124-12)."""

from __future__ import annotations

import shutil
from itertools import count
from pathlib import Path
from typing import Any, Iterator, Optional

import pytest

from caixa.documents.reconcile import decide

_ids = count(1)


def F(field: str, value: str, source: str, evidence: Optional[str] = None,
      page: Optional[int] = None, verified: Optional[int] = None) -> dict[str, Any]:  # fmt: skip
    return {"id": next(_ids), "field": field, "value": value, "source": source,
            "evidence": evidence, "page": page, "verified": verified, "state": "proposed"}  # fmt: skip


PAGES = {
    1: "Banco Atlântico\nChecking Statement\nStatement period: November 1, 2024 to November 30, 2024"
}


def _model(**values: Any) -> list[dict[str, Any]]:
    base = {
        "type": F("type", "statement", "ai_inference"),
        "category": F("category", "financial", "ai_inference"),
        "title": F("title", "Checking Statement", "ai_inference"),
        "author": F("author", "Banco Atlântico", "ai_inference", "Banco Atlântico", 1, 1),
        "date": F("date", "2024-11-30", "ai_inference", "November 30, 2024", 1, 1),
        "date_kind": F("date_kind", "statement_end", "ai_inference"),
    }
    for key, value in values.items():
        if value is None:
            base.pop(key, None)
        else:
            base[key] = value
    return list(base.values())


def test_everything_agreeing_is_confident() -> None:
    fields = _model() + [
        F("date", "2024-11", "original_filename", "2024-11"),
        F("type", "statement", "original_filename"),
        F("author", "Banco Atlântico", "pdf_metadata", "Banco Atlântico"),
    ]
    decision = decide(fields, PAGES, {}, ai_ok=True)
    assert decision.confident and decision.reasons == []
    assert (decision.date, decision.precision, decision.date_kind) == (
        "2024-11-30",
        "day",
        "statement_end",
    )
    assert (decision.title, decision.author, decision.type, decision.category) == (
        "Checking Statement", "Banco Atlântico", "statement", "financial",
    )  # fmt: skip
    applied = {f["field"] for f in fields if f["id"] in decision.applied}
    assert {"date", "author", "title", "type", "category"} <= applied
    assert decision.date_sources == ["ai_inference", "original_filename"]


def test_a_more_precise_filename_date_is_kept() -> None:
    fields = _model(date=F("date", "2024-11", "ai_inference", "November", 1, 1)) + [
        F("date", "2024-11-30", "original_filename", "2024-11-30")
    ]
    decision = decide(fields, PAGES, {}, ai_ok=True)
    assert decision.date == "2024-11-30" and decision.precision == "day"


def test_a_filename_date_that_names_another_date_is_explained() -> None:
    pages = {1: "Property Tax Statement\nTax year 2022\nIssued: April 20, 2023"}
    fields = _model(
        type=F("type", "tax", "ai_inference"),
        title=F("title", "Property Tax Bill", "ai_inference"),
        author=F("author", "Câmara Municipal de Vila Nova", "ai_inference", "Câmara", 1, 1),
        date=F("date", "2022", "ai_inference", "Tax year 2022", 1, 1),
        date_kind=F("date_kind", "tax_year", "ai_inference"),
    ) + [
        F("date", "2023", "original_filename", "2023"),
        F("date_in_text", "2023-04-20", "pdf_content", "April 20, 2023", 1),
        F("type", "tax", "original_filename"),
        F("type", "bill", "original_filename"),
    ]
    decision = decide(fields, pages, {}, ai_ok=True)
    assert decision.confident and decision.date == "2022" and decision.precision == "year"
    assert decision.explained == [("2023", "issue")] or decision.explained == [("2023", "other")]


def test_a_filename_date_nothing_explains_is_a_conflict() -> None:
    pages = {
        1: "Energia do Norte\nElectricity Bill\nIssued: January 10, 2024\nBilling period: December 2023"
    }
    filename_date = F("date", "2022", "original_filename", "2022")
    fields = _model(
        type=F("type", "bill", "ai_inference"),
        title=F("title", "Electricity Bill", "ai_inference"),
        author=F("author", "Energia do Norte", "ai_inference", "Energia do Norte", 1, 1),
        date=F("date", "2024-01-10", "ai_inference", "January 10, 2024", 1, 1),
        date_kind=F("date_kind", "issue", "ai_inference"),
    ) + [
        filename_date,
        F("type", "insurance", "original_filename"),
        F("date_in_text", "2024-01-10", "pdf_content", "January 10, 2024", 1),
    ]
    decision = decide(fields, pages, {}, ai_ok=True)
    assert not decision.confident
    assert {"conflict:date", "conflict:type"} <= set(decision.reasons)
    assert filename_date["id"] in decision.conflicts


def test_type_words_agree_when_one_of_them_is_the_models() -> None:
    fields = _model() + [
        F("type", "bill", "original_filename"),
        F("type", "statement", "original_filename"),
    ]
    assert "conflict:type" not in decide(fields, PAGES, {}, ai_ok=True).reasons


def test_a_bill_and_an_invoice_are_close_enough() -> None:
    fields = _model(type=F("type", "invoice", "ai_inference")) + [
        F("type", "bill", "original_filename")
    ]
    assert "conflict:type" not in decide(fields, PAGES, {}, ai_ok=True).reasons


def test_an_author_is_matched_to_a_known_one() -> None:
    known = {"banco atlantico": "Banco Atlântico"}
    fields = _model(
        author=F("author", "BANCO ATLANTICO, S.A.", "ai_inference", "Banco Atlântico", 1, 1)
    )
    decision = decide(fields, PAGES, known, ai_ok=True)
    assert decision.author == "Banco Atlântico" and decision.alias == "BANCO ATLANTICO, S.A."


def test_a_different_author_in_the_filename_is_a_conflict() -> None:
    fields = _model() + [
        F("author", "Seguradora Horizonte", "original_filename", "Seguradora Horizonte")
    ]
    decision = decide(fields, PAGES, {}, ai_ok=True)
    assert "conflict:author" in decision.reasons and not decision.confident


def test_a_different_author_in_the_properties_is_not() -> None:
    fields = _model() + [F("author", "J. Smith", "pdf_metadata", "J. Smith")]
    assert decide(fields, PAGES, {}, ai_ok=True).confident


def test_the_owners_values_win() -> None:
    fields = _model() + [
        F("author", "Banco do Atlântico", "user_verified"),
        F("date", "2024-12", "user_verified"),
        F("title", "Statement of Account", "user_verified"),
    ]
    decision = decide(fields, PAGES, {}, ai_ok=True)
    assert decision.author == "Banco do Atlântico" and decision.date == "2024-12"
    assert decision.precision == "month" and decision.title == "Statement of Account"
    assert decision.confident  # the owner's word needs no evidence


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"date": None}, "no_date"),
        ({"author": None}, "no_author"),
        ({"date": F("date", "2024-11-30", "ai_inference", "30 Nov", 1, 0)}, "unverified_date"),
        (
            {"author": F("author", "Banco Central", "ai_inference", "Banco Central", 1, 0)},
            "unverified_author",
        ),
        ({"title": None}, "no_title"),
        ({"type": None}, "no_type"),
    ],
)
def test_each_reason_for_review(changes: dict[str, Any], reason: str) -> None:
    decision = decide(_model(**changes), PAGES, {}, ai_ok=True)
    assert reason in decision.reasons and not decision.confident


def test_an_unusable_reading_is_not_confident() -> None:
    decision = decide(_model(), PAGES, {}, ai_ok=False)
    assert "ai_unusable" in decision.reasons and not decision.confident


def test_an_author_named_in_the_text_needs_no_quote() -> None:
    fields = _model(author=F("author", "Banco Atlântico", "ai_inference", None, None, None))
    assert decide(fields, PAGES, {}, ai_ok=True).confident


def test_a_date_written_in_the_text_needs_no_quote() -> None:
    fields = _model(date=F("date", "2024-11-30", "ai_inference", None, None, None)) + [
        F("date_in_text", "2024-11-30", "pdf_content", "November 30, 2024", 1)
    ]
    assert decide(fields, PAGES, {}, ai_ok=True).confident
