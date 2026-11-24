"""The synthetic PDF family: the documents Caixa's PDF tests import, inspect, OCR and classify.

`build_pdf_family(out_dir)` writes every PDF with PyMuPDF and returns a `PdfFamily` whose
`documents` describe each file and what is known about it (its *known answers*): the class of every
page, the document's type, title, author and naming date, its key fields, the words a search must
find and on which page, and whether its filename contradicts its contents. The same answers are
written to `answers.json` beside the files.

Beside them are the files an import must survive (`_awkward`): a statement locked with a password
(`PASSWORD`), a policy with only an owner password, a damaged scan, a text file named `.pdf`, an
exact copy of the statement in `Arquivo/2024/`, the same statement saved again (same text,
different bytes) and a `notes.txt`. `zip_family` puts the whole folder in a zip.

How each kind of page is made:

- **text**: a digital page, drawn with the base-14 fonts (WinAnsi: Portuguese letters, no "€").
- **needs_ocr**: a scanned page: the digital page rendered at 200 dpi in grey with a little
  deterministic noise, placed as the page's only image; it carries no text.
- **ocr_layer**: a scanned page with the same words over it in render mode 3 (invisible), as OCR
  software leaves them; a *poor* layer (kind `poor_ocr`) carries garbled words instead.
- **broken_text**: a digital page whose font has a `ToUnicode` map sending every code into the
  Private Use Area: it looks like text, and extracting it gives garbage.
- **blank**: nothing drawn.

Everyone in these documents is from the synthetic family (Maria Costa, Ana and João Costa, Rui
Pereira); every institution is invented. Two builds are byte-identical, except encrypted files
(AES carries a random IV).
"""

from __future__ import annotations

import json
import shutil
import zipfile
import zlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
import pymupdf

#: Fixed dates and producer, so a build does not depend on the clock.
FIXED_DATE = "D:20241201120000Z"
PRODUCER = "Caixa test fixtures"
#: The password of the locked statement (its owner password is `OWNER_PASSWORD`).
PASSWORD = "segredo"
OWNER_PASSWORD = "dono-da-caixa"
#: Page size (A4, points) and the scan resolution.
A4 = (595, 842)
SCAN_DPI = 200

CATEGORIES = {
    "statement": "financial",
    "cheque": "financial",
    "bill": "financial",
    "invoice": "financial",
    "insurance": "financial",
    "tax": "financial",
    "agreement": "legal",
    "property_record": "legal",
    "medical": "personal",
    "personal_record": "personal",
    "correspondence": "correspondence",
    "business": "business",
    "other": "other",
}


@dataclass(frozen=True)
class PdfFixture:
    """One file of the family and its known answers."""

    path: str  # relative to the family's folder, with "/"
    kind: str  # digital | scanned | mixed | ocr_layer | poor_ocr | broken_text | …
    pages: tuple[str, ...]  # the class of each page
    language: str = "en"
    type: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = (
        None  # the naming date, at its precision ("2024", "2024-11", "2024-11-30")
    )
    precision: Optional[str] = None  # day | month | year
    date_kind: Optional[str] = (
        None  # statement_end | issue | written | tax_year | coverage_start | …
    )
    fields: dict[str, Any] = field(default_factory=dict)
    people: tuple[str, ...] = ()  # people of the family named in it
    words: dict[str, int] = field(default_factory=dict)  # word or phrase → page index (from 0)
    conflicts: tuple[str, ...] = ()  # what the filename gets wrong ("year", "type", …)
    filename_informative: bool = True
    duplicate_of: Optional[str] = None  # the same bytes as this fixture's path
    same_text_as: Optional[str] = None  # different bytes, the same text

    @property
    def category(self) -> Optional[str]:
        return CATEGORIES.get(self.type or "")

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    def answers(self) -> dict[str, Any]:
        data = asdict(self)
        data["category"] = self.category
        return data


@dataclass
class PdfFamily:
    root: Path
    documents: list[PdfFixture]

    def get(self, name: str) -> PdfFixture:
        """The fixture whose file is called `name`."""
        for fixture in self.documents:
            if fixture.name == name:
                return fixture
        raise KeyError(name)


