"""The PDF collector: PDFs from a file, a folder (with every folder inside it) or a zip, filed in the
box's `Documents/PDF/` without the originals ever being moved or changed.

Named for its format: the documents domain (`caixa.documents`) is shared, and each later format
(Word, spreadsheets, …) gets a collector of its own.

- `locate` finds every `.pdf` (any case) in what was chosen, unpacking zips into the collector's
  working folder;
- `examine` (run in worker processes) reads one file: its SHA-256, size and time, its pages,
  whether it needs a password, its properties, or why it cannot be used (not a PDF; damaged beyond
  what MuPDF can rebuild);
- `preview` says what an import would bring, writing nothing;
- `run` files each new PDF: a byte-for-byte copy, checked against its hash, placed by
  `caixa.documents.archive`, and recorded in the master with where it was found. A file the box
  already has only gains the place it was found again; one that cannot be read is named in the
  warnings and left where it is.
"""

from __future__ import annotations

import concurrent.futures
import functools
import hashlib
import multiprocessing
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from caixa.box import Box
from caixa.collectors import inputs
from caixa.collectors.base import CollectorInfo, Preview, Progress, RunResult
from caixa.documents.pdf.inspect import inspect_pdf, text_hash
from caixa.documents.pdf.process import ocr_and_validate

FORMAT = "pdf"
COLLECTOR = "pdf"
#: The properties a PDF can carry that Caixa reads (PyMuPDF's names).
PROPERTIES = (
    "title",
    "author",
    "subject",
    "keywords",
    "creator",
    "producer",
    "creationDate",
    "modDate",
)

OPTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "workers": {
            "type": "integer",
            "minimum": 1,
            "maximum": 12,
            "title": "Workers",
            "description": "PDFs read at once (default: the box's Workers setting).",
        },
    },
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Examined:
    """What reading one file found (made in a worker process, so plain values only)."""

    path: str
    sha256: str = ""
    size: int = 0
    modified: Optional[str] = None
    pages: Optional[int] = None
    locked: bool = False  # it needs a password to be read
    properties: dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None  # why it cannot be used
    #: Each page as inspected (`caixa.documents.pdf.inspect`): number, class, poor, text, quality.
    inspection: tuple[dict[str, Any], ...] = ()
    text_hash: Optional[str] = None
    #: What OCR did (`caixa.documents.pdf.ocr.OcrOutcome` as plain values), when it was asked to.
    ocr: Optional[dict[str, Any]] = None

    @property
    def ocr_pages(self) -> int:
        """How many pages may need OCR (pictures, broken text, a poor OCR layer)."""
        return sum(page["needs_ocr"] for page in self.inspection)

    @property
    def name(self) -> str:
        return Path(self.path).name


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _empty(page: Any) -> bool:
    return not page.get_text().strip() and not page.get_images() and not page.get_drawings()


def examine(path: Path, ocr: Optional[Mapping[str, Any]] = None) -> Examined:
    """Read one file, never writing to it; with `ocr` (`enabled`, `languages`, `workdir`), also
    OCR the pages that need it into the working folder."""
    import pymupdf

    pymupdf.TOOLS.mupdf_display_errors(False)  # a damaged file says so in `error`, not on stderr
    try:
        stat = path.stat()
        sha256 = _hash(path)
    except OSError as error:
        return Examined(str(path), error=f"it could not be read ({error.strerror or error})")
    seen = Examined(
        str(path),
        sha256=sha256,
        size=stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    )
    try:
        doc = pymupdf.open(path)
    except Exception:
        return replace(seen, error="it is not a PDF that can be opened")
    try:
        if doc.needs_pass:
            return replace(seen, pages=doc.page_count, locked=True)
        if doc.is_repaired and all(_empty(page) for page in doc):
            return replace(seen, error="it is damaged: nothing on it could be recovered")
        properties = {
            key: str(value).strip()
            for key, value in (doc.metadata or {}).items()
            if key in PROPERTIES and value and str(value).strip()
        }
        pages = inspect_pdf(doc)
        inspection = tuple(
            {
                "number": page.number,
                "page_class": page.page_class,
                "poor": page.poor,
                "needs_ocr": page.needs_ocr,
                "text": page.text,
                "quality": page.quality(),
            }
            for page in pages
        )
        seen = replace(seen, pages=doc.page_count, properties=properties, inspection=inspection)
    finally:
        doc.close()
    texts = [page["text"] for page in seen.inspection]
    if ocr is not None and not seen.locked:
        done = ocr_and_validate(path, seen.sha256, seen.inspection, ocr)
        texts = [done["texts"].get(page["number"], page["text"]) for page in seen.inspection]
        seen = replace(seen, ocr=done)
    return replace(seen, text_hash=text_hash(texts))


