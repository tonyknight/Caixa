---
id: 20261127-01-prepare-pdfs-beside-the-box-and-compare-the-two
title: Prepare PDFs beside the box and compare the two models
type: feature
priority: high
status: done
created: 2026-11-27
updated: 2026-11-28
closed: 2026-11-28
notes: 'Done: documents prepare compares Apple Intelligence and the local model beside
  the box.'
parent:
depends_on:
- 20261124-02-the-archival-naming-convention
- 20261124-05-inspection-page-by-page
- 20261124-06-selective-ocr
- 20261124-09-filename-and-property-evidence
- 20261124-10-ai-classification
subtasks:
- id: T01
  title: The command and the two output folders
  status: done
- id: T02
  title: Preprocessing, once for both models
  status: done
- id: T03
  title: Both models, the same instructions, archival filing
  status: done
- id: T04
  title: The diff report
  status: done
plan_status: done
---
## Description

The first real import filed most documents in `Unrecognized`, and the ones it did file
often took the author from the PDF's properties. On the maintainer's sample that author was
`Brite:Bill`, the program that wrote the PDF, not the company that sent the bill. A second
reading of that sample, with the page in reading order and the issuer taken from the page,
filed 142 of 201 and put those bills under the company named on the page.

That reading was rules discovered by looking, not a fair run of Apple Intelligence against
the local model. This ticket makes it a command, so the same pages can be given to both
models and the difference between them can be read afterwards.

`caixa documents prepare <folder> --out <path> --box <box>`:

- does not open the box for writing, does not create `.caixa`, and does not change the
  originals;
- preprocesses every PDF once;
- asks Apple Intelligence and the local model, with the same instructions;
- files each answer with the archival name;
- writes a report that diffs the two trees.

Apple Intelligence's copies are `<path>/Documents/PDF/`. The local model's copies are
`<path> local/Documents/PDF/`. The local model is the endpoint and model already named in
that box's Settings, Summaries. The box is only read.

**Preprocessing, once:**

1. Text in reading order.
2. A text layer that is not words (punctuation and digits, as on the utility bills whose
   fonts do not map to letters) is read by OCR before anyone decides.
3. A cover sheet, a nearly empty first page or a fax or scan cover, is skipped. The next
   page is the first page.
4. The top of the first real page and the bottom of the last page are marked, and kept
   whole when the text sent to a model has to be cut.

**The same instructions to both models:**

- Decide the kind, then the date that kind uses: the issue date of a bill, the end of a
  statement's period, the tax year, the day a letter was written. Never invent a day.
- The author is who the page names as the sender. A software name in the PDF's Author
  field, such as `Brite:Bill`, is not an author.
- A date taken from the file name counts only when the page does not contradict it.

**Filing.** Caixa files an answer only when author, title and date are all present, as
`(date) Title - Author.pdf` under `<year>/<author>/`. Anything else is copied to
`Unrecognized/` under its own name. A second copy of the same decided name gets ` (2)`.

**The report,** `<path>/report.txt` and `report.jsonl`:

- filed by both to the same place;
- filed by both to different places, with both paths;
- filed by one and left unrecognized by the other;
- the counts, and the time each model took;
- per file, the preprocessing that ran (reading order, OCR, cover sheet, which region
  supplied a missing fact).

Decided values only. Never page text. When Apple Intelligence is not available the report
says so and the local model still runs. Vision, and a memory of past layouts, are out of
this command.

## Acceptance criteria

- [ ] `caixa documents prepare` on a folder of PDFs leaves every source byte unchanged and
      creates no `.caixa` directory. `--box` is read and not written.
- [ ] Apple Intelligence's copies are `<path>/Documents/PDF/`. The local model's copies are
      `<path> local/Documents/PDF/`. A file with no author, title or date is in
      `Unrecognized/` under its own name.
- [ ] A bill whose PDF Author is a program name is not filed under that name. The author is
      the one the page names.
- [ ] A page whose text is drawn bottom-first still presents its letterhead before its
      closing to both models.
- [ ] A text layer that is not words is read by OCR, and that is named on the file's record.
- [ ] A cover sheet is skipped. The next page is treated as the first.
- [ ] When author or date is still missing, the other marked region is tried, and the record
      says which look found the fact.
- [ ] Two stand-in models that disagree produce two trees, and the report gives both paths.
      Two that agree produce one path in the diff. The report contains no page text.
- [ ] With Apple Intelligence unavailable the report says Apple did not run, and the local
      model still files its tree.

## Context

- **Requirements:** D28. Naming is D9 (`caixa/naming.py`, `caixa/documents/archive.py`).
  Page classes are D4 (`caixa/documents/pdf/inspect.py`). OCR is D5. The model choice is D12
  and D17 (`caixa/documents/enrich.py` `provider`, `caixa/apple_intelligence.py`).
- **Why the rules look like this:** the maintainer's sample. The PDF Author `Brite:Bill` is
  the program that wrote the phone bills. The utility bills have a text layer that is not
  words, and today's inspection calls it good text, so OCR never runs. Most file names give
  no author, which is why import leaves them in `Unrecognized`.
