# Archival names

How Caixa names a file it brings into a box, whatever collected it. Documents (PDFs) are the first
to use the whole convention. Photos, videos and other file collectors are meant to adopt it later.
It extends what Caixa already does for mail attachments, conversation pages and Cleaned and Reduced
mboxes (`(YYYY-MM-DD) name`, ` (2)` on a clash).

The code is `caixa/naming.py`. The examples at the end of this page are checked against it by
the tests (`tests/test_naming.py`), so this page and Caixa always agree.

## The name

```
(DATE) Title - Author.ext
```

A name a person can read in any folder listing and that sorts by date. The box's database and its
search find a file whatever it is called, so a name is for people, not for finding things.

### Date

- Written at the precision it is known, in parentheses: `(2024-11-30)` for a day, `(2024-11)` for
  a month, `(2024)` for a year.
- A full date is never made up from a partial one. A statement known only by its month is
  `(2024-11)`, not `(2024-11-01)`.
- One date names the file: the one that matters most for what it is. For documents:

  | Type | The date that names it |
  | --- | --- |
  | Statement | the end of its period |
  | Bill, invoice, receipt | the date it was issued |
  | Cheque | the date it was written |
  | Tax document | the tax year (year only) |
  | Insurance | the start of the coverage |
  | Legal agreement | the date it was signed |
  | Letter | the date of the letter |
  | Anything else | its own date, else the date it was issued |

  Every other date a document has (issued, created, effective, due, the period, the tax year) is
  kept in the box's database, each as what it is, and never confused with another. The day a file
  was downloaded or last changed is recorded, but never names it.

### Title

- What the thing is, short: "Checking Statement", "Property Tax Bill", "Cheque 1042 to
  Canalizações Rui".
- In the document's own language.
- It does not repeat the date or the author. `Banco Atlântico Checking Statement` by Banco
  Atlântico is named `Checking Statement - Banco Atlântico`.

### Author

- Who issued, sent or made it: the bank of a statement, the clinic of a lab report, the person who
  wrote a letter or a cheque. Not who it is about, and not who it is addressed to.
- By the author's usual name in the box (Caixa keeps one name for each author and remembers the
  other ways it is written).
- Left out when it is not known: `(2021-09-30) Rental Agreement.pdf`.
- It is also the folder the file is in. It stays in the name so that a file copied out of the box
  still says what it is.

### No tags

Tags (banking, utilities, …) are kept in the box's database, not in names: they can change each
time a document is read again, and every change would rename the file.

### Extension

The file's own extension, in lower case (`.pdf`, `.jpg`).

## Characters

A name has to work on every computer a box may be copied to, so:

- `/`, `\` and `|` become `-` (`Invoice FT 2024/118` → `Invoice FT 2024-118`);
- `:` becomes ` - ` (`Re: a casa` → `Re - a casa`);
- `*`, `?`, `<` and `>` are left out, and `"` becomes `'`;
- control characters are left out, tabs and line breaks become spaces, and runs of spaces become
  one;
- no name starts or ends with a dot, a space or a dash;
- letters are stored in their composed form (NFC), so `é` is one character on every system;
- a part written all in capitals (more than five letters) is given ordinary capitals:
  `ENERGIA DO NORTE` → `Energia do Norte`, with short joining words (`de`, `do`, `da`, `of`,
  `the`, `and`, …) in lower case. Short acronyms (`EDP`) and abbreviations (`S.A.`) stay as they
  are.

## Length

A name is cut after **110 characters**, not counting its extension or a ` (2)`. When it is too long,
the title is shortened first, where a word ends, so the date and the author stay whole. Only when
the author alone is too long is the whole name cut, again at a word.

## Two files with the same name

A different file with a name already used in the same folder gets ` (2)`, then ` (3)`, before its
extension: `(2024) Minutes.pdf`, `(2024) Minutes (2).pdf`. Caixa compares the files' contents
(SHA-256) first, so the same file imported twice is recognised, not numbered.

## Documents Caixa could not name

Documents live in `Documents/<FORMAT>/<YYYY>/<Author>/`, for example
`Documents/PDF/2024/Banco Atlântico/`. The year is the naming date's. Category and type (financial,
statement, …) are not folders, so reclassifying a document never moves it.

A document whose author or date cannot be worked out (from its text, its properties, a model on
this computer, or a date in its filename) goes to `Documents/PDF/Unrecognized/` under its own
name, made safe by the rules above (`scan_00482.pdf`). When its author and date are known, by
Caixa or because the owner typed them, it moves to its year and author folder under its archival
name. A document whose filename and properties already give both is named and filed when it is
imported.

## Examples

<!-- examples -->
| Date | Title | Author | Name |
| --- | --- | --- | --- |
| `2024-11-30` | Checking Statement | Banco Atlântico | `(2024-11-30) Checking Statement - Banco Atlântico.pdf` |
| `2024-11` | Checking Statement | Banco Atlântico | `(2024-11) Checking Statement - Banco Atlântico.pdf` |
| `2022` | Property Tax Bill | Câmara Municipal de Vila Nova | `(2022) Property Tax Bill - Câmara Municipal de Vila Nova.pdf` |
| `2024-11-15` | Cheque 1042 to Canalizações Rui | Maria Costa | `(2024-11-15) Cheque 1042 to Canalizações Rui - Maria Costa.pdf` |
| `2021-09-30` | Rental Agreement | — | `(2021-09-30) Rental Agreement.pdf` |
| `2024-02-09` | Invoice FT 2024/118 | Livraria Estrela | `(2024-02-09) Invoice FT 2024-118 - Livraria Estrela.pdf` |
| `2024-01-10` | ELECTRICITY BILL | ENERGIA DO NORTE | `(2024-01-10) Electricity Bill - Energia do Norte.pdf` |
| `2024-11-30` | Banco Atlântico Checking Statement | Banco Atlântico | `(2024-11-30) Checking Statement - Banco Atlântico.pdf` |
| `2019-06-02` | Re: a casa de Braga | João Costa | `(2019-06-02) Re - a casa de Braga - João Costa.pdf` |
| `2024-07-01` | 2024-07-01 Home Insurance Renewal | Seguradora Horizonte | `(2024-07-01) Home Insurance Renewal - Seguradora Horizonte.pdf` |
<!-- examples -->

The people and institutions in these examples are invented (Caixa's synthetic family).