# --- Pages -------------------------------------------------------------------------------------


def _write_lines(page: pymupdf.Page, lines: Sequence[str], render_mode: int = 0) -> None:
    """The document's lines from the top: the first as a heading, the rest as body text."""
    y = 80.0
    for number, line in enumerate(lines):
        size = 16 if number == 0 else 12
        page.insert_text(
            (60, y), line, fontname="hebo" if number == 0 else "helv", fontsize=size,
            render_mode=render_mode,
        )  # fmt: skip
        y += size + 10


def _scan(lines: Sequence[str], size: tuple[float, float]) -> pymupdf.Pixmap:
    """A grey picture of the lines, as a scanner would make it (with deterministic specks)."""
    paper = pymupdf.open()
    page = paper.new_page(width=size[0], height=size[1])
    _write_lines(page, lines)
    picture = page.get_pixmap(dpi=SCAN_DPI, colorspace=pymupdf.csGRAY)
    pixels = np.frombuffer(picture.samples, dtype=np.uint8).reshape(picture.height, picture.width)
    seed = zlib.crc32("\n".join(lines).encode("utf-8"))
    rng = np.random.default_rng(seed)
    specks = (rng.random(pixels.shape) < 0.004) * rng.integers(40, 120, pixels.shape)
    scanned = np.clip(pixels.astype(np.int16) - specks - 6, 0, 255).astype(np.uint8)
    paper.close()
    return pymupdf.Pixmap(pymupdf.csGRAY, picture.width, picture.height, scanned.tobytes(), False)


def _garble(line: str) -> str:
    """What a poor OCR engine makes of a line: letters confused, symbols where letters were."""
    swaps = {"e": "c", "a": "@", "o": "0", "l": "1", "i": "!", "n": "rn", "s": "$", "t": "+"}
    return "".join(swaps.get(ch, ch) for ch in line) + " ~~"


#: Every code a simple font can draw, sent to the Private Use Area.
BROKEN_CMAP = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CMapName /CaixaBroken def
1 begincodespacerange <00> <FF> endcodespacerange
1 beginbfrange <00> <FF> <E000> endbfrange
endcmap
CMapName currentdict /CMap defineresource pop
end
end"""


def _break_text(doc: pymupdf.Document, page: pymupdf.Page) -> None:
    """Give the page's fonts a `ToUnicode` map into the Private Use Area."""
    cmap = doc.get_new_xref()
    doc.update_object(cmap, "<<>>")
    doc.update_stream(cmap, BROKEN_CMAP)
    for font in page.get_fonts():
        doc.xref_set_key(font[0], "ToUnicode", f"{cmap} 0 R")


@dataclass(frozen=True)
class _Page:
    kind: str  # text | needs_ocr | ocr_layer | poor_ocr | broken_text | blank
    lines: tuple[str, ...] = ()
    size: tuple[float, float] = A4
    rotation: int = 0

    @property
    def page_class(self) -> str:
        return "ocr_layer" if self.kind == "poor_ocr" else self.kind


def _page(*lines: str, kind: str = "text", **extra: Any) -> _Page:
    return _Page(kind, tuple(lines), **extra)


def _document(
    pages: Sequence[_Page], properties: Optional[dict[str, str]] = None
) -> pymupdf.Document:
    doc = pymupdf.open()
    for spec in pages:
        page = doc.new_page(width=spec.size[0], height=spec.size[1])
        if spec.kind in ("text", "broken_text"):
            _write_lines(page, spec.lines)
            if spec.kind == "broken_text":
                _break_text(doc, page)
        elif spec.kind in ("needs_ocr", "ocr_layer", "poor_ocr"):
            page.insert_image(page.rect, pixmap=_scan(spec.lines, spec.size))
            if spec.kind != "needs_ocr":
                words = spec.lines if spec.kind == "ocr_layer" else [_garble(x) for x in spec.lines]
                _write_lines(page, words, render_mode=3)
        if spec.rotation:
            page.set_rotation(spec.rotation)
    metadata = {
        "producer": PRODUCER,
        "creator": "",
        "creationDate": FIXED_DATE,
        "modDate": FIXED_DATE,
        "title": "",
        "author": "",
        "subject": "",
        "keywords": "",
    }
    metadata.update(properties or {})
    doc.set_metadata(metadata)
    return doc


