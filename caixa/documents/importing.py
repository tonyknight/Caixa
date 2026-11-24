"""Filing examined files in the box and the master: the writing half of a document import.

The collector examines files (in worker processes); this one writer then records each in order:

- a file the box already has (the same SHA-256) gains the place it was found again, nothing else;
- a file that cannot be used is named in the warnings and left where it is;
- a new file is placed (`archive.place`), copied byte for byte (`archive.copy_into`) and recorded:
  its document, its pages as inspected (text, class, quality), whether it needs OCR, where it was
  found, and an `import` run. A file locked with a password is kept as it is and waits for review
  (`locked`); one whose text is the same as a document's already in the box waits too
  (`probable_duplicate`): both stay.

Each document is committed as it is filed, so a stopped import leaves the master and the box in
step; undoing the import takes both back.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Sequence

from caixa import __version__
from caixa.box import Box
from caixa.collectors.base import Progress, RunResult
from caixa.documents import records
from caixa.documents.archive import Facts, copy_into, place

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


def import_examined(
    box: Box,
    source: Path,
    seen: Sequence["Examined"],
    progress: Callable[[Progress], None],
    format: str = "pdf",
    workdir: Optional[Path] = None,
    facts: Optional[Callable[["Examined"], Optional[Facts]]] = None,
) -> RunResult:
    """Record every examined file (see the module text); `facts` gives the date, author and title
    a file can be filed by before any model has read it (None: every new file is unrecognized)."""
    result = RunResult()
    total = len(seen)
    with box.master() as master:
        import_id = master.start_import(format, source)
        master.commit()
        for number, one in enumerate(seen, start=1):
            progress(Progress("filing", number, total, one.name))
            where = origin(Path(one.path), source, workdir)
            if one.error:
                result.warnings.append(f"{one.name}: {one.error}. Left where it is: {where}")
                continue
            known = records.find_by_source(master, one.sha256)
            if known is not None:
                records.add_source(master, known, where, one.size, one.modified, import_id)
                master.commit()
                result.unchanged += 1
                continue
            relative = place(box, one.name, one.sha256, facts(one) if facts else None, format)
            copy_into(box, Path(one.path), relative, one.sha256)
            review = ["locked"] if one.locked else []
            if one.text_hash and records.find_by_text(master, one.text_hash):
                review.append("probable_duplicate")
            record = records.DocumentRecord(
                format=format,
                original_filename=one.name,
                source_sha256=one.sha256,
                size=one.size,
                file_path=relative,
                archived_sha256=one.sha256,
                pages=one.pages,
                processing_status="needs_review" if review else "archived",
                ocr_status="needs_ocr" if one.ocr_pages else "not_needed",
                review=review,
                text_hash=one.text_hash,
            )
            item_id, _ = records.save_document(master, record, import_id)
            records.set_pages(
                master,
                item_id,
                [
                    records.PageText(
                        page["number"], page["text"], "pdf", page["page_class"], page["quality"]
                    )
                    for page in one.inspection
                ],
            )
            records.add_source(master, item_id, where, one.size, one.modified, import_id)
            records.add_run(
                master, item_id, "import", "ok", tool="caixa", version=__version__,
                report={"locked": one.locked, "pages": one.pages},
            )  # fmt: skip
            master.commit()
            result.inserted += 1
        master.finish_import(
            import_id,
            inserted=result.inserted,
            unchanged=result.unchanged,
            details="; ".join(result.warnings) or None,
        )
    return result
