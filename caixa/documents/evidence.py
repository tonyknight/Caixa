"""What a document's filename, its PDF properties and the dates in its text say, read without a
model.

A filename is evidence: `2024-11 Banco Atlântico Checking Statement.pdf` says when, who and what.
`scan_00482.pdf` says nothing, and `read_filename` knows the difference. PDF properties are often
empty or wrong (`Untitled`, `admin`, `Microsoft Office User`), so `read_properties` drops what is
placeholder or noise; their dates are recorded but never name a document. `text_dates` finds the
dates written on the pages, each with its page.

`provisional_facts` is what an import can file a document by before any model reads it: a date
from the filename, an author from the filename or the properties, and a title. Without all three
the document waits in `Unrecognized/`. Every fact is also recorded, with where it came from, for
the model and for reconciliation to weigh.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path
from typing import Iterable, Optional

from caixa.documents.archive import Facts

MONTHS = {
    **{m: i for i, m in enumerate(
        "january february march april may june july august september october november december"
        .split(), start=1)},
    **{m: i for i, m in enumerate(
        "jan feb mar apr may jun jul aug sep oct nov dec".split(), start=1)},
    **{m: i for i, m in enumerate(
        "janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro"
        .split(), start=1)},
    **{m: i for i, m in enumerate(
        "jan fev mar abr mai jun jul ago set out nov dez".split(), start=1)},
    "sept": 9,
}  # fmt: skip
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))

#: Words that say what a document is, by type (accents and case aside).
TYPE_WORDS = {
    "statement": "statement", "statements": "statement", "extrato": "statement",
    "extratos": "statement", "bill": "bill", "fatura": "bill", "factura": "bill",
    "invoice": "invoice", "receipt": "invoice", "recibo": "invoice", "talao": "invoice",
    "check": "cheque", "cheque": "cheque", "insurance": "insurance", "seguro": "insurance",
    "policy": "insurance", "apolice": "insurance", "tax": "tax", "imposto": "tax", "irs": "tax",
    "agreement": "agreement", "contract": "agreement", "contrato": "agreement",
    "arrendamento": "agreement", "lease": "agreement", "deed": "property_record",
    "escritura": "property_record", "exame": "medical", "exames": "medical",
    "analises": "medical", "lab": "medical", "medical": "medical", "letter": "correspondence",
    "carta": "correspondence",
}  # fmt: skip
#: How a type names a document when nothing better is known.
TYPE_LABELS = {
    "statement": "Statement", "bill": "Bill", "invoice": "Invoice", "cheque": "Cheque",
    "insurance": "Insurance", "tax": "Tax Document", "agreement": "Agreement",
    "property_record": "Property Record", "medical": "Medical Record",
    "correspondence": "Letter",
}  # fmt: skip

_UNINFORMATIVE = re.compile(
    r"^(?:(?:scan(?:ned)?(?: document)?|img|image|dsc|pxl|photo|doc|document|download|file|"
    r"untitled|print|copy|new document|output|tmp|temp|pdf)[\s_\-.]*\(?\d*\)?|[\d_\-\s.()]+|"
    r"[0-9a-f]{8,})$"
)
_PLACEHOLDER_TITLES = {"untitled", "document", "title", "pdf", "sem titulo", "sem título"}
_NOISE_AUTHORS = {
    "admin", "administrator", "user", "owner", "author", "unknown", "utilizador", "usuario",
    "usuário", "microsoft office user", "default", "guest",
}  # fmt: skip
_PROGRAMS = re.compile(
    r"\b(?:acrobat|adobe|scansnap|scanner|epson|canon|hp|xerox|brother|ricoh|microsoft|word|"
    r"excel|libreoffice|openoffice|quartz|ghostscript|pdf|office|writer|printer|distiller)\b",
    re.IGNORECASE,
)
#: Whole names of the programs that make PDFs (D31). A PDF's Author property, or a model's answer,
#: that is one of these names the program, not the sender. Whole names only: a company such as
#: "Microsoft" or "Canon" may send a bill.
PROGRAM_NAMES = frozenset({
    "brite", "brite bill", "pro api", "pro document", "adobe acrobat", "acrobat distiller",
    "adobe acrobat distiller", "adobe pdf library", "adobe indesign", "microsoft word",
    "microsoft excel", "microsoft powerpoint", "microsoft print to pdf", "microsoft reporting services",
    "libreoffice", "openoffice", "openoffice org", "ghostscript", "gpl ghostscript",
    "quartz pdfcontext", "mac os x quartz pdfcontext", "scansnap", "scansnap manager",
    "epson scan", "canon scan", "pdf printer", "pdfcreator", "wkhtmltopdf", "itext", "pdfsharp",
    "reportlab", "crystal reports", "skia pdf", "chromium", "google docs",
})  # fmt: skip
_VERSION = re.compile(r"^v?\d[\d.]*$")


def is_program(name: Optional[str]) -> bool:
    """Whether `name` is, as a whole, the name of a program that makes PDFs (see
    `PROGRAM_NAMES`); a version number after it does not count."""
    words = re.sub(r"[^a-z0-9]+", " ", _plain(name or "")).split()
    words = [word for word in words if not _VERSION.match(word)]
    return bool(words) and " ".join(words) in PROGRAM_NAMES


_FILE_NAME = re.compile(
    r"\.(?:docx?|xlsx?|pptx?|pdf|txt|odt|rtf|pages|jpe?g|png|tiff?|html?)$", re.I
)
_AMOUNT = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d{3})*[.,]\d{2}(?![\d])")
_CHEQUE = re.compile(r"\b(?:check|cheque)\s*(?:n[º°o]\.?|no\.?|#)?\s*(\d{2,})", re.IGNORECASE)
_INVOICE = re.compile(
    r"\b(?:invoice|inv|fatura|factura)\s*(?:n[º°o]\.?|no\.?|#)?\s*([A-Z]{0,3}\s?\d[\w/\-]*)",
    re.IGNORECASE,
)
_COPY = re.compile(r"\s*\(\d+\)$")
_SEPARATOR = re.compile(r"\s+[-–—]\s+")
#: The most dates `text_dates` returns.
MOST_DATES = 20


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def _plain_with_map(text: str) -> tuple[str, list[int]]:
    """`text` without accents or case, and for each of its characters the index it came from."""
    plain: list[str] = []
    origin: list[int] = []
    for index, ch in enumerate(text):
        for part in _plain(ch):
            plain.append(part)
            origin.append(index)
    return "".join(plain), origin


def _find(text: str, needle: str) -> Optional[tuple[int, int]]:
    """Where `needle` is in `text` as whole words, accents and case aside (original indices)."""
    plain, origin = _plain_with_map(text)
    match = re.search(rf"(?<!\w){re.escape(_plain(needle))}(?!\w)", plain)
    if not match or not origin:
        return None
    start = origin[match.start()]
    end = origin[match.end() - 1] + 1
    return start, end


def _valid(year: int, month: int, day: int = 1) -> bool:
    try:
        _date(year, month, day)
    except ValueError:
        return False
    return 1900 <= year <= 2099


@dataclass(frozen=True)
class FoundDate:
    value: str  # YYYY, YYYY-MM or YYYY-MM-DD
    precision: str  # year | month | day
    text: str  # as written


@dataclass
class FilenameEvidence:
    name: str
    informative: bool
    dates: list[FoundDate] = field(default_factory=list)
    amounts: list[str] = field(default_factory=list)
    cheque_number: Optional[str] = None
    invoice_number: Optional[str] = None
    types: list[str] = field(default_factory=list)
    author: Optional[str] = None
    title: Optional[str] = None

    @property
    def date(self) -> Optional[FoundDate]:
        """The filename's date: the most precise, when every other date agrees with it."""
        if not self.dates:
            return None
        best = max(self.dates, key=lambda d: len(d.value))
        if all(best.value.startswith(d.value) for d in self.dates):
            return best
        return None