def _save(doc: pymupdf.Document, path: Path, **options: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path, garbage=3, deflate=True, no_new_id=True, **options)
    doc.close()


# --- The family --------------------------------------------------------------------------------

STATEMENT_PAGES = (
    _page(
        "Banco Atlântico",
        "Checking Statement",
        "Maria Costa, Rua das Flores 12, Porto",
        "Account ending 4821",
        "Statement period: November 1, 2024 to November 30, 2024",
        "Opening balance: 2,310.55 EUR",
        "Closing balance: 1,987.20 EUR",
    ),
    _page(
        "Transactions",
        "2024-11-03  Supermercado Sol  -54.10",
        "2024-11-15  Cheque 1042  -450.00",
        "2024-11-28  Salary  +1,820.00",
        "Page 2 of 2",
    ),
)

STATEMENT = PdfFixture(
    path="2024-11 Banco Atlântico Checking Statement.pdf",
    kind="digital",
    pages=("text", "text"),
    type="statement",
    title="Checking Statement",
    author="Banco Atlântico",
    date="2024-11-30",
    precision="day",
    date_kind="statement_end",
    fields={
        "institution": "Banco Atlântico",
        "account_type": "checking",
        "account_suffix": "4821",
        "period": ["2024-11-01", "2024-11-30"],
        "opening_balance": "2,310.55",
        "closing_balance": "1,987.20",
    },
    people=("Maria Costa",),
    words={"4821": 0, "Supermercado Sol": 1, "1,987.20": 0},
)


