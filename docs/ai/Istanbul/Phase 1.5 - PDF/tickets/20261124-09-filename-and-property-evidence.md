---
id: 20261124-09-filename-and-property-evidence
title: Filename and property evidence
type: feature
priority: high
status: in-progress
created: 2026-11-24
updated: 2026-11-24
closed:
notes: ''
parent:
depends_on:
- 20261124-03-migration-6-and-document-records
subtasks: []
plan_status: approved
current_task: T01
---
## Description

Deterministic evidence from the original filename (dates and partial dates, amounts, numbers, known authors, type words, uninformative patterns) and from the PDF's properties, plus dates in the text; used by the import for the provisional date and author.

## Acceptance criteria

- [ ] Descriptive, uninformative and misleading fixture filenames give the facts their known answers name
- [ ] Properties are read, with producer noise ignored as an author
- [ ] Facts are stored as `document_fields` with source `original_filename` or `pdf_metadata`
- [ ] The import files a document by these when date and author are both known

## Context

Phase 1.5 - PDF Tasks Breakdown item 9. See `(2026-11-24) Phase 1.5 - PDF Requirements.md`. Requirements: *Components* (Filename and property evidence); D11.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: approved
Current task: T01

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
- [ ] done

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
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
