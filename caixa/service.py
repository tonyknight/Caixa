"""The service layer: everything the interface and the command line can do, in one place.

`Service` holds one open box. `caixa worker` exposes its methods over JSON-RPC and `caixa …` calls
them directly, so anything the browser does can be scripted. Methods take and return plain data
(dicts, lists, strings, numbers) and raise `ServiceError` with a short `kind` a program can act on
and a message a person can read.

Methods that change the box are marked `write`; a read-only service (heir viewing, groundwork for
a later project) refuses every one of them and never writes anywhere in the box.
"""

from __future__ import annotations

import copy

import contextlib
import functools
import inspect
import mimetypes
import queue
import threading
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, TypeVar, Union

from caixa import settings, undo
from caixa.box import Box, BoxError
from caixa.collectors.base import Collector, PeopleAware, Progress
from caixa.collectors.inputs import InputError
from caixa.collectors.messages import alias_kind
from caixa.collectors.options import OptionsError, validate
from caixa.collectors.registry import Registry, discover
from caixa.jobs import FINISHED, JobStore
from caixa.state import State

PathLike = Union[str, Path]
TEXT_LIMIT = 2_000_000  # the largest text file `browse.file` includes in full


class ServiceError(Exception):
    """A request could not be done. `kind` says why in a word; the message says it in plain words."""

    kind = "error"

    def __init__(self, kind: str, message: str, data: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.data = data or {}


class ReadOnlyError(ServiceError):
    def __init__(self, method: str) -> None:
        super().__init__("read_only", f"This box is open read-only, so '{method}' is not allowed.")


@dataclass(frozen=True)
class Method:
    name: str  # the protocol name, such as "box.create"
    attribute: str  # the Python method
    write: bool


F = TypeVar("F", bound=Callable[..., Any])
_METHODS: dict[str, Method] = {}


def method(name: str, write: bool = False) -> Callable[[F], F]:
    """Expose a `Service` method under a protocol name; writes are refused when read-only."""

    def decorate(function: F) -> F:
        @functools.wraps(function)
        def guarded(self: "Service", *args: Any, **kwargs: Any) -> Any:
            if write and self.read_only:
                raise ReadOnlyError(name)
            return function(self, *args, **kwargs)

        _METHODS[name] = Method(name, function.__name__, write)
        return guarded  # type: ignore[return-value]

    return decorate


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")


def _entry(path: Path, shown: str) -> dict[str, Any]:
    info = path.stat()
    is_dir = path.is_dir()
    return {
        "name": path.name,
        "path": shown,
        "kind": "directory" if is_dir else "file",
        "size": None if is_dir else info.st_size,
        "modified": _iso(info.st_mtime),
    }


def _listing(folder: Path, show_hidden: bool = False) -> list[Path]:
    """Folders first, then files, each by name; names that start with a dot only when asked."""
    found = [p for p in folder.iterdir() if show_hidden or not p.name.startswith(".")]
    return sorted(found, key=lambda p: (not p.is_dir(), p.name.casefold()))


class JobCancelled(Exception):
    """Raised inside a running import, from its progress callback, when a person cancelled it."""


class _Pace:
    """Pass progress on at a pace a person can read: every change of stage, the first and last
    step of each stage, and otherwise at most one step every `interval` seconds. (An export can
    hold thousands of conversations; saving and announcing every one would slow the import.)"""

    def __init__(self, emit: Callable[[Progress], None], interval: float = 0.2) -> None:
        self.emit, self.interval = emit, interval
        self.stage: Optional[str] = None
        self.sent = 0.0
        self.held: Optional[Progress] = None

    def __call__(self, step: Progress) -> None:
        now = time.monotonic()
        changed = step.stage != self.stage
        finished = step.total is not None and step.current >= step.total
        if changed:
            self.flush()
        if changed or finished or now - self.sent >= self.interval:
            self.stage, self.sent, self.held = step.stage, now, None
            self.emit(step)
        else:
            self.held = step

    def flush(self) -> None:
        """Send the last step that was held back, if any."""
        held, self.held = self.held, None
        if held is not None:
            self.emit(held)


Listener = Callable[[str, dict[str, Any]], None]


class Service:
    METHODS = _METHODS

    def __init__(
        self,
        box: Optional[PathLike] = None,
        read_only: bool = False,
        registry: Optional[Registry] = None,
        roots: Optional[Sequence[PathLike]] = None,
        state: Optional[State] = None,
    ) -> None:
        self.state = state  # what to remember between runs; None keeps nothing
        self.read_only = read_only
        self.registry = registry or discover()
        self.roots = [Path(r).resolve() for r in (roots if roots is not None else [Path.home()])]
        self.box: Optional[Box] = None
        self.jobs: Optional[JobStore] = None
        self._listeners: list[Listener] = []
        self._queue: "queue.Queue[Optional[int]]" = queue.Queue()
        self._runner: Optional[threading.Thread] = None
        self._cancelled: set[int] = set()
        self._finished: dict[int, threading.Event] = {}
        self._lock = threading.Lock()
        self._previews: dict[str, threading.Event] = {}  # previews being watched, by token
        if box is not None:
            self.box_open(str(box))

    def close(self, cancel: bool = False) -> None:
        """Stop the runner. A job still running finishes its current step; with `cancel`, every
        unfinished job is cancelled first (for when whoever asked for them has gone away)."""
        if cancel and self.jobs is not None and not self.read_only:
            for job in self.jobs.list(limit=1000):
                if job["status"] in ("queued", "running"):
                    with self._lock:
                        self._cancelled.add(job["id"])
        with self._lock:
            runner, self._runner = self._runner, None
        if runner is not None:
            self._queue.put(None)
            runner.join(timeout=30)

    # --- Calling by name (what the worker and tests use) ------------------------------------

    def call(self, name: str, params: Optional[dict[str, Any]] = None) -> Any:
        """Run a method by its protocol name with keyword parameters."""
        known = self.METHODS.get(name)
        if known is None:
            raise ServiceError("unknown_method", f"There is no method '{name}'.")
        if known.write and self.read_only:  # before anything else, whatever the parameters
            raise ReadOnlyError(name)
        function = getattr(self, known.attribute)
        try:
            inspect.signature(function).bind(**(params or {}))
        except TypeError as error:
            raise ServiceError(
                "invalid_params", f"Wrong parameters for '{name}': {error}."
            ) from None
        return function(**(params or {}))

    # --- The box ----------------------------------------------------------------------------

    def _require_box(self) -> Box:
        if self.box is None:
            raise ServiceError(
                "no_box", "You need to open a box first (create one, or open an existing one)."
            )
        return self.box

    @method("box.create", write=True)
    def box_create(self, path: str, name: str = "", owner: str = "") -> dict[str, Any]:
        try:
            box = Box.create(path, name=name)
        except BoxError as error:
            raise ServiceError("conflict", str(error)) from None
        if owner.strip():
            with box.master() as master:
                master.add_person(owner, is_owner=True)
        self._attach(box)
        return self.box_status()

    @method("box.open")
    def box_open(self, path: str) -> dict[str, Any]:
        try:
            box = Box.open(path)
            box.status(read_only=self.read_only)
        except BoxError as error:
            raise ServiceError("not_found", str(error)) from None
        except (FileNotFoundError, RuntimeError) as error:
            raise ServiceError(
                "not_found",
                f"{path} can't be opened read-only yet: open it once with Caixa first ({error}).",
            ) from None
        self._attach(box)
        return self.box_status()

    def _attach(self, box: Box) -> None:
        """Make `box` the open box and open its jobs table (marking anything a crash left)."""
        self.close()
        self.box = box
        if self.state is not None:
            self.state.remember_box(str(box.root), box.name)
        path = box.caixa_dir / "jobs.sqlite"
        if self.read_only:
            self.jobs = JobStore(path, read_only=True) if path.is_file() else None
        else:
            self.jobs = JobStore(path)
            self.jobs.mark_interrupted()

    @method("box.status")
    def box_status(self) -> dict[str, Any]:
        return self._require_box().status(read_only=self.read_only)

    # --- Finding out what is wrong ----------------------------------------------------------

    @method("diagnostics.report")
    def diagnostics_report(
        self, collector: Optional[str] = None, source: Optional[str] = None
    ) -> dict[str, str]:
        """A text report to paste when something does not work; with a collector and a source, it
        also says what Caixa sees in that source. Names and numbers are never in it."""
        from caixa import diagnostics

        return {"text": diagnostics.report(self, collector, source)}

    # --- What is remembered between runs ----------------------------------------------------

    @method("session.get")
    def session_get(self) -> dict[str, Any]:
        """The boxes opened lately, and where you were in the open box (section, unfinished import)."""
        recent = self.state.recent_boxes() if self.state else []
        view: Optional[str] = None
        draft: Optional[dict[str, Any]] = None
        if self.state is not None and self.box is not None:
            view, draft = self.state.view(str(self.box.root))
        return {
            "recent": recent,
            "last_box": self.state.last_box() if self.state else None,
            "box": str(self.box.root) if self.box else None,
            "view": view,
            "draft": draft,
        }

    @method("session.set")
    def session_set(self, values: dict[str, Any]) -> dict[str, Any]:
        """Keep the section (`view`) and/or the import `draft` for the open box (`draft: null`
        clears it). This is saved beside Caixa's own files, not in the box, so it works read-only.
        """
        box = self._require_box()
        unknown = sorted(set(values) - {"view", "draft"})
        errors = [f"'{name}' is not something Caixa remembers." for name in unknown]
        view = values.get("view")
        if (
            "view" in values
            and view is not None
            and not (isinstance(view, str) and len(view) <= 40)
        ):
            errors.append("'view' must be a short text.")
        draft = values.get("draft")
        if "draft" in values and draft is not None and not isinstance(draft, dict):
            errors.append("'draft' must be an object, or null to clear it.")
        if errors:
            raise ServiceError("invalid_params", " ".join(errors), {"errors": errors})
        if self.state is not None:
            try:
                self.state.set_view(str(box.root), **{k: values[k] for k in values})
            except ValueError as error:
                raise ServiceError("invalid_params", str(error)) from None
        return self.session_get()

    @method("session.forget")
    def session_forget(self, path: str) -> dict[str, Any]:
        """Take a box off the recent list (the box itself is left alone)."""
        if self.state is not None:
            self.state.forget_box(path)
        return self.session_get()

    @method("collectors.list")
    def collectors_list(self) -> list[dict[str, Any]]:
        """Every collector; with a box open, an option that follows a box setting (`x-setting`)
        starts from that setting's value, so the wizard shows what the run will use."""
        described = self.registry.describe()
        if self.box is None:
            return described
        saved = settings.load(self.box)
        for entry in described:
            schema = copy.deepcopy(entry["options_schema"])
            for spec in schema["properties"].values():
                key = spec.get("x-setting")
                if key and key in saved:
                    spec["default"] = saved[key]
            entry["options_schema"] = schema
        return described

    # --- Settings ---------------------------------------------------------------------------

    @method("settings.get")
    def settings_get(self) -> dict[str, Any]:
        box = self._require_box()
        return {
            "values": settings.load(box),
            "schema": settings.SCHEMA,
            "box": {"root": str(box.root), "name": box.name},
        }

    @method("settings.set", write=True)
    def settings_set(self, values: dict[str, Any]) -> dict[str, Any]:
        box = self._require_box()
        try:
            settings.save(box, values)
        except OptionsError as error:
            raise ServiceError("invalid_params", str(error), {"errors": error.errors}) from None
        return self.settings_get()

    # --- Browsing the box -------------------------------------------------------------------

    def _inside_box(self, relative: str) -> Path:
        """A path in the visible part of the box: not outside it, not Caixa's own `.caixa/`."""
        root = self._require_box().root.resolve()
        wanted = (root / relative).resolve() if relative else root
        if Path(relative).is_absolute() or not wanted.is_relative_to(root):
            raise ServiceError("outside_roots", f"'{relative}' is outside the box.")
        parts = wanted.relative_to(root).parts
        if parts and parts[0] == ".caixa":
            raise ServiceError("outside_roots", "That part of the box belongs to Caixa itself.")
        if not wanted.exists():
            raise ServiceError("not_found", f"'{relative}' is not in the box.")
        return wanted

    @method("browse.list")
    def browse_list(self, path: str = "") -> dict[str, Any]:
        folder = self._inside_box(path)
        if not folder.is_dir():
            raise ServiceError("not_found", f"'{path}' is not a folder.")
        root = self._require_box().root.resolve()
        here = "" if folder == root else folder.relative_to(root).as_posix()
        entries = []
        for child in _listing(folder):
            if not child.resolve().is_relative_to(root):  # a link out of the box is not shown
                continue
            shown = f"{here}/{child.name}" if here else child.name
            entries.append(_entry(child, shown))
        return {"path": here, "entries": entries}

    @method("browse.file")
    def browse_file(self, path: str) -> dict[str, Any]:
        file = self._inside_box(path)
        if not file.is_file():
            raise ServiceError("not_found", f"'{path}' is not a file.")
        info = file.stat()
        mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        result: dict[str, Any] = {
            "path": file.relative_to(self._require_box().root.resolve()).as_posix(),
            "name": file.name,
            "mime": mime,
            "size": info.st_size,
            "modified": _iso(info.st_mtime),
            "absolute": str(file),
        }
        if mime.startswith("text/") and info.st_size <= TEXT_LIMIT:
            result["content"] = file.read_text(encoding="utf-8", errors="replace")
        return result

    # --- The file picker and the inbox ------------------------------------------------------

    def _inside_roots(self, path: Path) -> Path:
        resolved = path.expanduser().resolve()
        if not any(resolved == root or resolved.is_relative_to(root) for root in self.roots):
            raise ServiceError("outside_roots", f"{path} is outside the folders Caixa may show.")
        return resolved

    @method("files.list")
    def files_list(self, path: Optional[str] = None, show_hidden: bool = False) -> dict[str, Any]:
        """A folder's contents for the file picker, limited to the user's own folders."""
        folder = self._inside_roots(Path(path) if path else self.roots[0])
        if not folder.is_dir():
            raise ServiceError("not_found", f"{folder} is not a folder.")
        entries = []
        for child in _listing(folder, show_hidden):
            try:
                entries.append(_entry(child, str(child)))
            except OSError:  # a file that vanished or can't be read is simply left out
                continue
        parent = folder.parent if folder not in self.roots else None
        return {
            "path": str(folder),
            "parent": str(parent) if parent is not None else None,
            "roots": [str(r) for r in self.roots],
            "entries": entries,
        }

    @method("inbox.list")
    def inbox_list(self) -> dict[str, Any]:
        """What has been dropped into the box's `Inbox/`."""
        box = self._require_box()
        inbox = box.root / "Inbox"
        if not inbox.is_dir() and not self.read_only:
            inbox = box.inbox_dir
        entries = []
        if inbox.is_dir():
            for child in _listing(inbox):
                entry = _entry(child, child.name)
                entry["absolute"] = str(child.resolve())
                entries.append(entry)
        return {"path": str(inbox), "entries": entries}

    # --- Imports ----------------------------------------------------------------------------

    def _collector(self, collector_id: str) -> Collector:
        try:
            return self.registry.get(collector_id)
        except KeyError:
            raise ServiceError("not_found", f"No collector '{collector_id}'.") from None

    @staticmethod
    def _options(collector: Collector, options: Optional[dict[str, Any]]) -> dict[str, Any]:
        try:
            return validate(collector.info.options_schema, options or {})
        except OptionsError as error:
            raise ServiceError("invalid_params", str(error), {"errors": error.errors}) from None

    @method("import.preview")
    def import_preview(
        self,
        collector: str,
        source: str,
        options: Optional[dict[str, Any]] = None,
        token: Optional[str] = None,
    ) -> dict[str, Any]:
        """A dry run: what an import would bring in. Writes nothing to the box or the source.

        With a `token` (any text the caller chooses) the preview's progress is announced as
        `preview.progress` carrying that token, and `import.preview.cancel` can stop it.
        """
        box = self._require_box()
        found = self._collector(collector)
        checked = self._options(found, options)
        extra: dict[str, Any] = {}
        pace: Optional[_Pace] = None
        if token and "progress" in inspect.signature(found.preview).parameters:
            stop = threading.Event()
            with self._lock:
                self._previews[token] = stop
            pace = _Pace(
                lambda step: self._announce(
                    "preview.progress",
                    {
                        "token": token,
                        "stage": step.stage,
                        "current": step.current,
                        "total": step.total,
                        "message": step.message,
                    },
                )
            )
            watched = pace

            def report(step: Progress) -> None:
                if stop.is_set():
                    raise JobCancelled()
                watched(step)

            extra["progress"] = report
        try:
            return asdict(found.preview(Path(source).expanduser(), checked, box, **extra))
        except JobCancelled:
            raise ServiceError("cancelled", "The preview was cancelled.") from None
        except InputError as error:
            raise ServiceError("input", str(error), {"details": error.details}) from None
        finally:
            if pace is not None:
                pace.flush()
            if token:
                with self._lock:
                    self._previews.pop(token, None)

    @method("import.preview.cancel")
    def import_preview_cancel(self, token: str) -> dict[str, bool]:
        """Stop the preview that was started with this token (it ends with a 'cancelled' error)."""
        with self._lock:
            stop = self._previews.get(token)
        if stop is None:
            return {"cancelled": False}
        stop.set()
        return {"cancelled": True}

    @method("import.start", write=True)
    def import_start(
        self, collector: str, source: str, options: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Queue an import; it runs in the background (one at a time) and is followed as a job."""
        self._require_box()
        found = self._collector(collector)
        checked = self._options(found, options)
        path = Path(source).expanduser()
        if not path.exists():
            raise ServiceError("input", f"Not found: {path}")
        return self._enqueue("import", collector, str(path), checked)

    @method("import.undo.info")
    def import_undo_info(self) -> dict[str, Any]:
        """Which import can be undone now (the newest that has a snapshot), or why none can."""
        box = self._require_box()
        latest = undo.latest(box)
        if latest is None:
            return {"job": None, "reason": "There is no import to undo."}
        return {
            "job": latest["job"],
            "collector": latest["collector"],
            "source": latest["source"],
            "taken": latest["taken"],
            "people_changes": int(latest.get("people_changes", 0)),
            "reason": None,
        }

    @method("import.undo", write=True)
    def import_undo(self) -> dict[str, Any]:
        """Undo the newest import: the box goes back to how it was before it, including any
        naming of people done since. Runs as a job. The export it came from is not touched."""
        box = self._require_box()
        latest = undo.latest(box)
        if latest is None:
            raise ServiceError("conflict", "There is no import to undo.")
        busy = [j for j in self._jobs().list(limit=1000) if j["status"] in ("queued", "running")]
        if busy:
            raise ServiceError("busy", "Wait for the import that is running to finish, then undo.")
        return self._enqueue("undo", latest["collector"], latest["source"], {"job": latest["job"]})

    @method("import.again", write=True)
    def import_again(self, job: int) -> dict[str, Any]:
        """Run an earlier import again: the same source, the same options."""
        earlier = self._job(job)
        if earlier["kind"] != "import":
            raise ServiceError(
                "conflict", f"Job {job} is not an import, so it cannot be run again."
            )
        return self.import_start(earlier["collector"], earlier["source"], earlier["options"])

    @method("import.cancel", write=True)
    def import_cancel(self, job: int) -> dict[str, Any]:
        """Cancel a queued job at once, or a running one at its next step."""
        store = self._jobs()
        current = self._job(job)
        if current["status"] in FINISHED:
            raise ServiceError("conflict", f"Job {job} is already {current['status']}.")
        with self._lock:
            self._cancelled.add(job)
        if current["status"] == "queued":
            store.update(job, status="cancelled", message="Cancelled before it started.")
            self._announce("job.finished", self._job(job) | {"job": job})
            self._signal(job)
        return self._job(job)

    # --- Jobs -------------------------------------------------------------------------------

    def _jobs(self) -> JobStore:
        if self.jobs is None:
            raise ServiceError("not_found", "This box has no jobs yet.")
        return self.jobs

    def _job(self, job: int) -> dict[str, Any]:
        try:
            return self._jobs().get(job)
        except KeyError:
            raise ServiceError("not_found", f"There is no job {job}.") from None

    @method("jobs.list")
    def jobs_list(self, limit: int = 50, status: Optional[str] = None) -> list[dict[str, Any]]:
        self._require_box()
        return self.jobs.list(limit=limit, status=status) if self.jobs else []

    @method("jobs.get")
    def jobs_get(self, job: int) -> dict[str, Any]:
        self._require_box()
        return self._job(job)

    @method("jobs.log")
    def jobs_log(self, job: int, max_bytes: int = 65536) -> dict[str, Any]:
        """The end of a job's log: what a collector printed, and a traceback if it failed."""
        self._require_box()
        record = self._job(job)
        path = Path(record["log"]) if record.get("log") else None
        if path is None or not path.is_file():
            return {"text": "", "size": 0, "truncated": False}
        size = path.stat().st_size
        with open(path, "rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
            data = handle.read()
        return {
            "text": data.decode("utf-8", errors="replace"),
            "size": size,
            "truncated": size > max_bytes,
        }

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Be told about `job.progress` and `job.finished`; returns the function that stops it."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def wait(self, job: int, timeout: Optional[float] = None) -> dict[str, Any]:
        """Block until a job has finished (for scripts and tests); returns its final state."""
        with self._lock:
            event = self._finished.setdefault(job, threading.Event())
        if self._job(job)["status"] in FINISHED:
            return self._job(job)
        if not event.wait(timeout):
            raise ServiceError("busy", f"Job {job} is still running.")
        return self._job(job)

    def _announce(self, name: str, payload: dict[str, Any]) -> None:
        for listener in list(self._listeners):
            try:
                listener(name, payload)
            except Exception:  # a listener's bug must never stop an import
                continue

    def _signal(self, job: int) -> None:
        with self._lock:
            self._finished.setdefault(job, threading.Event()).set()

    def _enqueue(
        self, kind: str, collector: Optional[str], source: Optional[str], options: dict[str, Any]
    ) -> dict[str, Any]:
        box = self._require_box()
        number = self._jobs().create(kind, collector, source, options)
        self._jobs().update(number, log=str(box.logs_dir / f"job-{number}.log"))
        with self._lock:
            self._finished.setdefault(number, threading.Event())
            if self._runner is None:
                self._runner = threading.Thread(target=self._work, name="caixa-jobs", daemon=True)
                self._runner.start()
        self._queue.put(number)
        return self._job(number)

    def _work(self) -> None:
        while True:
            number = self._queue.get()
            if number is None:
                return
            try:
                self._run_job(number)
            except Exception:  # the runner itself must outlive any one job
                traceback.print_exc()

    def _run_job(self, number: int) -> None:
        box, store = self._require_box(), self._jobs()
        job = store.get(number)
        if job["status"] != "queued":  # cancelled while waiting
            self._signal(number)
            return
        if number in self._cancelled:  # cancelled by close() before it began
            store.update(number, status="cancelled", message="Cancelled before it started.")
            self._signal(number)
            return
        store.update(number, status="running", stage="starting")
        box.logs_dir.mkdir(parents=True, exist_ok=True)

        def save(step: Progress) -> None:
            store.update(
                number,
                stage=step.stage,
                current=step.current,
                total=step.total,
                message=step.message,
            )
            self._announce(
                "job.progress",
                {
                    "job": number,
                    "stage": step.stage,
                    "current": step.current,
                    "total": step.total,
                    "message": step.message,
                },
            )

        pace = _Pace(save)

        def progress(step: Progress) -> None:
            if number in self._cancelled:
                raise JobCancelled()
            pace(step)

        outcome: dict[str, Any]
        with open(job["log"], "a", encoding="utf-8", buffering=1) as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                try:
                    result = self._execute(box, job, progress)
                    outcome = {"status": "done", "result": result, "error": None}
                except JobCancelled:
                    outcome = {"status": "cancelled", "message": "Cancelled.", "error": None}
                except (InputError, ServiceError) as error:
                    outcome = {"status": "failed", "error": str(error)}
                except Exception as error:
                    traceback.print_exc()
                    outcome = {"status": "failed", "error": f"{type(error).__name__}: {error}"}
        if outcome["status"] == "done":
            pace.flush()  # the last step that was held back, before the job is marked done
        store.update(number, **outcome)
        self._announce("job.finished", self._job(number) | {"job": number})
        self._signal(number)

    def _execute(
        self, box: Box, job: dict[str, Any], progress: Callable[[Progress], None]
    ) -> dict[str, Any]:
        if job["kind"] == "undo":
            return self._undo(box, int(job["options"]["job"]), progress)
        if job["kind"] == "refresh":
            result = self._refresh_all(box, progress)
        else:
            collector = self._collector(job["collector"])
            undo.begin(box, job["id"], job["collector"], job["source"])
            try:
                result = asdict(collector.run(box, Path(job["source"]), job["options"], progress))
            finally:
                undo.finish(box, job["id"])  # however it ended, it can now be undone
        undo.note_moves(box, result.pop("moved", []))
        return result

    def _undo(self, box: Box, target: int, progress: Callable[[Progress], None]) -> dict[str, Any]:
        """Put the box back as it was before import `target`, then redraw the pages."""
        progress(Progress("undoing", message="Putting the box back as it was"))
        done = undo.restore(box, target)
        with box.master() as master:
            (last,) = master.connection.execute(
                "SELECT COALESCE(MAX(id), 0) FROM imports"
            ).fetchone()
        result = self._refresh_all(box, progress)
        result.pop("moved", None)
        with box.master() as master:
            # Redrawing the pages records itself as an import that changed nothing; that record
            # is not part of how the box was, so it goes.
            master.connection.execute(
                "DELETE FROM imports WHERE id > ? AND inserted = 0 AND updated = 0", (last,)
            )
            master.commit()
        store = self._jobs()
        before = store.get(target)
        store.update(target, result={**(before["result"] or {}), "undone": True})
        return {**result, **done, "undone_job": target, "inserted": 0, "updated": 0}

    def _refresh_all(self, box: Box, progress: Callable[[Progress], None]) -> dict[str, Any]:
        """Redraw pages for every working folder that can (once each); the last result is kept."""
        result: dict[str, Any] = {}
        for aware in self._people_aware():
            result = asdict(aware.refresh(box, progress))
        return result

    # --- People -----------------------------------------------------------------------------

    def _people_aware(self) -> list[PeopleAware]:
        """One collector for each working folder that can name its missing people."""
        chosen: dict[str, PeopleAware] = {}
        for collector in self.registry.all():
            if isinstance(collector, PeopleAware):
                chosen.setdefault(collector.work_key, collector)
        return list(chosen.values())

    @method("people.list")
    def people_list(self) -> dict[str, Any]:
        box = self._require_box()
        with box.master(read_only=self.read_only) as master:
            return {"people": master.summary()}

    @method("people.unresolved")
    def people_unresolved(self) -> dict[str, Any]:
        """Handles (a number, an address, a name) that no person is known for, busiest first."""
        box = self._require_box()
        handles = [h for aware in self._people_aware() for h in aware.unresolved(box)]
        handles.sort(key=lambda h: (-h["messages"], h["service"], h["identifier"]))
        return {"handles": handles}

    def _person(self, master: Any, who: Union[int, str]) -> int:
        """The id of a person given by id, or by name (a new name makes a new person)."""
        if isinstance(who, int) and not isinstance(who, bool):
            if not any(p.id == who for p in master.people()):
                raise ServiceError("not_found", f"There is no person {who}.")
            return who
        if not str(who).strip():
            raise ServiceError("invalid_params", "A person needs a name; the name was empty.")
        return int(master.add_person(str(who)))

    def _after_people_change(self, master: Any, person: int) -> dict[str, Any]:
        """The person as it now stands, plus the job that redraws the pages."""
        summary = next(p for p in master.summary() if p["id"] == person)
        master.commit()
        undo.note_people_change(self._require_box())  # undoing the newest import would undo this
        job = self._enqueue("refresh", None, None, {}) if self._people_aware() else None
        return {"person": summary, "job": job}

    @method("people.link", write=True)
    def people_link(
        self, service: str, identifier: str, person: Union[int, str], move: bool = False
    ) -> dict[str, Any]:
        """Say who a handle is. A phone or address then names that person on every service."""
        box = self._require_box()
        with box.master() as master:
            who = self._person(master, person)
            kind, scope = alias_kind(service, identifier)
            try:
                master.add_alias(who, identifier, kind, service=scope, move=move)
            except ValueError as error:
                master.connection.rollback()
                raise ServiceError(
                    "conflict", f"{error} Use move to give it to this person."
                ) from None
            return self._after_people_change(master, who)

    @method("people.rename", write=True)
    def people_rename(self, person: int, name: str) -> dict[str, Any]:
        box = self._require_box()
        if not name.strip():
            raise ServiceError("invalid_params", "A person needs a name; the name was empty.")
        with box.master() as master:
            who = self._person(master, person)
            try:
                master.rename_person(who, name)
            except ValueError as error:
                raise ServiceError("conflict", str(error)) from None
            return self._after_people_change(master, who)

    @method("people.merge", write=True)
    def people_merge(self, source: int, target: int) -> dict[str, Any]:
        """Fold `source` into `target` (they were the same person); the source disappears."""
        box = self._require_box()
        if source == target:
            raise ServiceError("invalid_params", "A person can't be merged with themselves.")
        with box.master() as master:
            self._person(master, source)
            who = self._person(master, target)
            try:
                master.merge_people(source, target)
            except ValueError as error:
                raise ServiceError("conflict", str(error)) from None
            return self._after_people_change(master, who)