- **The sample stays out of the repository.** Tests build synthetic PDFs.
- **Not in this ticket:** vision, a memory of a sender's layout, importing either tree into
  a box, changing `caixa import pdf`.

## Subtasks

- [ ] T01 The command and the two output folders
- [ ] T02 Preprocessing, once for both models
- [ ] T03 Both models, the same instructions, archival filing
- [ ] T04 The diff report

## Implementation plan

Status: done
Current task: 

### T01: The command and the two output folders

- **Files:** `caixa/cli.py` (`documents prepare`, with `<folder>`, `--out`, `--box`);
  `caixa/documents/prepare.py` (new); `tests/test_documents_prepare.py` (new).
- **RED:** the command copies a synthetic PDF into `<out>/Documents/PDF/Unrecognized/` under
  its own name and into `<out> local/Documents/PDF/Unrecognized/`, creates no `.caixa`, and
  does not change the source. `--box` is not written.
- **GREEN:** the command and the two folders, with no model yet (both trees unrecognized).
- **Verify:** `python -m pytest -q tests/test_documents_prepare.py`
- [x] done

### T02: Preprocessing, once for both models

- **Files:** `caixa/documents/prepare.py`; `tests/fixtures/` a small builder, or the builders
  already in `tests/fixtures/`, extended; `caixa/documents/pdf/inspect.py` only if the
  "not words" test belongs beside the existing page classes.
- **RED:**
  - a page drawn bottom-first yields the letterhead before the closing;
  - a text layer of punctuation and digits is flagged and, when Tesseract is installed,
    replaced by OCR text (skipped with a reason otherwise);
  - a cover sheet leaves page 2 as the first page;
  - the top of the first page and the bottom of the last are marked, and survive a short
    cut.
- **GREEN:** one preprocessed document, reused for both models.
- **Verify:** `python -m pytest -q tests/test_documents_prepare.py tests/test_pdf_inspect.py`
- [x] done

### T03: Both models, the same instructions, archival filing

- **Files:** `caixa/documents/prepare.py` (the shared instruction, the call through
  `enrich.provider` for the local model and `apple_intelligence` for Apple, filing through
  `archive.place`); `tests/test_documents_prepare.py` with two stand-ins.
- **RED:** a stand-in that answers with the program name as author is filed under the
  sender the instruction asked for, when the stand-in follows it; an answer missing a date
  stays in `Unrecognized`; two stand-ins that name different authors produce two different
  folders. Apple unavailable is reported and the local stand-in still files.
- **GREEN:** both calls, then `place` for each answer. The second look uses the other marked
  region before giving up, and the record names which look succeeded.
- **Verify:** `python -m pytest -q tests/test_documents_prepare.py`
- [x] done

### T04: The diff report

- **Files:** `caixa/documents/prepare.py` (`report.txt`, `report.jsonl`);
  `tests/test_documents_prepare.py`; `docs/Documentation/Collector.md` (a short section on
  `prepare`).
- **RED:** the report lists same place, both paths when they differ, and filed-by-one; a
  sentence from the page body is absent while the decided author is present; counts and a
  time per model are present.
- **GREEN:** the report beside the Apple tree.
- **Verify:** `python -m pytest -q tests/test_documents_prepare.py`, then the project verify
  command:
  `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`.
- [x] done
## Completion report

- **Outcome:** `caixa documents prepare` preprocesses a folder once and files Apple
  Intelligence's answers in the output path and the local model's in `<path> local`.
  The report diffs the two trees. No box is written and the originals are unchanged.
- **Files:** `caixa/documents/prepare.py` (new); `caixa/cli.py`; `tests/test_documents_prepare.py`
  (new); `docs/Documentation/Collector.md`; the Requirements (D28 and task 24).
- **Errors:** A first page of a multi-page file with fewer than 40 letters is treated as a
  cover even without the cover words. Both models leaving a file unrecognized is counted as
  the same place.
- **Verify:** `tests/test_documents_prepare.py`: 11 passed. Project suite: 2067 passed, 8
  failed (the 7 known Chattr web-convert failures, and one iMessage report test that passes
  when run by itself). black only the known `tests/test_mail_sent_and_received.py`. mypy the
  8 known errors. Web `tsc` clean; vitest 249 passed, 37 end-to-end tests skipped because
  Playwright is not installed on this machine.

## Review

2026-11-27, on `63bdcd6..e30509d`. No Critical or Important findings. The command matches D28:
one preprocessing, both models, two trees, a diff with no page text, and the box only read.
Two minors, recorded under Errors above: the short-page cover rule, and unrecognized pairs
counted as the same place.

## Notes

Append-only running log. Each entry dated.

- 2026-11-27: Agreed after the sample. One command, not a rules ticket and a model ticket.
  Apple's tree is the output path. The local tree is `<path> local`. The local model is the
  one Settings already names. The report diffs the trees and holds no page text.

### 2026-11-28
Started. Work stays on 2026-Istanbul/Phase1.5-PDF (no separate worktree).

### 2026-11-28
T04 done and reviewed. No critical or important findings.