def _family() -> list[tuple[PdfFixture, Sequence[_Page], dict[str, str]]]:
    """Every fixture, the pages it is drawn from and the properties it carries."""
    return [
        (STATEMENT, STATEMENT_PAGES, {"title": "Statement", "author": "Banco Atlântico"}),
        (
            PdfFixture(
                path="scan_00482.pdf",
                kind="scanned",
                pages=("needs_ocr",),
                language="pt",
                type="bill",
                title="Fatura de Água",
                author="Águas do Vale",
                date="2024-03-12",
                precision="day",
                date_kind="issue",
                fields={
                    "provider": "Águas do Vale",
                    "amount_due": "23,40",
                    "billing_period": ["2024-02-01", "2024-02-29"],
                },
                people=("Maria Costa",),
                words={"77812": 0},
                filename_informative=False,
            ),
            [
                _page(
                    "Aguas do Vale",
                    "Fatura de agua",
                    "Cliente: Maria Costa",
                    "Contador 77812",
                    "Data de emissao: 12/03/2024",
                    "Periodo: 01/02/2024 a 29/02/2024",
                    "Total a pagar: 23,40 EUR",
                    kind="needs_ocr",
                )
            ],
            {},
        ),
        (
            PdfFixture(
                path="Check 1042 - Canalizações Rui - 450.00.pdf",
                kind="scanned",
                pages=("needs_ocr",),
                type="cheque",
                title="Cheque 1042",
                author="Maria Costa",
                date="2024-11-15",
                precision="day",
                date_kind="written",
                fields={"number": "1042", "payee": "Canalizacoes Rui", "amount": "450.00"},
                people=("Maria Costa",),
                words={"1042": 0},
            ),
            [
                _page(
                    "Banco Atlantico",
                    "Cheque No. 1042",
                    "Date: 2024-11-15",
                    "Pay to the order of: Canalizacoes Rui",
                    "Amount: 450.00 EUR",
                    "Four hundred fifty euros",
                    "Signed: Maria Costa",
                    kind="needs_ocr",
                )
            ],
            {},
        ),
        (
            PdfFixture(
                path="2023 Property Tax Bill.pdf",
                kind="digital",
                pages=("text", "blank"),
                type="tax",
                title="Property Tax Bill",
                author="Câmara Municipal de Vila Nova",
                date="2022",
                precision="year",
                date_kind="tax_year",
                fields={
                    "issuer": "Câmara Municipal de Vila Nova",
                    "tax_year": "2022",
                    "issued": "2023-04-20",
                    "amount_due": "312.00",
                },
                people=("Maria Costa",),
                words={"Tax year 2022": 0},
            ),
            [
                _page(
                    "Câmara Municipal de Vila Nova",
                    "Property Tax Statement",
                    "Tax year 2022",
                    "Issued: April 20, 2023",
                    "Owner: Maria Costa",
                    "Property: Rua das Flores 12, Porto",
                    "Amount due: 312.00 EUR",
                    "Due by: May 31, 2023",
                ),
                _page(kind="blank"),
            ],
            # wrong properties: a placeholder title, a meaningless author, a creation date years off
            {"title": "Untitled", "author": "admin", "creationDate": "D:20190101000000Z"},
        ),
        (
            PdfFixture(
                path="Document1.pdf",
                kind="digital",
                pages=("text",),
                language="pt",
                type="correspondence",
                title="Carta de João Costa",
                author="João Costa",
                date="2019-06-02",
                precision="day",
                date_kind="letter",
                people=("João Costa", "Maria Costa"),
                words={"Braga": 0},
                filename_informative=False,
            ),
            [
                _page(
                    "Porto, 2 de junho de 2019",
                    "Querida Maria,",
                    "Escrevo-te para contar que a casa de Braga ficou pronta.",
                    "Os azulejos da cozinha chegaram na semana passada.",
                    "Um abraço,",
                    "João Costa",
                )
            ],
            {"creator": "Microsoft Word", "author": "Microsoft Office User"},
        ),
        (
            PdfFixture(
                path="download.pdf",
                kind="mixed",
                pages=("text", "needs_ocr"),
                type="invoice",
                title="Invoice FT 2024/118",
                author="Livraria Estrela",
                date="2024-02-09",
                precision="day",
                date_kind="issue",
                fields={"vendor": "Livraria Estrela", "number": "FT 2024/118", "total": "37.80"},
                people=("Maria Costa",),
                words={"FT 2024/118": 0, "55031": 1},
                filename_informative=False,
            ),
            [
                _page(
                    "Livraria Estrela",
                    "Invoice FT 2024/118",
                    "Date: February 9, 2024",
                    "Customer: Maria Costa",
                    "2 books: A Casa das Marés, O Rio",
                    "Total: 37.80 EUR",
                ),
                _page(
                    "Livraria Estrela",
                    "Payment receipt",
                    "Paid 37.80 EUR by card",
                    "Ref 55031",
                    kind="needs_ocr",
                ),
            ],
            {"producer": "Estrela POS 3.1"},
        ),
        (
            PdfFixture(
                path="2024-06-15 Insurance Renewal - Seguradora Horizonte.pdf",
                kind="ocr_layer",
                pages=("ocr_layer",),
                type="insurance",
                title="Home Insurance Renewal",
                author="Seguradora Horizonte",
                date="2024-07-01",
                precision="day",
                date_kind="coverage_start",
                fields={
                    "insurer": "Seguradora Horizonte",
                    "policy_number": "HZ-55120",
                    "coverage_period": ["2024-07-01", "2025-06-30"],
                },
                people=("Maria Costa",),
                words={"HZ-55120": 0},
            ),
            [
                _page(
                    "Seguradora Horizonte",
                    "Home Insurance Renewal",
                    "Policy number HZ-55120",
                    "Insured: Maria Costa",
                    "Coverage: July 1, 2024 to June 30, 2025",
                    "Issued: June 15, 2024",
                    "Annual premium: 245.00 EUR",
                    kind="ocr_layer",
                )
            ],
            {"creator": "ScanSnap Manager"},
        ),
        (
            PdfFixture(
                path="old_ocr_contract.pdf",
                kind="poor_ocr",
                pages=("ocr_layer", "ocr_layer"),
                type="agreement",
                title="Rental Agreement",
                author=None,
                date="2021-09-30",
                precision="day",
                date_kind="execution",
                fields={
                    "parties": ["Maria Costa", "Rui Pereira"],
                    "subject": "Rua do Sol 8, Braga",
                },
                people=("Maria Costa", "Rui Pereira"),
                words={"Rental Agreement": 0},
            ),
            [
                _page(
                    "Rental Agreement",
                    "Between Maria Costa (landlord) and Rui Pereira (tenant)",
                    "Property: Rua do Sol 8, Braga",
                    "Monthly rent: 650.00 EUR",
                    kind="poor_ocr",
                ),
                _page(
                    "Clause 1. The tenant pays the rent by the 8th of each month.",
                    "Signed in Braga on September 30, 2021",
                    "Maria Costa        Rui Pereira",
                    kind="poor_ocr",
                ),
            ],
            {},
        ),
        (
            PdfFixture(
                path="extrato_marco.pdf",
                kind="broken_text",
                pages=("broken_text",),
                language="pt",
                type="statement",
                title="Extrato de Conta",
                author="Banco Atlântico",
                date="2024-03-31",
                precision="day",
                date_kind="statement_end",
                fields={
                    "institution": "Banco Atlântico",
                    "account_suffix": "4821",
                    "closing_balance": "2.104,33",
                },
                people=("Maria Costa",),
                words={"4821": 0},
            ),
            [
                _page(
                    "Banco Atlantico",
                    "Extrato de conta",
                    "Titular: Maria Costa",
                    "Conta terminada em 4821",
                    "Periodo: 1 a 31 de marco de 2024",
                    "Saldo final: 2.104,33 EUR",
                    kind="broken_text",
                )
            ],
            {},
        ),
        (
            PdfFixture(
                path="2022 Car Insurance.pdf",
                kind="digital",
                pages=("text",),
                type="bill",
                title="Electricity Bill",
                author="Energia do Norte",
                date="2024-01-10",
                precision="day",
                date_kind="issue",
                fields={
                    "provider": "Energia do Norte",
                    "billing_period": ["2023-12-01", "2023-12-31"],
                    "amount_due": "88.15",
                },
                people=("Maria Costa",),
                words={"Energia do Norte": 0},
                conflicts=("year", "type"),
            ),
            [
                _page(
                    "Energia do Norte",
                    "Electricity Bill",
                    "Customer: Maria Costa",
                    "Issued: January 10, 2024",
                    "Billing period: December 2023",
                    "Amount due: 88.15 EUR",
                )
            ],
            {},
        ),
        (
            PdfFixture(
                path="receipt_rotated.pdf",
                kind="digital",
                pages=("text",),
                type="invoice",
                title="Receipt 0093",
                author="Café Central",
                date="2024-05-03",
                precision="day",
                date_kind="issue",
                fields={"vendor": "Café Central", "number": "0093", "total": "6.40"},
                words={"Receipt 0093": 0},
            ),
            [
                _page(
                    "Café Central",
                    "Receipt 0093",
                    "3 May 2024",
                    "2 coffees 2.40",
                    "1 cake 4.00",
                    "Total 6.40 EUR",
                    size=(226, 566),
                    rotation=90,
                )
            ],
            {},
        ),
        (
            PdfFixture(
                path="Exame Ana Costa 2020.pdf",
                kind="digital",
                pages=("text",),
                language="pt",
                type="medical",
                title="Resultados de Análises",
                author="Clínica Santa Luzia",
                date="2020-10-14",
                precision="day",
                date_kind="issue",
                people=("Ana Costa",),
                words={"Hemoglobina": 0},
            ),
            [
                _page(
                    "Clínica Santa Luzia",
                    "Resultados de análises",
                    "Paciente: Ana Costa",
                    "Data da colheita: 14/10/2020",
                    "Hemoglobina 13,8 g/dL",
                    "Médico: Dr. Paulo Lima",
                )
            ],
            {},
        ),
    ]


