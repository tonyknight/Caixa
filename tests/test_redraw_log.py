"""A redraw tells the terminal what each step did, how many workers it used and how long it took."""

from __future__ import annotations

import io
import re
from pathlib import Path

from fixtures import family

from caixa.collectors.base import Progress
from caixa.service import Service, _Terminal


def _whatsapp(fixture_family) -> str:  # type: ignore[no-untyped-def]
    return str(fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt")


def test_a_closing_line_always_reaches_the_terminal() -> None:
    out = io.StringIO()
    tell = _Terminal(7, interval=60, out=out)
    tell(Progress("rendering", 1, 10, "Writing the pages (4 workers)"))
    tell(Progress("rendering", 5, 10, "Writing the pages (4 workers)"))  # (held back: too soon)
    tell(
        Progress(
            "rendering",
            10,
            10,
            "10 pages: 2 written, 8 unchanged · 4 workers · 1.2 s",
            summary=True,
        )
    )
    lines = out.getvalue().splitlines()
    assert lines == [
        "[caixa] job 7: rendering 1/10 - Writing the pages (4 workers)",
        "[caixa] job 7: rendering 10/10 - 10 pages: 2 written, 8 unchanged · 4 workers · 1.2 s",
    ]


def test_each_step_of_a_redraw_says_what_it_did(tmp_path: Path, fixture_family) -> None:  # type: ignore[no-untyped-def]
    service = Service(roots=[tmp_path])
    service.box_create(str(tmp_path / "Box"), name="Box", owner=family.OWNER.name)
    service.wait(service.import_start("whatsapp", _whatsapp(fixture_family))["id"], 60)
    steps: list[Progress] = []
    aware = service._people_aware()[0]
    aware.refresh(service._require_box(), steps.append)
    service.close()
    said = [s.message for s in steps if s.summary]
    assert len(said) == 4, said
    linked, filed, drawn, synced = said
    assert re.fullmatch(r"People matched · [\d.]+ s", linked)
    assert re.fullmatch(r"[\d,]+ files: [\d,]+ new, [\d,]+ moved · [\d.]+ s", filed)
    assert re.fullmatch(r"[\d,]+ pages: 0 written, [\d,]+ unchanged · 1 worker · [\d.]+ s", drawn)
    assert re.fullmatch(r"Box updated · [\d.]+ s", synced)
    rendering = [s for s in steps if s.stage == "rendering" and not s.summary]
    assert rendering and "worker" in rendering[0].message
