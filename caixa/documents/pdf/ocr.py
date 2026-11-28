"""OCR of the pages of a PDF that need it, on this computer: OCRmyPDF with Tesseract.

Inspection (`caixa.documents.pdf.inspect`) says which pages need OCR. Only those are touched:

- **pictures of pages** (`needs_ocr`) get an invisible text layer from OCRmyPDF, which keeps the
  pages as they look (`skip_text` leaves every page that has text alone; `optimize=0` keeps the
  pictures as they are; the output is a plain PDF, not PDF/A);
- **poor OCR layers** are done again (`redo_ocr`, which takes out the old invisible text first);
- **broken text** (visible text that extracts as garbage) is not rewritten, since OCRmyPDF could
  only fix it by turning the page into a picture. Tesseract reads a render of the page through
  PyMuPDF, and only that text is kept, in the box's database, so search finds the page while it
  looks exactly as before.

The original is only read, and OCRmyPDF writes to a working file. Validation
(`caixa.documents.pdf.validate`) decides whether that file is accepted. Nothing here is required:
without OCRmyPDF or Tesseract, the pages are still `needs_ocr` and the import goes on.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

#: How to install what OCR needs on a Mac (Homebrew brings Tesseract and Ghostscript with it).
ADVICE = "brew install ocrmypdf  (on a Mac; elsewhere: pip install ocrmypdf, and Tesseract)"
#: Resolution of the render Tesseract reads for a page whose text is broken.
BROKEN_DPI = 300


@dataclass(frozen=True)
class OcrTools:
    ready: bool
    versions: dict[str, str] = field(default_factory=dict)
    languages: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    advice: str = ADVICE


def _first_line(argv: list[str]) -> str:
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = (done.stdout or done.stderr or "").strip().splitlines()
    return lines[0].strip() if lines else ""


def _languages(tesseract: str) -> tuple[str, ...]:
    try:
        done = subprocess.run(
            [tesseract, "--list-langs"], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    lines = (done.stdout or "").strip().splitlines()
    return tuple(sorted(line.strip() for line in lines[1:] if line.strip()))  # after the heading


def tools() -> OcrTools:
    """Whether OCR can run here, with which versions and languages, and what is missing."""
    versions: dict[str, str] = {}
    missing: list[str] = []
    try:
        import ocrmypdf

        versions["ocrmypdf"] = str(ocrmypdf.__version__)
    except ImportError:
        missing.append("ocrmypdf")
    tesseract = shutil.which("tesseract")
    languages: tuple[str, ...] = ()
    if tesseract:
        versions["tesseract"] = _first_line([tesseract, "--version"]).removeprefix("tesseract ")
        languages = _languages(tesseract)
    else:
        missing.append("tesseract")
    return OcrTools(not missing, versions, languages, tuple(missing))


@dataclass
class OcrOutcome:
    """What OCR did to one PDF."""

    status: str  # not_needed | done | partial | needs_ocr | failed
    output: Optional[Path] = None  # the OCR'd PDF, when pages were given a text layer
    texts: dict[int, str] = field(default_factory=dict)  # page number → its text after OCR
    mode: Optional[str] = None  # skip_text | redo_ocr
    tool: str = "ocrmypdf"
    versions: dict[str, str] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    #: What OCRmyPDF said while it worked (its warnings and errors) and its verdict on its output
    #: when not `ok`: kept with the file, never printed to the terminal.
    notes: list[str] = field(default_factory=list)


def _read_broken(source: Path, numbers: Sequence[int], languages: str) -> dict[int, str]:
    """Tesseract's reading of renders of these pages (the file is not changed)."""
    import pymupdf

    texts: dict[int, str] = {}
    with pymupdf.open(source) as doc:
        for number in numbers:
            page = doc[number - 1]
            textpage = page.get_textpage_ocr(language=languages, dpi=BROKEN_DPI, full=True)
            texts[number] = str(page.get_text(textpage=textpage, sort=True))
    return texts