def _dates_in_name(stem: str) -> tuple[list[FoundDate], str]:
    """The dates written in a filename, and the name with them blanked out."""
    found: list[FoundDate] = []
    rest = stem

    def take(pattern: str, make: object, flags: int = 0) -> None:
        nonlocal rest
        for match in list(re.finditer(pattern, rest, flags)):
            made = make(match)  # type: ignore[operator]
            if made is not None:
                found.append(FoundDate(made[0], made[1], match.group(0)))
                rest = rest[: match.start()] + " " * len(match.group(0)) + rest[match.end() :]

    def day(m: re.Match[str]) -> Optional[tuple[str, str]]:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (f"{y:04d}-{mo:02d}-{d:02d}", "day") if _valid(y, mo, d) else None

    def month(m: re.Match[str]) -> Optional[tuple[str, str]]:
        y, mo = int(m.group(1)), int(m.group(2))
        return (f"{y:04d}-{mo:02d}", "month") if _valid(y, mo) else None

    def named(m: re.Match[str]) -> Optional[tuple[str, str]]:
        mo, y = MONTHS[_plain(m.group(1)).rstrip(".")], int(m.group(2))
        return (f"{y:04d}-{mo:02d}", "month") if _valid(y, mo) else None

    def year(m: re.Match[str]) -> Optional[tuple[str, str]]:
        return (m.group(1), "year") if _valid(int(m.group(1)), 1) else None

    take(r"(?<!\d)(\d{4})[-_.](\d{2})[-_.](\d{2})(?!\d)", day)
    take(r"(?<![\dA-Za-z])(\d{4})(\d{2})(\d{2})(?!\d)", day)
    take(r"(?<!\d)(\d{4})[-_.](\d{2})(?![\d])", month)
    plain = _plain(rest)
    for match in list(re.finditer(rf"\b({_MONTH})\.?\s+(?:de\s+)?(\d{{4}})\b", plain)):
        made = named(match)
        if made is not None:
            found.append(FoundDate(made[0], made[1], rest[match.start() : match.end()]))
            rest = rest[: match.start()] + " " * (match.end() - match.start()) + rest[match.end() :]
            plain = _plain(rest)
    take(r"(?<![\d.,])(19\d{2}|20\d{2})(?![\d.,])", year)
    return found, rest


