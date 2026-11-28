"""Read a folder of PDFs with both models, beside any box, and compare where they file.

One run preprocesses every PDF once, asks Apple Intelligence and the local model the same
question, and files each answer under the output path (Apple) and `<output> local` (the local
model). Nothing is written into a box, and the originals are only read. See D28.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Optional

from caixa.documents.archive import DOCUMENTS, FORMAT_FOLDERS, _target
from caixa.naming import free_path


def local_root(out: Path) -> Path:
    """The local model's folder, beside the one asked for: `prepared` and `prepared local`."""
    return out.with_name(out.name + " local")


def _pdfs(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf" and not path.name.startswith(".")
    )


def _copy(root: Path, source: Path) -> Path:
    """A copy filed as unrecognized, byte for byte. The source is only read."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    relative = _target(source.name, digest, None, "pdf")
    folder = root / DOCUMENTS / FORMAT_FOLDERS["pdf"] / relative.parent
    target = free_path(folder, relative.name, digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def prepare(folder: Path, out: Path, box: Optional[Path] = None) -> None:
    """File every PDF in `folder` into both trees. `box` is accepted and not written (T01: no
    model yet, so both copies wait in Unrecognized)."""
    del box  # read later, for the model Settings names; never written
    for source in _pdfs(folder):
        for root in (out, local_root(out)):
            _copy(root, source)