class _Notes(logging.Handler):
    """OCRmyPDF's warnings and errors during one file's OCR."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.messages.append(record.getMessage())
        except Exception:  # (a message that cannot be formatted costs only itself)
            pass


def restore_metadata(source: Path, output: Path) -> None:
    """Give `output` the source's document information and XMP exactly as the source has them
    (none where it has none): OCRmyPDF writes its own Creator, Producer, dates and XMP. The pages,
    and the text layer OCR added, are left as they are."""
    import pikepdf

    with (
        pikepdf.open(source) as original,
        pikepdf.open(output, allow_overwriting_input=True) as copy,
    ):
        if "/Info" in original.trailer:
            copy.trailer.Info = copy.copy_foreign(original.trailer.Info)
        elif "/Info" in copy.trailer:
            del copy.trailer.Info
        if "/Metadata" in original.Root:
            copy.Root.Metadata = copy.copy_foreign(original.Root.Metadata)
        elif "/Metadata" in copy.Root:
            del copy.Root.Metadata
        copy.save(output, fix_metadata_version=False)


def ocr_document(
    source: Path,
    output: Path,
    inspection: Sequence[dict[str, Any]],
    languages: str = "eng",
    enabled: bool = True,
) -> OcrOutcome:
    """OCR the pages `inspection` says need it (see the module text); `output` is written only
    when pages are given a text layer, and is gone again if that fails."""
    layered = [p["number"] for p in inspection if p["page_class"] == "needs_ocr" or p["poor"]]
    broken = [p["number"] for p in inspection if p["page_class"] == "broken_text"]
    if not layered and not broken:
        return OcrOutcome("not_needed")
    settings: dict[str, Any] = {
        "pages": layered,
        "read_only_pages": broken,
        "languages": languages,
        "output_type": "pdf",
        "optimize": 0,
    }
    if not enabled:
        return OcrOutcome("needs_ocr", settings=settings, error="OCR is turned off in Settings")
    found = tools()
    if not found.ready:
        return OcrOutcome(
            "needs_ocr",
            versions=found.versions,
            settings=settings,
            error=f"missing: {', '.join(found.missing)} ({found.advice})",
        )
    import ocrmypdf

    outcome = OcrOutcome("done", versions=found.versions, settings=settings)
    if layered:
        redo = any(p["poor"] for p in inspection if p["number"] in layered)
        outcome.mode = "redo_ocr" if redo else "skip_text"
        settings["mode"] = outcome.mode
        output.parent.mkdir(parents=True, exist_ok=True)
        heard = _Notes()
        logger = logging.getLogger("ocrmypdf")
        was = (logger.level, logger.propagate)
        logger.addHandler(heard)
        logger.setLevel(logging.WARNING)
        logger.propagate = False  # (else Python prints them, with no file named)
        try:
            code = ocrmypdf.ocr(
                source,
                output,
                pages=",".join(str(n) for n in layered),
                output_type="pdf",
                optimize=0,
                language=languages.split("+"),
                progress_bar=False,
                jobs=1,
                **{outcome.mode: True},
            )
        except Exception as error:  # OCRmyPDF has many failures of its own; each is one outcome
            output.unlink(missing_ok=True)
            return OcrOutcome(
                "failed",
                versions=found.versions,
                settings=settings,
                mode=outcome.mode,
                error=f"{type(error).__name__}: {error}",
                notes=heard.messages,
            )
        finally:
            logger.removeHandler(heard)
            logger.setLevel(was[0])
            logger.propagate = was[1]
        outcome.notes = heard.messages
        if code is not None and code != ocrmypdf.ExitCode.ok:
            verdict = getattr(code, "name", str(code))
            outcome.notes.append(
                f"OCRmyPDF judged its output {verdict}; Caixa's validation decides"
            )
        try:
            restore_metadata(source, output)  # the source's own words about itself, not OCRmyPDF's
        except Exception as error:
            output.unlink(missing_ok=True)
            return OcrOutcome(
                "failed", versions=found.versions, settings=settings, mode=outcome.mode,
                error=f"the source's metadata could not be kept: {type(error).__name__}: {error}",
            )  # fmt: skip
        import pymupdf

        with pymupdf.open(output) as doc:
            outcome.texts = {n: str(doc[n - 1].get_text(sort=True)) for n in layered}
        outcome.output = output
    try:
        outcome.texts.update(_read_broken(source, broken, languages))
    except Exception as error:
        outcome.error = f"broken pages could not be read: {type(error).__name__}: {error}"
    if not all(outcome.texts.get(n, "").strip() for n in [*layered, *broken]):
        outcome.status = "partial"
    return outcome


__all__ = ["ADVICE", "OcrOutcome", "OcrTools", "ocr_document", "restore_metadata", "tools"]
