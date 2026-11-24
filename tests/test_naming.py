"""Caixa's archival names (ticket 20261124-02): `(DATE) Title - Author.ext`, shared by file collectors.

See `docs/Archival names.md`. Its examples table is checked here too, so the document and the code
say the same thing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from caixa.naming import (
    LIMIT,
    NamingDate,
    NamingError,
    archival_name,
    clean,
    folder_name,
    free_path,
    original_name,
)

# --- Dates ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "precision", "prefix"),
    [
        ("2024-11-30", "day", "(2024-11-30)"),
        ("2024-11", "month", "(2024-11)"),
        ("2024", "year", "(2024)"),
    ],
)
def test_a_date_keeps_its_precision(value: str, precision: str, prefix: str) -> None:
    date = NamingDate.parse(value)
    assert (date.value, date.precision, date.prefix) == (value, precision, prefix)
    assert date.year == 2024


@pytest.mark.parametrize("value", ["", "24", "2024-13", "2024-02-30", "2024/11/30", "30-11-2024"])
def test_a_date_that_is_not_one_is_refused(value: str) -> None:
    with pytest.raises(NamingError):
        NamingDate.parse(value)


# --- Cleaning ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "cleaned"),
    [
        ("Invoice FT 2024/118", "Invoice FT 2024-118"),
        ("Re: the house", "Re - the house"),
        ('Policy "Home" <renewal>?*', "Policy 'Home' renewal"),
        ("  .Statement..  ", "Statement"),
        ("Line\tone\nline two", "Line one line two"),
        ("Tab\x00le", "Table"),
        ("a | b \\ c", "a - b - c"),
        ("Café Central", "Café Central"),  # NFC: one character for é
    ],
)
def test_unsafe_characters_are_cleaned(text: str, cleaned: str) -> None:
    assert clean(text) == cleaned


@pytest.mark.parametrize(
    ("text", "cleaned"),
    [
        ("BANCO ATLÂNTICO", "Banco Atlântico"),
        ("CÂMARA MUNICIPAL DE VILA NOVA", "Câmara Municipal de Vila Nova"),
        ("STATEMENT OF ACCOUNT", "Statement of Account"),
        ("EDP", "EDP"),  # short: an acronym, kept
        ("Banco ATLÂNTICO", "Banco ATLÂNTICO"),  # not all capitals: left as written
    ],
)
def test_shouting_becomes_title_case(text: str, cleaned: str) -> None:
    assert clean(text) == cleaned


# --- Names ---------------------------------------------------------------------------------------


def test_the_full_name() -> None:
    name = archival_name(NamingDate.parse("2024-11-30"), "Checking Statement", "Banco Atlântico")
    assert name == "(2024-11-30) Checking Statement - Banco Atlântico.pdf"


def test_without_an_author() -> None:
    assert archival_name(NamingDate.parse("2023"), "Property Agreement") == (
        "(2023) Property Agreement.pdf"
    )


def test_the_extension_is_kept_lower_case() -> None:
    name = archival_name(NamingDate.parse("2024-05"), "Holiday", None, extension=".JPG")
    assert name == "(2024-05) Holiday.jpg"


@pytest.mark.parametrize(
    "title",
    [
        "Banco Atlântico Checking Statement",
        "Checking Statement - Banco Atlântico",
        "Checking Statement Banco Atlântico",
        "2024-11-30 Checking Statement",
        "(2024-11-30) Checking Statement",
    ],
)
def test_the_title_does_not_repeat_the_date_or_the_author(title: str) -> None:
    name = archival_name(NamingDate.parse("2024-11-30"), title, "Banco Atlântico")
    assert name == "(2024-11-30) Checking Statement - Banco Atlântico.pdf"


def test_a_title_that_is_only_the_author_is_kept() -> None:
    name = archival_name(NamingDate.parse("2024"), "Banco Atlântico", "Banco Atlântico")
    assert name == "(2024) Banco Atlântico - Banco Atlântico.pdf"


@pytest.mark.parametrize("title", ["", "   ", "???"])
def test_a_name_needs_a_title(title: str) -> None:
    with pytest.raises(NamingError):
        archival_name(NamingDate.parse("2024"), title, "Banco Atlântico")


def test_a_long_title_is_shortened_at_a_word_and_the_author_kept() -> None:
    title = "Annual Statement of Benefits and Contributions for the Pension Plan " * 3
    name = archival_name(NamingDate.parse("2024-12-31"), title, "Seguradora Horizonte")
    stem = name.removesuffix(".pdf")
    assert len(stem) <= LIMIT
    assert stem.startswith("(2024-12-31) Annual Statement")
    assert stem.endswith(" - Seguradora Horizonte")
    shortened = stem.removeprefix("(2024-12-31) ").removesuffix(" - Seguradora Horizonte")
    assert title.startswith(shortened)  # cut where a word ends
    assert title[len(shortened)] == " "


def test_a_long_author_is_cut_too() -> None:
    author = "Associação de Moradores e Proprietários do Bairro " * 4
    name = archival_name(NamingDate.parse("2020"), "Minutes", author)
    stem = name.removesuffix(".pdf")
    assert len(stem) <= LIMIT and stem.startswith("(2020) Minutes - Associação")
    assert not stem.endswith((" ", "-"))


def test_the_limit_is_110() -> None:
    assert LIMIT == 110


# --- Original names and folders --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "kept"),
    [
        ("scan_00482.pdf", "scan_00482.pdf"),
        ("Document1.PDF", "Document1.pdf"),
        ("a: b?.pdf", "a - b.pdf"),
        ("  .hidden.pdf", "hidden.pdf"),
    ],
)
def test_an_original_name_is_kept_safe(filename: str, kept: str) -> None:
    assert original_name(filename) == kept


def test_a_very_long_original_name_is_cut() -> None:
    name = original_name("x" * 300 + ".pdf")
    assert name.endswith(".pdf") and len(name.removesuffix(".pdf")) <= LIMIT


def test_folder_names_are_cleaned_like_parts() -> None:
    assert folder_name("BANCO ATLÂNTICO, S.A.") == "Banco Atlântico, S.A"
    assert folder_name("AC/DC") == "AC-DC"
    with pytest.raises(NamingError):
        folder_name("  ...  ")


# --- Clashes -------------------------------------------------------------------------------


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_a_free_name_is_kept(tmp_path: Path) -> None:
    assert free_path(tmp_path, "(2024) Minutes.pdf") == tmp_path / "(2024) Minutes.pdf"


def test_a_different_file_of_the_same_name_gets_a_number(tmp_path: Path) -> None:
    (tmp_path / "(2024) Minutes.pdf").write_bytes(b"one")
    (tmp_path / "(2024) Minutes (2).pdf").write_bytes(b"two")
    found = free_path(tmp_path, "(2024) Minutes.pdf", sha256=_sha(b"three"))
    assert found == tmp_path / "(2024) Minutes (3).pdf"


def test_the_same_file_is_recognised(tmp_path: Path) -> None:
    (tmp_path / "(2024) Minutes.pdf").write_bytes(b"one")
    (tmp_path / "(2024) Minutes (2).pdf").write_bytes(b"two")
    found = free_path(tmp_path, "(2024) Minutes.pdf", sha256=_sha(b"two"))
    assert found == tmp_path / "(2024) Minutes (2).pdf"


def test_without_a_hash_any_existing_file_is_a_clash(tmp_path: Path) -> None:
    (tmp_path / "Document1.pdf").write_bytes(b"one")
    assert free_path(tmp_path, "Document1.pdf") == tmp_path / "Document1 (2).pdf"