def _awkward(out_dir: Path) -> list[PdfFixture]:
    """The files an import must survive: locked, damaged, false, copied, saved twice."""
    found: list[PdfFixture] = []

    locked = PdfFixture(
        path="extrato_protegido.pdf",
        kind="encrypted",
        pages=("text",),
        language="pt",
        type="statement",
        title="Extrato de Conta",
        author="Banco Atlântico",
        date="2024-02-29",
        precision="day",
        date_kind="statement_end",
        filename_informative=False,
    )
    doc = _document([_page("Banco Atlântico", "Extrato de conta", "Fevereiro de 2024")])
    _save(
        doc, out_dir / locked.path, encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw=PASSWORD, owner_pw=OWNER_PASSWORD,
    )  # fmt: skip
    found.append(locked)

    restricted = PdfFixture(
        path="apolice_restrita.pdf",
        kind="owner_password",
        pages=("text",),
        language="pt",
        type="insurance",
        title="Apólice de Seguro Automóvel",
        author="Seguradora Horizonte",
        date="2023-03-01",
        precision="day",
        date_kind="coverage_start",
        words={"HZ-20877": 0},
        filename_informative=False,
    )
    doc = _document(
        [
            _page(
                "Seguradora Horizonte",
                "Apólice de seguro automóvel HZ-20877",
                "Tomador: Maria Costa",
                "Início: 1 de março de 2023",
            )
        ]
    )
    _save(
        doc, out_dir / restricted.path, encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw=OWNER_PASSWORD, user_pw="",
        permissions=int(pymupdf.PDF_PERM_ACCESSIBILITY | pymupdf.PDF_PERM_PRINT),
    )  # fmt: skip
    found.append(restricted)

    damaged = PdfFixture(path="damaged_scan.pdf", kind="corrupted", pages=())
    scan = _document([_page("Recibo", "Ref 1", kind="needs_ocr")])
    good = scan.tobytes(garbage=3, deflate=True, no_new_id=True)
    scan.close()
    noise = np.random.default_rng(11).integers(0, 256, 4096, dtype=np.uint8).tobytes()
    (out_dir / damaged.path).write_bytes(good[:300] + noise)
    found.append(damaged)

    false = PdfFixture(path="not_really.pdf", kind="not_pdf", pages=())
    (out_dir / false.path).write_text("A note saved with the wrong extension.\n", encoding="utf-8")
    found.append(false)

    archive = out_dir / "Arquivo" / "2024"
    archive.mkdir(parents=True, exist_ok=True)
    copy = PdfFixture(
        path="Arquivo/2024/statement copy.pdf",
        kind="duplicate",
        pages=STATEMENT.pages,
        type=STATEMENT.type,
        title=STATEMENT.title,
        author=STATEMENT.author,
        date=STATEMENT.date,
        precision=STATEMENT.precision,
        date_kind=STATEMENT.date_kind,
        duplicate_of=STATEMENT.path,
    )
    shutil.copyfile(out_dir / STATEMENT.path, out_dir / copy.path)
    found.append(copy)

    again = PdfFixture(
        path="Banco Atlântico November 2024 (1).pdf",
        kind="same_text",
        pages=STATEMENT.pages,
        type=STATEMENT.type,
        title=STATEMENT.title,
        author=STATEMENT.author,
        date=STATEMENT.date,
        precision=STATEMENT.precision,
        date_kind=STATEMENT.date_kind,
        same_text_as=STATEMENT.path,
    )
    downloaded = {"producer": "Banco Atlântico Online 7", "modDate": "D:20241205093000Z"}
    _save(_document(STATEMENT_PAGES, downloaded), out_dir / again.path)
    found.append(again)

    (out_dir / "Arquivo" / "notes.txt").write_text(
        "Papers to keep: the house deed, the insurance, the statements.\n", encoding="utf-8"
    )
    return found


def zip_family(folder: Path, zip_path: Path) -> Path:
    """The family's files (not `answers.json`) in a zip, with their folders, as an owner would
    send them; entries in a fixed order with a fixed date."""
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "answers.json")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipped:
        for file in files:
            entry = zipfile.ZipInfo(file.relative_to(folder).as_posix(), (2024, 12, 1, 12, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(entry, file.read_bytes())
    return zip_path


def build_pdf_family(out_dir: Path) -> PdfFamily:
    """Write every PDF of the family into `out_dir`, with `answers.json`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    documents: list[PdfFixture] = []
    for fixture, pages, properties in _family():
        _save(_document(pages, properties), out_dir / fixture.path)
        documents.append(fixture)
    documents.extend(_awkward(out_dir))
    answers = [fixture.answers() for fixture in documents]
    (out_dir / "answers.json").write_text(
        json.dumps(answers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return PdfFamily(out_dir, documents)