def _wordy(part: str) -> bool:
    letters = sum(ch.isalpha() for ch in part)
    return letters >= 3 and not _AMOUNT.fullmatch(part.strip())


def _tidy(text: str) -> str:
    text = _COPY.sub("", text)
    text = re.sub(r"[_]+", " ", text)
    text = re.sub(r"\s*[-–—]\s*(?=[-–—]|$)", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -–—_.,;:")


def read_filename(name: str, known_authors: Iterable[str] = ()) -> FilenameEvidence:
    """What a filename says (see the module text)."""
    stem = unicodedata.normalize("NFC", Path(name).stem).strip()
    plain_stem = _plain(_COPY.sub("", stem)).strip()
    informative = not _UNINFORMATIVE.match(plain_stem)
    dates, rest = _dates_in_name(stem)
    found = FilenameEvidence(name=name, informative=informative, dates=dates)
    found.amounts = _AMOUNT.findall(rest)
    cheque = _CHEQUE.search(rest)
    found.cheque_number = cheque.group(1) if cheque else None
    invoice = _INVOICE.search(rest)
    found.invoice_number = invoice.group(1).strip() if invoice and not cheque else None
    for word in re.findall(r"[^\W\d_]+", _plain(rest)):
        kind = TYPE_WORDS.get(word)
        if kind and kind not in found.types:
            found.types.append(kind)
    remaining = rest
    for amount in found.amounts:
        remaining = remaining.replace(amount, " ")
    for author in sorted(set(known_authors), key=len, reverse=True):
        span = _find(remaining, author) if author.strip() else None
        if span:
            found.author = author
            remaining = remaining[: span[0]] + " " + remaining[span[1] :]
            break
    if found.author is None and "cheque" not in found.types:
        parts = [p for p in _SEPARATOR.split(remaining.strip(" -–—_")) if p.strip()]
        for part in reversed(parts if len(parts) > 1 else []):
            words = re.findall(r"[^\W\d_]+", _plain(part))
            if _wordy(part) and not all(w in TYPE_WORDS for w in words):
                found.author = _tidy(part)
                remaining = remaining.replace(part, " ", 1)
                break
    title = _tidy(remaining)
    found.title = title if informative and sum(ch.isalpha() for ch in title) >= 3 else None
    return found


@dataclass
class PropertyEvidence:
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    created: Optional[str] = None  # YYYY-MM-DD
    modified: Optional[str] = None


def _property_date(value: Optional[str]) -> Optional[str]:
    match = re.match(r"^(?:D:)?(\d{4})(\d{2})(\d{2})", (value or "").strip())
    if not match:
        return None
    y, m, d = (int(g) for g in match.groups())
    return f"{y:04d}-{m:02d}-{d:02d}" if _valid(y, m, d) else None


def _title(value: str) -> Optional[str]:
    text = value.strip()
    plain = _plain(text)
    if (
        not text
        or plain in _PLACEHOLDER_TITLES
        or plain.startswith(("microsoft word - ", "microsoft excel - ", "microsoft powerpoint - "))
        or _FILE_NAME.search(text)
        or _UNINFORMATIVE.match(plain)
    ):
        return None
    return text


def _author(value: str) -> Optional[str]:
    text = value.strip()
    if not text or _plain(text) in _NOISE_AUTHORS or _PROGRAMS.search(text) or is_program(text):
        return None
    return text


def read_properties(properties: dict[str, str]) -> PropertyEvidence:
    """What a PDF's properties say, without placeholders and noise."""
    keywords = [k.strip() for k in re.split(r"[,;]", properties.get("keywords") or "") if k.strip()]
    return PropertyEvidence(
        title=_title(properties.get("title") or ""),
        author=_author(properties.get("author") or ""),
        subject=(properties.get("subject") or "").strip() or None,
        keywords=keywords,
        created=_property_date(properties.get("creationDate")),
        modified=_property_date(properties.get("modDate")),
    )


@dataclass(frozen=True)
class TextDate:
    value: str  # YYYY-MM-DD
    page: int
    text: str
    source: str  # pdf | ocr


def _dates_in_text(text: str) -> list[tuple[int, str, str]]:
    """(position, YYYY-MM-DD, as written) for every date written in `text`."""
    found: list[tuple[int, str, str]] = []
    plain = _plain(text)

    def add(at: int, y: int, m: int, d: int, written: str) -> None:
        if _valid(y, m, d):
            found.append((at, f"{y:04d}-{m:02d}-{d:02d}", written))

    for match in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", text):
        add(
            match.start(),
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
            match.group(0),
        )
    for match in re.finditer(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])", text):
        first, second, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        day, month = (second, first) if second > 12 >= first else (first, second)
        add(match.start(), y, month, day, match.group(0))
    for match in re.finditer(rf"\b({_MONTH})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", plain):
        add(match.start(), int(match.group(3)), MONTHS[match.group(1)], int(match.group(2)),
            text[match.start() : match.end()])  # fmt: skip
    for match in re.finditer(
        rf"\b(\d{{1,2}})(?:º)?\s+(?:de\s+)?({_MONTH})\.?,?\s+(?:de\s+)?(\d{{4}})\b", plain
    ):
        add(match.start(), int(match.group(3)), MONTHS[match.group(2)], int(match.group(1)),
            text[match.start() : match.end()])  # fmt: skip
    return sorted(found)


