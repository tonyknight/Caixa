---
id: 20261124-09-filename-and-property-evidence
title: Filename and property evidence
type: feature
priority: high
status: done
created: 2026-11-24
updated: 2026-11-24
closed: 2026-11-24
notes: 'Done: filename, property and text-date evidence; provisional filing by name.'
parent:
depends_on:
- 20261124-03-migration-6-and-document-records
subtasks: []
plan_status: done
---
## Description

Deterministic evidence from the original filename (dates and partial dates, amounts, numbers, known authors, type words, uninformative patterns) and from the PDF's properties, plus dates in the text; used by the import for the provisional date and author.

## Acceptance criteria

- [x] Descriptive, uninformative and misleading fixture filenames give the facts their known answers name
- [x] Properties are read, with producer noise ignored as an author
- [x] Facts are stored as `document_fields` with source `original_filename` or `pdf_metadata`
- [x] The import files a document by these when date and author are both known

## Context

Phase 1.5 - PDF Tasks Breakdown item 9. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Filename and property evidence); D11.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/documents/evidence.py`, deterministic, with no model.

- `read_filename(name, known_authors)` gives `FilenameEvidence`:
  - dates found, each with its value, precision and the text it came from: `2024-11-30`,
    `2024_11_30`, `20241130`, `2024-11`, `November 2024` / `novembro de 2024` / `Nov 2024`, a
    year;
  - amounts (`450.00`, `23,40`);
  - a cheque number (`Check 1042`, `cheque nº 1042`) and an invoice number;
  - type words (statement/extrato → statement, bill/fatura → bill, invoice/receipt/recibo →
    invoice, check/cheque → cheque, insurance/seguro/policy/apólice → insurance, tax/imposto →
    tax, agreement/contract/contrato → agreement, deed/escritura → property_record,
    exame/análises/lab → medical, letter/carta → correspondence);
  - an author: a known author named in it, else the last ` - ` part that is words (not for a
    cheque, whose ` - ` parts name the payee);
  - the title left once the date, author, amounts and separators are taken out;
  - whether the name says anything: `scan_00482`, `Document1`, `download`, `IMG_20241115`, digits
    or a hash do not.
- `read_properties(properties)`:
  - title, unless it is a placeholder (`Untitled`, a `.doc` file name, `Microsoft Word - …`);
  - author, unless it is noise (`admin`, `user`, `Microsoft Office User`, a program's or a
    scanner's name);
  - subject, keywords;
  - creation and modification dates as dates. These are recorded, and never name a document.
- `text_dates(pages)`: dates written in the page text (`2024-11-30`, `30/11/2024`, `November 30,
  2024`, `30 de novembro de 2024`, `12/03/2024` read day first), each with its page and text, at
  most 20.
- `provisional_facts(filename, properties)`: the date, title and author an import can file by
  before any model reads the document. The date is the filename's (one date, or the most precise
  when they agree). The author is the filename's, else the properties'. The title is the
  filename's leftover words (at least three letters), else the type word's label. All three are
  needed; otherwise None (Unrecognized).

The import records every fact as `document_fields` (source `original_filename`, `pdf_metadata`,
or `pdf_content`/`ocr` for text dates, with the matched text as evidence and the page) and files by
`provisional_facts`, with known authors from the master. An author it files by is created with that
name.

### T01: Reading filenames, properties and dates in text

- `caixa/documents/evidence.py`.
- Tests (`tests/test_documents_evidence.py`):
  - every fixture's filename gives what its answers name (dates and precision, the cheque number
    and amount, type words, the author after ` - `, informative or not);
  - the misleading `2022 Car Insurance.pdf` gives year 2022 and type insurance (the conflict is
    for reconciliation);
  - placeholder and noise properties are dropped (`Untitled`, `admin`, `Microsoft Office User`);
  - text dates in both languages with their pages;
  - `provisional_facts` for the statement (filename date and properties author), the insurance
    renewal (date and author from the filename), and None for the property tax bill (author
    noise) and the cheque (no date).
- Verify: `python -m pytest -q tests/test_documents_evidence.py`
- [x] done

### T02: Evidence in the import

- `caixa/documents/importing.py`: fields recorded, provisional filing with known authors.
- Tests (`tests/test_pdf_collector.py`, `tests/test_documents_evidence.py`):
  - an import of the family files the statement to
    `2024/Banco Atlântico/(2024-11) Checking Statement - Banco Atlântico.pdf` and the insurance
    renewal to `2024/Seguradora Horizonte/…`, the rest to Unrecognized under their own names;
  - fields carry their sources and evidence;
  - the original filename stays on the record;
  - a second import changes nothing.
- Verify: `python -m pytest -q tests/test_documents_evidence.py tests/test_pdf_collector.py tests/test_documents_search.py && python -m mypy --python-version 3.12 caixa`
- [x] done

## Completion report

- **Outcome:** `caixa/documents/evidence.py` reads, without a model:
  - **filenames**: dates at their precision (ISO, underscores, compact, month names in English
    and Portuguese, years), amounts, cheque and invoice numbers, type words in both languages, an
    author (a known one, or the last ` - ` part that is not a type word, never a cheque's payee),
    the leftover title, and whether the name says anything;
  - **properties**: placeholders and noise dropped; creation and modification dates recorded,
    never naming;
  - **dates in page text**: day first, with page and source, at most 20.

  The import records every fact as a field with its source, evidence and page. It files by
  `provisional_facts` (the filename's date; the filename's or the properties' author; a title):
  the statement goes to `2024/Banco Atlântico/(2024-11) Checking Statement - Banco Atlântico.pdf`
  and the renewal to `2024/Seguradora Horizonte/…`, the rest to Unrecognized.
- **Files:**
  - new: `caixa/documents/evidence.py`, `tests/test_documents_evidence.py`;
  - changed: `caixa/documents/importing.py`, `caixa/documents/records.py` (`author_names`),
    `tests/test_pdf_collector.py` (two documents are now filed by name),
    `tests/fixtures/pdf_family.py`.
- **Errors:**
  - The fixture answers called three names uninformative that name their type; corrected.
  - An author before a type word (`2024-11 - Banco Atlântico - statement`) was missed; the rule
    now takes the last part that is not only type words.
- **Verify:**
  - `python -m pytest -q`: 1794 passed, 1 skipped.
  - mypy (3.12 target): only the 8 baseline errors.

## Review

### 2026-11-24: b7a310d..d1c71bb (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only.

- **Minor:** a slash date in text is read day first unless only month-first makes sense;
  US-style `03/12/2024` is read as 3 December. The model's reading and reconciliation weigh it
  later.
- **Minor:** `date_kind` is `filename` for documents filed by their name until enrichment gives
  the real kind.
- **Minor:** the noise-author list treats any author naming a program (`Microsoft`, `Adobe`) as
  noise, so a real invoice from such a company loses its property author (the text still names
  it).
- **Spec:** D11 met; every acceptance criterion met.
- **TDD:** RED (`ModuleNotFoundError: caixa.documents.evidence`; the import tests before the
  wiring) before each GREEN.
- **Commits:** `20261124-09 T01/T02: …`, authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.
