"""caixa documents prepare: both models, beside the box (20261127-01). Synthetic files only."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from caixa import cli
from caixa.box import Box


def _pdf(path: Path, *lines: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 72 + index * 16), line)
    doc.save(path)
    doc.close()


def test_prepare_copies_both_trees_and_leaves_the_source_and_the_box(tmp_path: Path) -> None:
    folder = tmp_path / "pdfs"
    folder.mkdir()
    pdf = folder / "Scan.pdf"
    _pdf(pdf, "Hello from the page")
    before = pdf.read_bytes()
    box = Box.create(tmp_path / "Box", name="Our box")
    settings = (box.caixa_dir / "box.yaml").read_bytes()
    out = tmp_path / "prepared"

    assert (
        cli.main(["documents", "prepare", str(folder), "--out", str(out), "--box", str(box.root)])
        == 0
    )

    assert pdf.read_bytes() == before
    assert (out / "Documents/PDF/Unrecognized/Scan.pdf").read_bytes() == before
    local = tmp_path / "prepared local"
    assert (local / "Documents/PDF/Unrecognized/Scan.pdf").read_bytes() == before
    assert not (out / ".caixa").exists()
    assert not (local / ".caixa").exists()
    assert (box.caixa_dir / "box.yaml").read_bytes() == settings
