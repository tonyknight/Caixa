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


def test_compose_writes_the_owners_pattern() -> None:
    from caixa.documents.organized import compose

    name = read_organized("(2024-03-12) Water bill (Águas do Vale) [Utilities] [Home] (2).pdf")
    assert name is not None
    assert compose(name, "2024-03-13", "Water invoice", "AdV") == (
        "(2024-03-13) Water invoice (AdV) [Utilities] [Home] (2).pdf"
    )
    plain = read_organized("(2023-11-05) Letter from João [Family].PDF")
    assert plain is not None
    assert compose(plain, "2023-11-05", "Letter from João", None) == (
        "(2023-11-05) Letter from João [Family].PDF"
    )
    assert compose(plain, "2023-11-05", "Letter", "João Costa") == (
        "(2023-11-05) Letter (João Costa) [Family].PDF"
    )


# --- The author and tags wherever the name holds them (20261128-07, D30 amended) ------------------


@pytest.mark.parametrize(
    ("filename", "subject", "author", "tags"),
    [
        ("(1985-06-01) Training Certificate - (Escola Naval) - [Navy].pdf",
         "Training Certificate", "Escola Naval", ["Navy"]),
        ("(1989-11-18) (Proteção Civil) Payout.pdf", "Payout", "Proteção Civil", []),
        ("(1981-01-01) Costa Cheques (Banco Atlântico)  - [Cheques].pdf",
         "Costa Cheques", "Banco Atlântico", ["Cheques"]),
        ("(1988-06-01) Class of 1988 Programme - (Escola Secundária) - 2.pdf",
         "Class of 1988 Programme", "Escola Secundária", []),
        ("(1990-06-01) Photos from the camp - (Maria Costa) [Escola Naval] - [Navy].pdf",
         "Photos from the camp", "Maria Costa", ["Escola Naval", "Navy"]),
        ("(1995-08-09) [Quartz] 2.1 Notes  - (Café Central) - [Quartz].pdf",
         "[Quartz] 2.1 Notes", "Café Central", ["Quartz"]),
        ("(2007-06-01) (Ana Costa)'s garden plan - [Ana Costa].pdf",
         "Ana Costa's garden plan", "Ana Costa", ["Ana Costa"]),
        ("(2010-06-01) August (Energia do Norte) Bill.pdf",
         "August Energia do Norte Bill", "Energia do Norte", []),
        ("(2013-08-13) (Clínica Santa Luzia) Bill - I(Clínica Santa Luzia)].pdf",
         "Bill", "Clínica Santa Luzia", []),
        ("(2016-07-07) (Rua Nova) Appraisal - [(Rua Nova)].pdf", "Appraisal", "Rua Nova", ["Rua Nova"]),
        ("(2000-06-01) Statements - (Banco Atlântico) - [Banking] - [Home].pdf",
         "Statements", "Banco Atlântico", ["Banking", "Home"]),
        ("(1987-12-31) Costa Cheques [1987].pdf", "Costa Cheques", None, ["1987"]),
        ("(1985-12-31) Costa Cheques [1985-1986] 2.pdf", "Costa Cheques", None, ["1985-1986"]),
    ],
)  # fmt: skip
def test_the_author_and_tags_wherever_they_are(
    filename: str, subject: str, author: str | None, tags: list[str]
) -> None:
    name = read_organized(filename)
    assert name is not None
    assert (name.subject, name.author, name.tags) == (subject, author, tags)


def test_a_copy_number_without_brackets() -> None:
    name = read_organized("(1993-06-01) Postcard - (Ana Costa) 2.pdf")
    assert name is not None and (name.author, name.copy) == ("Ana Costa", "2")
    dashed = read_organized("(1988-06-01) Programme - (Escola Secundária) - 2.pdf")
    assert dashed is not None and dashed.copy == "2"
    year = read_organized("(2015-06-01) (Livraria Estrela) - 1679.pdf")
    assert year is not None and year.copy is None and year.subject == "1679"


def test_of_two_different_authors_the_last() -> None:
    name = read_organized("(2022-06-01) Lease (signed copy) (Rui Pereira) [Housing].pdf")
    assert name is not None
    assert (name.subject, name.author, name.authors) == (
        "Lease (signed copy)", "Rui Pereira", ["signed copy", "Rui Pereira"],
    )  # fmt: skip


def test_the_same_tag_once_and_the_same_author_once() -> None:
    name = read_organized(
        "(2013-09-18) (Clínica Santa Luzia) Bill - [Ana] - [ana] - (Clínica Santa Luzia).pdf"
    )
    assert name is not None and name.authors == ["Clínica Santa Luzia"] and name.tags == ["Ana"]


def test_rewrite_in_place() -> None:
    from caixa.documents.organized import rewrite

    old = "(1985-06-01) Training Certificate - (Escola Naval) - [Navy].pdf"
    name = read_organized(old)
    assert name is not None
    assert (
        rewrite(name, author="Marinha")
        == "(1985-06-01) Training Certificate - (Marinha) - [Navy].pdf"
    )
    assert rewrite(name, subject="Training Diploma") == (
        "(1985-06-01) Training Diploma - (Escola Naval) - [Navy].pdf"
    )
    assert (
        rewrite(name, date="1985-07-01")
        == "(1985-07-01) Training Certificate - (Escola Naval) - [Navy].pdf"
    )
    first = read_organized("(1989-11-18) (Proteção Civil) Payout.pdf")
    assert first is not None
    assert rewrite(first, author="Protecção Civil") == "(1989-11-18) (Protecção Civil) Payout.pdf"
    none = read_organized("(1987-12-31) Costa Cheques [1987].pdf")
    assert none is not None
    assert (
        rewrite(none, author="Banco Atlântico")
        == "(1987-12-31) Costa Cheques (Banco Atlântico) [1987].pdf"
    )


@pytest.mark.parametrize(
    ("filename", "subject"),
    [
        ("(2013-09-18) Ana (Clínica Santa Luzia) Bill - [Ana Costa] - I(Clínica Santa Luzia)].pdf",
         "Ana Clínica Santa Luzia Bill"),
        ("(2001-06-01) Title Report - (Notário Silva)a.pdf", "Title Report"),
        ("(2001-06-01) Title Report - (Notário Silva)b.pdf", "Title Report"),
    ],
)  # fmt: skip
def test_untidy_endings_leave_a_clean_subject(filename: str, subject: str) -> None:
    name = read_organized(filename)
    assert name is not None and name.subject == subject
