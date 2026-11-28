"""Reading organized file names (ticket 20261128-01, D30): `(YYYY-MM-DD) Subject (Author) [Tag].pdf`
and its partial forms, with no model."""

from __future__ import annotations

import pytest

from caixa.documents.organized import compatible, on_page, read_organized, with_date


def test_the_full_form() -> None:
    name = read_organized("(2024-03-12) Water bill (Águas do Vale) [Utilities].pdf")
    assert name is not None
    assert (name.date, name.precision, name.impossible) == ("2024-03-12", "day", False)
    assert (name.subject, name.author, name.tags) == ("Water bill", "Águas do Vale", ["Utilities"])


@pytest.mark.parametrize(
    ("filename", "date", "precision"),
    [
        ("(2024-03) Statement (Banco Atlântico) [Banking].pdf", "2024-03", "month"),
        ("(2019) Tax return (IRS).pdf", "2019", "year"),
    ],
)
def test_month_and_year_dates(filename: str, date: str, precision: str) -> None:
    name = read_organized(filename)
    assert name is not None and (name.date, name.precision) == (date, precision)


def test_no_author() -> None:
    name = read_organized("(2023-11-05) Letter from João [Family].pdf")
    assert name is not None
    assert (name.subject, name.author, name.tags) == ("Letter from João", None, ["Family"])


def test_no_tag_and_several_tags() -> None:
    plain = read_organized("(2019) Tax return (IRS).pdf")
    assert plain is not None and (plain.author, plain.tags) == ("IRS", [])
    many = read_organized("(2024-03) Statement (Banco Atlântico) [Banking] [Joint].pdf")
    assert many is not None and many.tags == ["Banking", "Joint"]


def test_brackets_inside_the_subject() -> None:
    name = read_organized("(2022-06-01) Lease (signed copy) (Rui Pereira) [Housing].pdf")
    assert name is not None
    assert (name.subject, name.author) == ("Lease (signed copy)", "Rui Pereira")


def test_a_copy_number_is_kept_apart() -> None:
    name = read_organized("(2024-03-12) Water bill (Águas do Vale) [Utilities] (2).pdf")
    assert name is not None
    assert (name.author, name.tags, name.copy) == ("Águas do Vale", ["Utilities"], "(2)")


@pytest.mark.parametrize("last", ["(March)", "(Março)", "(2)", "(12)", "(2024)"])
def test_a_month_or_a_number_is_not_an_author(last: str) -> None:
    name = read_organized(f"(2024-03) Statement {last}.pdf")
    assert name is not None and name.author is None


def test_an_impossible_date_is_flagged_not_trimmed() -> None:
    name = read_organized("(2024-02-30) Bill (PG&E) [Utilities].pdf")
    assert name is not None
    assert (name.date, name.impossible, name.author) == ("2024-02-30", True, "PG&E")
    month = read_organized("(2024-13) Bill (PG&E).pdf")
    assert month is not None and month.impossible


@pytest.mark.parametrize(
    "filename",
    [
        "2024-03-12 Water bill.pdf",  # no brackets round the date
        "(2024-03-12).pdf",  # no subject
        "scan_00482.pdf",
        "(24-03-12) Bill (PG&E).pdf",  # a two-digit year
    ],
)
def test_a_name_that_does_not_fit(filename: str) -> None:
    assert read_organized(filename) is None


def test_a_date_and_a_subject_alone_are_enough() -> None:
    name = read_organized("(2024-03-12) Water bill - Águas do Vale.pdf")  # Caixa's own form too
    assert name is not None
    assert (name.subject, name.author, name.tags) == ("Water bill - Águas do Vale", None, [])


def test_with_date_changes_only_the_date() -> None:
    old = "(2024-02-30) Bill (PG&E) [Utilities] (2).pdf"
    assert with_date(old, "2024-02-28") == "(2024-02-28) Bill (PG&E) [Utilities] (2).pdf"
    assert with_date("(2024) Tax (IRS).pdf", "2024-04-15") == "(2024-04-15) Tax (IRS).pdf"


PAGE = (
    "Águas do Vale. Fatura emitida a 12 de março de 2024. Período: 01/02/2024 a 29/02/2024. "
    "Pagar até 2024-04-02."
)


@pytest.mark.parametrize(
    ("date", "found"),
    [
        ("2024-03-12", True),  # in Portuguese
        ("2024-02-29", True),  # dd/mm/yyyy
        ("2024-04-02", True),  # ISO
        ("2024-03-13", False),
        ("2024-03", True),  # a day in that month
        ("2024-05", False),
        ("2024", True),
        ("2023", False),
    ],
)
def test_on_page_at_each_precision(date: str, found: bool) -> None:
    assert on_page(date, [PAGE]) is found


@pytest.mark.parametrize(
    ("date", "text"),
    [
        ("2024-03", "Statement for March 2024"),
        ("2024-03", "Extrato de março de 2024"),
        ("2024-03", "Period 03/2024"),
        ("2024-03", "Billing month: 2024-03"),
        ("2019", "Tax year 2019"),
    ],
)
def test_a_month_or_year_written_alone_is_on_the_page(date: str, text: str) -> None:
    assert on_page(date, [text])


@pytest.mark.parametrize(
    ("one", "other", "same"),
    [
        ("2024-03-12", "2024-03-12", True),
        ("2024-03", "2024-03-12", True),
        ("2024-03-12", "2024", True),
        ("2024-03-12", "2024-03-15", False),
        ("2024-03", "2024-04", False),
        ("2024", "2023-12-31", False),
    ],
)
def test_compatible(one: str, other: str, same: bool) -> None:
    assert compatible(one, other) is same and compatible(other, one) is same