def _examine_all(
    files: list[Path],
    workers: int,
    progress: Callable[[Progress], None],
    ocr: Optional[Mapping[str, Any]] = None,
) -> list[Examined]:
    """Every file examined (and, with `ocr`, OCR'd where it needs it), in the order given, by up
    to `workers` processes."""
    total = len(files)
    progress(Progress("reading", 0, total, f"Reading {total} PDFs"))
    work = functools.partial(examine, ocr=dict(ocr) if ocr is not None else None)
    if workers <= 1 or total <= 1:
        found = []
        for number, file in enumerate(files, start=1):
            found.append(work(file))
            progress(Progress("reading", number, total, file.name))
        return found
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=min(workers, total), mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        found = []
        for number, seen in enumerate(pool.map(work, files, chunksize=2), start=1):
            found.append(seen)
            progress(Progress("reading", number, total, seen.name))
        return found


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


class PdfCollector:
    info = CollectorInfo(
        id=COLLECTOR,
        name="PDF documents",
        platform="Any",
        inputs=("file", "folder", "zip"),
        how_to_export=(
            "Choose a PDF, a folder of PDFs (the folders inside it are searched too) or a .zip of "
            "them, such as your Downloads folder or a folder of scans. The files stay where they "
            "are: Caixa files a copy of each in the box's Documents/PDF folder, with its text "
            "made searchable, and never changes or moves the originals."
        ),
        options_schema=OPTIONS_SCHEMA,
    )

    def locate(self, source: Path, workdir: Path) -> list[Path]:
        def find(folder: Path) -> list[Path]:
            return [
                p
                for p in folder.rglob("*")
                if p.is_file()
                and p.suffix.lower() == ".pdf"
                and not inputs._is_system(p, folder)  # noqa: SLF001 (the inputs' own rule)
            ]

        return inputs.resolve(
            source,
            find,
            workdir,
            expects="PDF files (.pdf), on their own or in a folder or a .zip",
        )

    def _workers(self, box: Optional[Box], options: Mapping[str, Any]) -> int:
        if options.get("workers"):
            return int(options["workers"])
        if box is None:
            return 1
        from caixa import settings

        return int(settings.load(box)["workers"])

    def _workdir(self, box: Optional[Box], source: Path) -> Path:
        if box is not None:
            return box.work_dir("documents") / "unpacked"
        return source.parent / ".caixa-unpacked"

    def preview(
        self,
        source: Path,
        options: Mapping[str, Any],
        box: Optional[Box] = None,
        progress: Optional[Callable[[Progress], None]] = None,
    ) -> Preview:
        files = self.locate(source, self._workdir(box, source))
        seen = _examine_all(files, self._workers(box, options), progress or (lambda step: None))
        known: set[str] = set()
        if box is not None and box.master_path.exists():
            from caixa.documents import records

            with box.master(read_only=True) as master:
                known = {s.sha256 for s in seen if records.find_by_source(master, s.sha256)}
        new: dict[str, Examined] = {}
        already, copies, locked, unreadable = 0, 0, 0, []
        for one in seen:
            if one.error:
                unreadable.append(f"{one.name}: {one.error}")
            elif one.sha256 in known:
                already += 1
            elif one.sha256 in new:
                copies += 1
            else:
                new[one.sha256] = one
                locked += one.locked
        pages = sum(one.pages or 0 for one in new.values())
        size = sum(one.size for one in new.values())
        ocr = sum(one.ocr_pages for one in new.values())
        warnings = [
            f"{_plural(len(new), 'new document', 'new documents')}, "
            f"{_plural(pages, 'page', 'pages')}, {size / 1_000_000:.1f} MB",
        ]
        if ocr:
            warnings.append(
                f"{_plural(ocr, 'page may', 'pages may')} need OCR (scanned, or text that "
                "cannot be read)"
            )
        if already:
            warnings.append(f"{_plural(already, 'file', 'files')} already in the box")
        if copies:
            warnings.append(f"{_plural(copies, 'copy', 'copies')} of a file found twice")
        if locked:
            warnings.append(f"{locked} locked with a password (kept, to be opened with it)")
        warnings += [f"Cannot be read, left where it is: {line}" for line in unreadable]
        return Preview(items=len(new), warnings=warnings)

    def run(
        self,
        box: Box,
        source: Path,
        options: Mapping[str, Any],
        progress: Callable[[Progress], None],
    ) -> RunResult:
        from caixa.documents.importing import import_examined

        from caixa import settings

        workdir = self._workdir(box, source)
        files = self.locate(source, workdir)
        saved = settings.load(box)
        ocr = {
            "enabled": bool(saved.get("documents.ocr", True)),
            "languages": str(saved.get("documents.ocr_languages") or "eng"),
            "workdir": str(box.work_dir("documents") / "ocr"),
        }
        seen = _examine_all(files, self._workers(box, options), progress, ocr)
        result = import_examined(box, source, seen, progress, FORMAT, workdir)
        from caixa.documents.enrich import enrich_documents

        read = enrich_documents(box, progress=progress)  # the documents still waiting
        if read.get("reason") and read.get("waiting"):
            result.warnings.append(
                f"{read['waiting']} documents were not read by a model: {read['message']} "
                "They can be read later (caixa documents enrich)."
            )
        return result


def collectors() -> list[PdfCollector]:
    return [PdfCollector()]


__all__ = ["COLLECTOR", "Examined", "FORMAT", "PdfCollector", "collectors", "examine"]
