"""Progress a person can follow: during the preview as well as the import, and not so chatty that
reporting it slows a large import down."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import pytest
from fixtures import family

from caixa.box import Box
from caixa.collectors.base import CollectorInfo, Preview, Progress, RunResult
from caixa.collectors.registry import Registry
from caixa.service import Service, ServiceError


class Steps:
    """A collector that reports `count` steps, slowly if asked, in its preview and its run."""

    info = CollectorInfo(
        id="steps",
        name="Steps",
        platform="Test",
        inputs=("file",),
        how_to_export="Nothing to export; this is a test collector that reports many steps.",
        options_schema={"type": "object", "properties": {}},
    )

    def __init__(self, count: int = 20, pause: float = 0.0) -> None:
        self.count, self.pause = count, pause
        self.reached = 0

    def _work(self, progress: Callable[[Progress], None]) -> None:
        progress(Progress("preparing", message="Reading"))
        for step in range(self.count):
            self.reached = step
            progress(Progress("importing", step, self.count, f"conversation {step}"))
            if self.pause:
                time.sleep(self.pause)
        progress(Progress("importing", self.count, self.count))

    def preview(
        self,
        source: Path,
        options: Mapping[str, Any],
        box: Optional[Box] = None,
        progress: Optional[Callable[[Progress], None]] = None,
    ) -> Preview:
        self._work(progress or (lambda step: None))
        return Preview(items=self.count, conversations=1, first="2024-01-01", last="2024-01-02")

    def run(
        self,
        box: Box,
        source: Path,
        options: Mapping[str, Any],
        progress: Callable[[Progress], None],
    ) -> RunResult:
        self._work(progress)
        progress(Progress("done", self.count))
        return RunResult(inserted=self.count, updated=0, unchanged=0, pages=1)


class Quiet(Steps):
    """An older collector whose preview takes no progress callback."""

    info = CollectorInfo(
        id="quiet",
        name="Quiet",
        platform="Test",
        inputs=("file",),
        how_to_export="Nothing to export; this is a test collector from before previews reported.",
        options_schema={"type": "object", "properties": {}},
    )

    def preview(  # type: ignore[override]
        self, source: Path, options: Mapping[str, Any], box: Optional[Box] = None
    ) -> Preview:
        return Preview(items=1, conversations=1, first=None, last=None)


def _service(tmp_path: Path, *collectors: Any) -> tuple[Service, list[tuple[str, dict[str, Any]]]]:
    registry = Registry()
    for collector in collectors:
        registry.register(collector, "test")
    service = Service(registry=registry, roots=[tmp_path])
    service.box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    heard: list[tuple[str, dict[str, Any]]] = []
    service.subscribe(lambda name, payload: heard.append((name, dict(payload))))
    return service, heard


def test_a_preview_reports_its_progress_when_asked_to(tmp_path: Path) -> None:
    service, heard = _service(tmp_path, Steps(count=5))
    result = service.import_preview("steps", str(tmp_path), token="p1")
    assert result["items"] == 5
    events = [payload for name, payload in heard if name == "preview.progress"]
    assert events and all(event["token"] == "p1" for event in events)
    assert events[0]["stage"] == "preparing"
    assert (events[-1]["stage"], events[-1]["current"], events[-1]["total"]) == ("importing", 5, 5)
    service.close()


def test_a_preview_nobody_is_watching_announces_nothing(tmp_path: Path) -> None:
    service, heard = _service(tmp_path, Steps(count=5))
    service.import_preview("steps", str(tmp_path))
    assert not [name for name, _ in heard if name == "preview.progress"]
    service.close()


def test_a_collector_that_cannot_report_its_preview_still_previews(tmp_path: Path) -> None:
    service, heard = _service(tmp_path, Quiet())
    assert service.import_preview("quiet", str(tmp_path), token="p1")["items"] == 1
    service.close()


def test_a_preview_can_be_cancelled(tmp_path: Path) -> None:
    collector = Steps(count=10_000, pause=0.002)
    service, _ = _service(tmp_path, collector)
    outcome: dict[str, Any] = {}

    def preview() -> None:
        try:
            outcome["result"] = service.import_preview("steps", str(tmp_path), token="p2")
        except ServiceError as error:
            outcome["error"] = error

    thread = threading.Thread(target=preview)
    thread.start()
    deadline = time.time() + 10
    while collector.reached < 5 and thread.is_alive() and time.time() < deadline:
        time.sleep(0.005)
    assert collector.reached >= 5, outcome
    assert service.import_preview_cancel("p2") == {"cancelled": True}
    thread.join(timeout=10)
    assert not thread.is_alive() and outcome["error"].kind == "cancelled"
    assert collector.reached < 9_000  # it stopped; it did not run to the end
    assert service.import_preview_cancel("nothing-like-it") == {"cancelled": False}
    service.close()


def test_the_real_collectors_report_each_conversation_in_the_preview(
    tmp_path: Path, fixture_family
) -> None:
    service = Service(roots=[tmp_path])
    service.box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    heard: list[dict[str, Any]] = []
    service.subscribe(lambda name, p: heard.append(dict(p)) if name == "preview.progress" else None)
    service.import_preview("whatsapp", str(fixture_family.paths["whatsapp"]), token="p3")
    importing = [e for e in heard if e["stage"] == "importing"]
    assert importing[-1]["current"] == importing[-1]["total"] == 3
    assert any(e["stage"] == "linking" for e in heard)  # and what comes after the reading
    service.close()


def test_many_quick_steps_are_not_all_announced_but_the_ends_are(tmp_path: Path) -> None:
    service, heard = _service(tmp_path, Steps(count=2_000))
    job = service.import_start("steps", str(tmp_path))
    done = service.wait(job["id"], 60)
    assert done["status"] == "done"
    events = [payload for name, payload in heard if name == "job.progress"]
    importing = [e for e in events if e["stage"] == "importing"]
    assert 2 <= len(importing) < 200  # 2,001 were reported
    assert importing[0]["current"] == 0 and importing[-1]["current"] == 2_000
    assert [e["stage"] for e in events if e["stage"] != "importing"] == ["preparing", "done"]
    service.close()


def test_a_slow_import_still_reports_as_it_goes(tmp_path: Path) -> None:
    service, heard = _service(tmp_path, Steps(count=8, pause=0.15))
    job = service.import_start("steps", str(tmp_path))
    service.wait(job["id"], 60)
    importing = [p for n, p in heard if n == "job.progress" and p["stage"] == "importing"]
    assert len(importing) >= 5  # a step every 150 ms is not too often to show
    service.close()


def test_progress_methods_are_known_and_a_preview_is_never_a_write() -> None:
    assert "import.preview.cancel" in Service.METHODS
    assert not Service.METHODS["import.preview"].write
    assert not Service.METHODS["import.preview.cancel"].write