def text_dates(pages: Iterable[tuple[int, str, str]]) -> list[TextDate]:
    """Dates written on the pages, given as (page number, text, source), in page order, each
    once per page, at most `MOST_DATES`."""
    found: list[TextDate] = []
    seen: set[tuple[str, int]] = set()
    for page, text, source in pages:
        for _, value, written in _dates_in_text(text or ""):
            if (value, page) in seen:
                continue
            seen.add((value, page))
            found.append(TextDate(value, page, written.strip(), source))
            if len(found) >= MOST_DATES:
                return found
    return found


def _without_author(title: str, author: str) -> str:
    span = _find(title, author)
    if not span:
        return title
    shorter = _tidy(title[: span[0]] + " " + title[span[1] :])
    return shorter if sum(ch.isalpha() for ch in shorter) >= 3 else title


def provisional_facts(filename: FilenameEvidence, properties: PropertyEvidence) -> Optional[Facts]:
    """The date, title and author a document can be filed by before a model reads it: all three,
    or None (it waits in `Unrecognized/`)."""
    date = filename.date
    author = filename.author or properties.author
    if date is None or not author:
        return None
    title = filename.title
    if title:
        title = _without_author(title, author)
    if not title and filename.types:
        title = TYPE_LABELS.get(filename.types[0])
    if not title:
        return None
    return Facts(date=date.value, title=title, author=author)


def lacking(filename: FilenameEvidence, properties: PropertyEvidence) -> list[str]:
    """Why `provisional_facts` gave nothing: `no_date` (or `dates_disagree`, the filename's dates
    not agreeing), `no_author`, `no_title`. Empty when it gave facts."""
    if provisional_facts(filename, properties) is not None:
        return []
    found = []
    if filename.date is None:
        found.append("dates_disagree" if filename.dates else "no_date")
    author = filename.author or properties.author
    if not author:
        found.append("no_author")
    title = filename.title
    if title and author:
        title = _without_author(title, author)
    if not title and not (filename.types and TYPE_LABELS.get(filename.types[0])):
        found.append("no_title")
    return found


__all__ = [
    "FilenameEvidence",
    "FoundDate",
    "MOST_DATES",
    "PropertyEvidence",
    "TYPE_LABELS",
    "TYPE_WORDS",
    "TextDate",
    "lacking",
    "provisional_facts",
    "read_filename",
    "read_properties",
    "text_dates",
]
