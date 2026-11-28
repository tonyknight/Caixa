"""What the owner teaches Caixa about authors (20261127-02). Synthetic names only."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from caixa.box import Box
from caixa.documents import author_knowledge


def test_a_missing_file_is_empty(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    found = author_knowledge.load(box)
    assert found.accepted == [] and found.rejected == [] and found.instead == []


def test_the_file_keeps_accepted_rejected_and_instead_and_is_owner_only(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    known = author_knowledge.Knowledge(
        accepted=["PG&E", "T-Mobile"],
        rejected=["City of Springfield", "null"],
        instead=[{"said": "Anthony D. Knight", "use": "T-Mobile", "kind": "bill"}],
    )
    author_knowledge.save(box, known)
    path = box.caixa_dir / "author-knowledge.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text()) == {
        "accepted": ["PG&E", "T-Mobile"],
        "rejected": ["City of Springfield", "null"],
        "instead": [{"said": "Anthony D. Knight", "use": "T-Mobile", "kind": "bill"}],
    }
    assert "page" not in path.read_text()
    again = author_knowledge.load(box)
    assert again.accepted == known.accepted
    assert again.rejected == known.rejected
    assert again.instead == known.instead


def test_the_owner_is_never_rejected(tmp_path: Path) -> None:
    box = Box.create(tmp_path / "Box", name="Our box")
    known = author_knowledge.Knowledge()
    author_knowledge.learn_correction(
        known, said="Maria Costa", use="PG&E", kind="bill", owner="Maria Costa"
    )
    assert "Maria Costa" not in known.rejected
    assert "PG&E" in known.accepted
    assert known.instead == [{"said": "Maria Costa", "use": "PG&E", "kind": "bill"}]
    author_knowledge.save(box, known)
    os.chmod(box.caixa_dir / "author-knowledge.json", 0o600)
