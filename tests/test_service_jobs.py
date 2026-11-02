"""The service layer: previews, imports as jobs, progress, cancelling, and surviving restarts."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import pytest
from fixtures import family

from caixa.box import Box
from caixa.collectors.base import CollectorInfo, Preview, Progress, RunResult
from caixa.collectors.inputs import InputError
from caixa.collectors.registry import Registry, discover
from caixa.jobs import JobStore
from caixa.service import ReadOnlyError, Service, ServiceError


def _whatsapp(fixture_family) -> str:
    return str(fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt")


@pytest.fixture
def service(tmp_path: Path) -> Service:
    with_box = Service(roots=[tmp_path])
    with_box.box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    yield with_box
    with_box.close()


class Fake:
    """A collector for tests: it can be told to wait, fail, print or report progress."""

    info = CollectorInfo(
        id="fake",
        name="Fake",
        platform="Test",
        inputs=("file",),
        how_to_export="Nothing to export; this is a test collector for the jobs table.",
        options_schema={
            "type": "object",
            "properties": {"mode": {"type": "string", "default": ""}},
        },
    )

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.running = 0
        self.most_at_once = 0
        self.runs: list[str] = []

    def preview(
        self, source: Path, options: Mapping[str, Any], box: Optional[Box] = None
    ) -> Preview:
        if not Path(source).exists():
            raise InputError(f"Not found: {source}")
        return Preview(items=3, conversations=1, first="2024-01-01", last="2024-01-02")

    def run(
        self,
        box: Box,
        source: Path,
        options: Mapping[str, Any],
        progress: Callable[[Progress], None],
    ) -> RunResult:
        self.running += 1
        self.most_at_once = max(self.most_at_once, self.running)
        self.runs.append(Path(source).name)
        try:
            mode = options.get("mode")
            progress(Progress("preparing"))
            print("hello from the collector")
            if mode == "boom":
                raise RuntimeError("the disk caught fire")
            if mode == "input":
                raise InputError("Nothing to import was found in there.")
            if mode == "wait":
                self.started.set()
                while not self.release.wait(0.01):
                    progress(Progress("importing", 1, 10))  # cancelling takes effect here
            progress(Progress("done"))
            return RunResult(inserted=3)
        finally:
            self.running -= 1


@pytest.fixture
def fake_service(tmp_path: Path) -> tuple[Service, Fake]:
    fake = Fake()
    registry = Registry()
    registry.register(fake, "test")
    owned = Service(registry=registry, roots=[tmp_path])
    owned.box_create(str(tmp_path / "Box"), owner=family.OWNER.name)
    yield owned, fake
    fake.release.set()
    owned.close()


def _source(tmp_path: Path, name: str = "export.txt") -> str:
    path = tmp_path / name
    path.write_text("x")
    return str(path)


# --- Previews -------------------------------------------------------------------------------


def test_a_preview_is_plain_data_and_writes_nothing(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    before = sorted(str(p) for p in (tmp_path / "Box").rglob("*") if not p.name.endswith("-wal"))
    preview = service.import_preview("whatsapp", _whatsapp(fixture_family))
    assert preview["items"] == 7 and preview["conversations"] == 1
    assert preview["first"] and preview["participants"] == ["Ana Costa"]
    json.dumps(preview)
    after = sorted(str(p) for p in (tmp_path / "Box").rglob("*") if not p.name.endswith("-wal"))
    assert before == after and service.jobs_list() == []


def test_a_preview_explains_a_missing_source(service: Service, tmp_path: Path) -> None:
    with pytest.raises(ServiceError, match="Not found") as stop:
        service.import_preview("whatsapp", str(tmp_path / "nothing.txt"))
    assert stop.value.kind == "input"


def test_every_option_problem_is_listed_at_once(service: Service, fixture_family) -> None:
    with pytest.raises(ServiceError) as stop:
        service.import_preview(
            "imessage", _whatsapp(fixture_family), {"spam_mode": "nope", "colour": 1}
        )
    assert stop.value.kind == "invalid_params" and len(stop.value.data["errors"]) == 2


def test_an_unknown_collector_is_not_found(service: Service, tmp_path: Path) -> None:
    with pytest.raises(ServiceError, match="No collector") as stop:
        service.import_preview("telegram", _source(tmp_path))
    assert stop.value.kind == "not_found"


# --- Running an import as a job -------------------------------------------------------------


def test_an_import_runs_as_a_job_and_ends_done(
    service: Service, fixture_family, tmp_path: Path
) -> None:
    job = service.import_start("whatsapp", _whatsapp(fixture_family))
    assert job["status"] in ("queued", "running") and job["collector"] == "whatsapp"
    done = service.wait(job["id"], timeout=60)
    assert done["status"] == "done" and done["stage"] == "done"
    assert done["result"]["inserted"] == 7 and done["error"] is None
    assert done["started_at"] and done["finished_at"]
    assert service.box_status()["items"] == 7
    assert [j["id"] for j in service.jobs_list()] == [job["id"]]
    assert (tmp_path / "Box" / "Messages" / "Ana Costa").is_dir()


def test_progress_is_stored_and_announced_in_order(service: Service, fixture_family) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    service.subscribe(lambda name, payload: events.append((name, payload)))
    job = service.import_start("mail", str(fixture_family.paths["mbox"]))
    service.wait(job["id"], timeout=60)
    names = [n for n, _ in events]
    assert names[-1] == "job.finished" and set(names) == {"job.progress", "job.finished"}
    stages = [p["stage"] for n, p in events if n == "job.progress"]
    order = ["preparing", "importing", "linking", "rendering", "syncing", "done"]
    assert stages[0] == "preparing" and stages[-1] == "done"
    assert stages == sorted(stages, key=order.index)
    assert all(p["job"] == job["id"] for _, p in events)
    assert events[-1][1]["status"] == "done"


def test_a_listener_that_fails_never_stops_the_job(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, _ = fake_service

    def broken(name: str, payload: dict[str, Any]) -> None:
        raise RuntimeError("listener bug")

    owned.subscribe(broken)
    assert owned.wait(owned.import_start("fake", _source(tmp_path))["id"], 30)["status"] == "done"


def test_options_are_checked_before_a_job_is_made(service: Service, fixture_family) -> None:
    with pytest.raises(ServiceError):
        service.import_start("imessage", _whatsapp(fixture_family), {"workers": 0})
    assert service.jobs_list() == []


def test_a_missing_source_makes_no_job(service: Service, tmp_path: Path) -> None:
    with pytest.raises(ServiceError, match="Not found") as stop:
        service.import_start("whatsapp", str(tmp_path / "nothing.txt"))
    assert stop.value.kind == "input" and service.jobs_list() == []


# --- Failures -------------------------------------------------------------------------------


def test_a_failure_is_recorded_in_plain_words_and_the_trace_goes_to_the_log(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, _ = fake_service
    job = owned.wait(owned.import_start("fake", _source(tmp_path), {"mode": "boom"})["id"], 30)
    assert job["status"] == "failed" and "the disk caught fire" in job["error"]
    assert "Traceback" in Path(job["log"]).read_text(encoding="utf-8")


def test_an_input_problem_is_just_its_message(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, _ = fake_service
    job = owned.wait(owned.import_start("fake", _source(tmp_path), {"mode": "input"})["id"], 30)
    assert job["status"] == "failed" and job["error"] == "Nothing to import was found in there."


def test_a_failed_job_does_not_stop_the_next_one(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, _ = fake_service
    bad = owned.import_start("fake", _source(tmp_path, "a.txt"), {"mode": "boom"})
    good = owned.import_start("fake", _source(tmp_path, "b.txt"))
    assert owned.wait(bad["id"], 30)["status"] == "failed"
    assert owned.wait(good["id"], 30)["status"] == "done"


def test_what_a_collector_prints_goes_to_the_jobs_log_not_the_screen(
    fake_service: tuple[Service, Fake], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    owned, _ = fake_service
    job = owned.wait(owned.import_start("fake", _source(tmp_path))["id"], 30)
    assert "hello from the collector" in Path(job["log"]).read_text(encoding="utf-8")
    assert "hello from the collector" not in capsys.readouterr().out


# --- Order and cancelling -------------------------------------------------------------------


def test_imports_run_one_at_a_time_in_the_order_given(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, fake = fake_service
    jobs = [owned.import_start("fake", _source(tmp_path, f"{n}.txt")) for n in "abc"]
    for job in jobs:
        owned.wait(job["id"], 30)
    assert fake.runs == ["a.txt", "b.txt", "c.txt"] and fake.most_at_once == 1


def test_a_running_job_can_be_cancelled(fake_service: tuple[Service, Fake], tmp_path: Path) -> None:
    owned, fake = fake_service
    job = owned.import_start("fake", _source(tmp_path), {"mode": "wait"})
    assert fake.started.wait(30)
    assert owned.import_cancel(job["id"])["status"] in ("running", "cancelled")
    done = owned.wait(job["id"], 30)
    assert done["status"] == "cancelled" and done["finished_at"]


def test_a_queued_job_can_be_cancelled_and_never_runs(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, fake = fake_service
    first = owned.import_start("fake", _source(tmp_path, "first.txt"), {"mode": "wait"})
    assert fake.started.wait(30)
    second = owned.import_start("fake", _source(tmp_path, "second.txt"))
    assert owned.import_cancel(second["id"])["status"] == "cancelled"
    fake.release.set()
    assert owned.wait(first["id"], 30)["status"] == "done"
    assert owned.wait(second["id"], 30)["status"] == "cancelled"
    assert fake.runs == ["first.txt"]


def test_cancelling_a_finished_or_unknown_job_is_explained(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, _ = fake_service
    job = owned.wait(owned.import_start("fake", _source(tmp_path))["id"], 30)
    with pytest.raises(ServiceError, match="already") as stop:
        owned.import_cancel(job["id"])
    assert stop.value.kind == "conflict"
    with pytest.raises(ServiceError) as missing:
        owned.import_cancel(999)
    assert missing.value.kind == "not_found"


# --- Listing and restarts -------------------------------------------------------------------


def test_jobs_list_newest_first_with_a_limit_and_a_status_filter(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, _ = fake_service
    ids = []
    for mode in ("", "boom", ""):
        job = owned.import_start("fake", _source(tmp_path), {"mode": mode})
        owned.wait(job["id"], 30)
        ids.append(job["id"])
    assert [j["id"] for j in owned.jobs_list()] == ids[::-1]
    assert [j["id"] for j in owned.jobs_list(limit=1)] == [ids[2]]
    assert [j["id"] for j in owned.jobs_list(status="failed")] == [ids[1]]
    assert owned.jobs_get(ids[0])["options"] == {"mode": ""}
    with pytest.raises(ServiceError) as stop:
        owned.jobs_get(999)
    assert stop.value.kind == "not_found"


def test_jobs_survive_a_restart_and_unfinished_ones_are_marked_interrupted(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, _ = fake_service
    done = owned.wait(owned.import_start("fake", _source(tmp_path))["id"], 30)
    store = JobStore(tmp_path / "Box" / ".caixa" / "jobs.sqlite")
    crashed = store.create("import", "fake", "x", {})
    store.update(crashed, status="running", stage="importing")
    waiting = store.create("import", "fake", "y", {})
    owned.close()

    again = Service(roots=[tmp_path])
    again.box_open(str(tmp_path / "Box"))
    try:
        by_id = {j["id"]: j for j in again.jobs_list()}
        assert by_id[done["id"]]["status"] == "done"
        assert (
            by_id[crashed]["status"] == "interrupted" and by_id[waiting]["status"] == "interrupted"
        )
        assert "stopped" in by_id[crashed]["error"]
    finally:
        again.close()


# --- Read-only ------------------------------------------------------------------------------


def test_a_read_only_service_lists_jobs_and_changes_none(
    fake_service: tuple[Service, Fake], tmp_path: Path
) -> None:
    owned, _ = fake_service
    job = owned.wait(owned.import_start("fake", _source(tmp_path))["id"], 30)
    store = JobStore(tmp_path / "Box" / ".caixa" / "jobs.sqlite")
    stuck = store.create("import", "fake", "x", {})
    store.update(stuck, status="running")
    viewer = Service(read_only=True, roots=[tmp_path], registry=owned.registry)
    viewer.box_open(str(tmp_path / "Box"))
    assert {j["id"] for j in viewer.jobs_list()} == {job["id"], stuck}
    assert viewer.jobs_get(stuck)["status"] == "running"  # not rewritten
    with pytest.raises(ReadOnlyError):
        viewer.import_start("fake", _source(tmp_path))
    with pytest.raises(ReadOnlyError):
        viewer.import_cancel(job["id"])
    assert (
        viewer.import_preview("fake", _source(tmp_path))["items"] == 3
    )  # a preview writes nothing
    viewer.close()


def test_a_read_only_service_with_no_jobs_file_has_no_jobs(tmp_path: Path) -> None:
    Service(roots=[tmp_path]).box_create(str(tmp_path / "Box"))
    (tmp_path / "Box" / ".caixa" / "jobs.sqlite").unlink(missing_ok=True)
    viewer = Service(read_only=True, roots=[tmp_path])
    viewer.box_open(str(tmp_path / "Box"))
    assert viewer.jobs_list() == []
    assert not (tmp_path / "Box" / ".caixa" / "jobs.sqlite").exists()


def test_the_job_store_survives_two_connections(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs.sqlite")
    number = store.create("import", "x", "s", {"a": 1})
    other = JobStore(tmp_path / "jobs.sqlite", read_only=True)
    assert other.get(number)["options"] == {"a": 1}
    with pytest.raises(sqlite3.OperationalError):
        sqlite3.connect(f"file:{tmp_path / 'jobs.sqlite'}?mode=ro", uri=True).execute(
            "DELETE FROM jobs"
        )


def test_real_collectors_are_the_ones_a_service_starts_with(tmp_path: Path) -> None:
    assert {c.info.id for c in discover().all()} >= {"whatsapp", "imessage"}
