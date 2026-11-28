"""Filing examined files in the box and the master: the writing half of a document import.

The collector examines files (in worker processes); this one writer then records each in order:

- a file the box already has (the same SHA-256) gains the place it was found again, nothing else;
- a file that cannot be used is named in the warnings and left where it is;
- a new file is placed (`archive.place`), copied byte for byte (`archive.copy_into`) and recorded:
  its document, its pages as inspected (text, class, quality; OCR's text where OCR read a page),
  what OCR did (an `ocr` run, with the tools' versions and settings), where it was found, and an
  `import` run. When OCR gave a page a text layer and the result passed validation (a `validate`
  run records the checks), the box holds the OCR'd copy (its own SHA-256); otherwise a
  byte-for-byte copy of the original (`unchanged_copy` when validation failed, `ocr_failed` for
  review; the failed file is kept in the working folder's `failed/`). A file locked with a password is kept as it is and waits for review
  (`locked`); one whose text is the same as a document's already in the box waits too
  (`probable_duplicate`): both stay.

Each document is committed as it is filed, so a stopped import leaves the master and the box in
step; undoing the import takes both back.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence

from caixa import __version__, session_log
from caixa.box import Box
from caixa.collectors.base import Progress, RunResult
from caixa.documents import evidence, records
from caixa.documents.archive import UNRECOGNIZED, Facts, copy_into, place
from caixa.session_log import Document, QuietLog

if TYPE_CHECKING:
    from caixa.collectors.pdfImport import Examined

#: What a working folder's unpacked zip is called (see `caixa.collectors.inputs.unpack`).
UNPACKED = "unpacked"


def origin(path: Path, source: Path, workdir: Optional[Path]) -> str:
    """Where a file was found, as the owner knows it: its own path, or `<zip>!/<member>` for one
    that came out of a zip."""
    if workdir is not None:
        try:
            inside = path.relative_to(workdir)
        except ValueError:
            return str(path)
        member = "/".join(inside.parts[1:])  # after the `<zip name>-<hash>` folder
        return f"{source}!/{member}"
    return str(path)


def _taught(known: Any, filed: Optional[Facts]) -> Optional[Facts]:
    """Provisional facts with the author the owner's lessons give: an `instead` replaces it, and a
    rejected name is not used, so the document waits in Unrecognized (D31)."""
    if filed is None or not filed.author:
        return filed
    from dataclasses import replace

    from caixa.documents.author_knowledge import apply

    author = apply(known, filed.author)
    return filed if author == filed.author else replace(filed, author=author)


def import_examined(
    box: Box,
    source: Path,
    seen: Sequence["Examined"],
    progress: Callable[[Progress], None],
    format: str = "pdf",
    workdir: Optional[Path] = None,
    facts: Optional[Callable[["Examined"], Optional[Facts]]] = None,
    organized: bool = False,
) -> RunResult:
    """Record every examined file (see the module text). A new file is filed by what its filename
    and properties say (`caixa.documents.evidence.provisional_facts`), or by `facts` when given,
    its author put through the owner's lessons (D31). With `organized`, a file named the organized
    way (D30) keeps its name, under its year and author; its tags are the owner's, and its author
    and tags join the whitelist."""
    from caixa.documents import author_knowledge
    from caixa.documents.organized import read_organized

    lessons = author_knowledge.load(box)
    learned_authors: list[str] = []
    learned_tags: list[str] = []
    result = RunResult()
    total = len(seen)
    log = session_log.current()
    with box.master() as master:
        import_id = master.start_import(format, source)
        master.commit()
        for number, one in enumerate(seen, start=1):
            progress(Progress("filing", number, total, one.name))
            where = origin(Path(one.path), source, workdir)
            doc = Document(number, total, one.name)
            with log.on(doc):
                if one.error:
                    result.warnings.append(f"{one.name}: {one.error}. Left where it is: {where}")
                    log.event("import", "unreadable", doc, "left where it is", reason=one.error)
                    log.outcome(doc, "unreadable")
                    continue
                known = records.find_by_source(master, one.sha256)
                if known is not None:
                    records.add_source(master, known, where, one.size, one.modified, import_id)
                    master.commit()
                    result.unchanged += 1
                    log.event("import", "known", doc, "already in the box (the same bytes)")
                    log.outcome(doc, "already in the box")
                    continue
                log_examination(log, doc, one)
                done = one.ocr or {}
                output = Path(done["output"]) if done.get("output") else None
                archived = str(done["sha256"]) if output is not None else one.sha256
                texts = {int(number): text for number, text in (done.get("texts") or {}).items()}
                named = evidence.read_filename(one.name, records.author_names(master))
                stated = evidence.read_properties(one.properties)
                name = read_organized(one.name) if organized else None
                filed: Optional[Facts]
                if name is not None:  # the owner's own name, and their author: no lessons
                    filed = Facts(
                        date=None if name.impossible else name.date,
                        title=name.subject,
                        author=name.author,
                    )
                    learned_authors += [name.author] if name.author else []
                    learned_tags += name.tags
                else:
                    filed = facts(one) if facts else evidence.provisional_facts(named, stated)
                    filed = _taught(lessons, filed)
                relative = place(
                    box, one.name, one.sha256, filed, format,
                    filename=one.name if name is not None else None,
                )  # fmt: skip
                copy_into(box, output or Path(one.path), relative, archived)
                review = ["locked"] if one.locked else []
                if one.text_hash and records.find_by_text(master, one.text_hash):
                    review.append("probable_duplicate")
                status = str(done.get("status") or ("needs_ocr" if one.ocr_pages else "not_needed"))
                if status == "failed":
                    review.append("ocr_failed")
                validation = done.get("validation")
                checked = "unchanged_copy" if validation and not validation["passed"] else "passed"
                record = records.DocumentRecord(
                    format=format,
                    original_filename=one.name,
                    source_sha256=one.sha256,
                    size=one.size,
                    file_path=relative,
                    archived_sha256=archived,
                    pages=one.pages,
                    processing_status="needs_review" if review else "archived",
                    ocr_status=status,
                    validation_status=checked,
                    review=review,
                    text_hash=one.text_hash,
                    title=filed.title if filed else None,
                    author=filed.author if filed else None,
                    date=filed.date if filed else None,
                    date_precision=(
                        (name.precision if filed and filed.date else None)
                        if name is not None
                        else (named.date.precision if filed and named.date else None)
                    ),
                    date_kind="filename" if filed else None,
                )
                item_id, _ = records.save_document(master, record, import_id)
                records.set_pages(
                    master,
                    item_id,
                    [
                        records.PageText(
                            page["number"],
                            texts.get(page["number"], page["text"]),
                            "ocr" if page["number"] in texts else "pdf",
                            page["page_class"],
                            page["quality"],
                        )
                        for page in one.inspection
                    ],
                )
                if done and status != "not_needed":
                    records.add_run(
                        master, item_id, "ocr", status, tool=done.get("tool"),
                        version=(done.get("versions") or {}).get("ocrmypdf"),
                        settings={**(done.get("settings") or {}), "versions": done.get("versions")},
                        report={"error": done["error"]} if done.get("error") else None,
                    )  # fmt: skip
                _record_evidence(master, item_id, named, stated, one, texts, filed)
                if name is not None:
                    records.add_field(master, item_id, "organized", one.name, "original_filename",
                                      state="applied")  # fmt: skip
                    records.set_tags(master, item_id, name.tags, "user_verified")
                if validation:
                    records.add_run(
                        master, item_id, "validate", "passed" if validation["passed"] else "failed",
                        tool="caixa", version=__version__, report=validation,
                    )  # fmt: skip
                if output is not None:
                    output.unlink(missing_ok=True)  # the working copy, now in the box
                records.add_source(master, item_id, where, one.size, one.modified, import_id)
                records.add_run(
                    master, item_id, "import", "ok", tool="caixa", version=__version__,
                    report={"locked": one.locked, "pages": one.pages},
                )  # fmt: skip
                master.commit()
                result.inserted += 1
                _log_filing(
                    log, doc, item_id, relative, named, stated, filed, facts is None, review
                )
        master.finish_import(
            import_id,
            inserted=result.inserted,
            unchanged=result.unchanged,
            details="; ".join(result.warnings) or None,
        )
    if learned_authors or learned_tags:  # what the owner's organized names teach (D30)
        whitelist = author_knowledge.load(box)
        author_knowledge.learn_organized(whitelist, learned_authors, learned_tags)
        author_knowledge.save(box, whitelist)
    return result


def log_examination(log: QuietLog, doc: Document, one: "Examined") -> None:
    """What examining one file found, then what OCR and validation did with it."""
    classes = Counter(str(page["page_class"]) for page in one.inspection)
    log.event(
        "examine", "examine", doc, pages=one.pages, classes=dict(classes),
        needs_ocr=one.ocr_pages, locked=one.locked, seconds=one.seconds,
    )  # fmt: skip
    done = one.ocr or {}
    if done and done.get("status") != "not_needed":
        asked = done.get("settings") or {}
        log.event(
            "examine", "ocr", doc, status=done.get("status"), mode=done.get("mode"),
            pages=asked.get("pages") or [], languages=asked.get("languages"),
            error=done.get("error"), seconds=done.get("seconds"),
        )  # fmt: skip
    validation = done.get("validation")
    if validation:
        log.event(
            "examine", "validate", doc, passed=bool(validation["passed"]),
            failed=[check["name"] for check in validation["checks"] if not check["passed"]],
            seconds=done.get("validate_seconds"),
        )  # fmt: skip


def _log_filing(
    log: QuietLog,
    doc: Document,
    item_id: str,
    relative: str,
    named: evidence.FilenameEvidence,
    stated: evidence.PropertyEvidence,
    filed: Optional[Facts],
    by_evidence: bool,
    review: list[str],
) -> None:
    """Where a new document was filed and why: what its filename and properties said, the facts
    it was filed by, or what was missing to file it (it waits in `Unrecognized/`)."""
    unrecognized = UNRECOGNIZED in Path(relative).parts
    why: list[str] = []
    if unrecognized:
        why = evidence.lacking(named, stated) if by_evidence else []
        why = why or ["no_usable_name" if filed is not None else "no_facts"]
    said_by_name = {
        "date": named.date.value if named.date else None,
        "author": named.author,
        "title": named.title,
        "types": named.types,
    }
    said_by_properties = {
        "author": stated.author,
        "title": stated.title,
        "created": stated.created,
    }
    fields: dict[str, Any] = {
        "filename": {key: value for key, value in said_by_name.items() if value},
        "properties": {key: value for key, value in said_by_properties.items() if value},
    }
    if filed is not None and not unrecognized:
        fields["filed_by"] = asdict(filed)
    if why:
        fields["why"] = why
    if review:
        fields["review"] = review
    log.event("import", "file", doc, f"→ {relative}", **fields)
    log.outcome(doc, "Unrecognized" if unrecognized else "filed", why + review, key=item_id)


def _record_evidence(
    master: Any,
    item_id: str,
    named: evidence.FilenameEvidence,
    stated: evidence.PropertyEvidence,
    one: "Examined",
    texts: dict[int, str],
    filed: Optional[Facts],
) -> None:
    """Every fact the filename, the properties and the text give, with where it came from; those
    the document was filed by are `applied`."""

    def state(field: str, value: Optional[str]) -> str:
        used = filed is not None and getattr(filed, field, None) == value
        return "applied" if used else "proposed"

    def add(field: str, value: Optional[str], source: str, **extra: Any) -> None:
        if value:
            records.add_field(master, item_id, field, value, source, **extra)

    when = named.date
    add("filename", "informative" if named.informative else "uninformative", "original_filename")
    if when is not None:
        add(
            "date",
            when.value,
            "original_filename",
            evidence=when.text,
            state=state("date", when.value),
        )
    add("author", named.author, "original_filename", evidence=named.author,
        state=state("author", named.author))  # fmt: skip
    add("title", named.title, "original_filename", evidence=named.title)
    for kind in named.types:
        add("type", kind, "original_filename")
    for amount in named.amounts:
        add("amount", amount, "original_filename", evidence=amount)
    add("cheque_number", named.cheque_number, "original_filename", evidence=named.cheque_number)
    add("invoice_number", named.invoice_number, "original_filename", evidence=named.invoice_number)
    add("title", stated.title, "pdf_metadata", evidence=stated.title)
    author_used = state("author", stated.author) if named.author is None else "proposed"
    add("author", stated.author, "pdf_metadata", evidence=stated.author, state=author_used)
    add("subject", stated.subject, "pdf_metadata")
    add("keywords", ", ".join(stated.keywords), "pdf_metadata")
    add("creation_date", stated.created, "pdf_metadata")
    add("modification_date", stated.modified, "pdf_metadata")
    pages = [
        (
            page["number"],
            texts.get(page["number"], page["text"]),
            "ocr" if page["number"] in texts else "pdf_content",
        )
        for page in one.inspection
    ]
    for found in evidence.text_dates(pages):
        add("date_in_text", found.value, found.source, evidence=found.text, page=found.page)
