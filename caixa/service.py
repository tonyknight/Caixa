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
import email
import email.message
import email.policy
import email.utils
import json

import contextlib
import functools
import inspect
import mimetypes
import queue
import re
import sys
import threading
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Optional, Sequence, TypeVar, Union
from urllib.parse import urlparse

from chattr.pages import templates_fingerprint
from chattr.people import Contacts, mac_contacts_folder
from chattr.translation import TranslationError, is_local_endpoint

from caixa import owner as owner_file
from caixa import apple_intelligence, session_log, settings, summaries, translation, undo
from caixa.box import LAYOUT, Box, BoxError
from caixa.collectors.base import Cancelled, Collector, PeopleAware, Progress
from caixa.collectors.inputs import InputError
from caixa.documents import records as document_records
from caixa.collectors.messages import alias_kind
from caixa.collectors.options import OptionsError, validate
from caixa.collectors.registry import Registry, discover
from caixa.master import CATEGORIES
from caixa.reset import reset_box
from caixa.jobs import FINISHED, JobStore
from caixa.mail import clean as mail_clean
from caixa.mail import index as mail_index
from caixa.mail import records as mail_records
from caixa.mail import senders as mail_senders
from caixa.mail import write as mail_write
from caixa.state import State

PathLike = Union[str, Path]
TEXT_LIMIT = 2_000_000  # the largest text file `browse.file` includes in full
#: How long a search waits for the embedding model before it searches by words alone.
SEARCH_WAIT = 10


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


def _readable(folder: Path) -> bool:
    """Whether macOS lets this program list the Contacts folder (it refuses without Full Disk
    Access)."""
    try:
        next(folder.iterdir(), None)
    except OSError:
        return False
    return True


#: The jobs that write a session log (`caixa.session_log`), by the name each gives its file.
SESSION_KINDS = {
    "documents-enrich": "documents enrich",
    "documents-embed": "documents embed",
    "documents-reprocess": "documents reprocess",
}


def session_kind(job: Mapping[str, Any]) -> Optional[str]:
    """The name of a job's session log, or None for a job that keeps none."""
    if job["kind"] == "import" and job.get("collector") == "pdf":
        return "PDF import"
    return SESSION_KINDS.get(job["kind"])


@contextlib.contextmanager
def _no_session() -> Iterator[None]:
    yield


class JobCancelled(Cancelled):
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


#: How a job is getting on, written to the terminal Caixa was started from (`caixa serve` runs the
#: service in its own process, so its error stream is that terminal) with this mark in front.
TERMINAL_MARK = "[caixa] "


class _Terminal:
    """Tell the terminal that started Caixa how a job is getting on: each new stage, each
    recording put through speech-to-text, and otherwise a line every few seconds."""

    def __init__(self, job: int, interval: float = 5.0, out: Any = None) -> None:
        self.job, self.interval = job, interval
        self.out = out if out is not None else sys.__stderr__
        self.stage: Optional[str] = None
        self.message = ""
        self.sent = 0.0

    def __call__(self, step: Progress) -> None:
        now = time.monotonic()
        each = (step.stage == "transcribing" and step.message != self.message) or step.summary
        if step.stage == self.stage and not each and now - self.sent < self.interval:
            return
        self.stage, self.message, self.sent = step.stage, step.message, now
        count = f" {step.current:,}/{step.total:,}" if step.total else ""
        text = f"{TERMINAL_MARK}job {self.job}: {step.stage}{count}"
        if step.message:
            text += f" - {step.message}"
        try:
            print(text, file=self.out, flush=True)
        except (OSError, ValueError, AttributeError):
            pass  # no terminal to tell


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
        batch_pages: bool = False,
    ) -> None:
        self.state = state  # what to remember between runs; None keeps nothing
        #: Changes to people wait for `people.update` instead of each starting a redraw (Caixa's
        #: window: the owner sorts many people, then draws them all at once).
        self.batch_pages = batch_pages
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
        with self._lock:  # job numbers belong to a jobs table: another box's (or a reset's) restart
            self._finished.clear()
            self._cancelled.clear()
        self.box = box
        if not self.read_only and box.master_path.exists():
            with box.master() as master:  # what was typed into the owner's file while closed
                owner_file.apply(box, master, force=True)
        if self.state is not None:
            self.state.remember_box(str(box.root), box.name)
        path = box.caixa_dir / "jobs.sqlite"
        if self.read_only:
            self.jobs = JobStore(path, read_only=True) if path.is_file() else None
        else:
            self.jobs = JobStore(path)
            self.jobs.mark_interrupted()
            if box.layout < LAYOUT:
                self._move_files(box)
            elif box.pages != templates_fingerprint():
                self._redraw_older(box)
            elif box.pending()["changes"] and self._people_aware():
                # changes made last time and never drawn: draw them now
                self._refresh_job(str(box.pending()["scope"] or "pages"))

    def _redraw_older(self, box: Box) -> None:
        """Pages drawn by an older Caixa lack what this one draws (a page's script is brought up to
        date when it is served, its contents are not): draw them again, once. The drawing records
        the new templates, so the next opening starts nothing."""
        chattr_db = box.caixa_dir / "work" / "chattr" / "Database" / "chattr.sqlite"
        if chattr_db.is_file():
            self._enqueue("refresh", None, None, {"pages": "redrawn with this version of Caixa"})

    def _move_files(self, box: Box) -> None:
        """A box built before every source had an Attachments folder: draw its pages again, which
        moves its files there (filing follows where files belong); the box is marked once that has
        finished. Stopped or failed, it is started again the next time the box is opened."""
        chattr_db = box.caixa_dir / "work" / "chattr" / "Database" / "chattr.sqlite"
        if not chattr_db.is_file():
            box.mark_layout(LAYOUT)  # nothing filed yet
            return
        self._enqueue("refresh", None, None, {"layout": LAYOUT})

    @method("box.reset", write=True)
    def box_reset(self, forget_names: bool = False) -> dict[str, Any]:
        """Take out everything that was imported, keeping the box's settings, its owner and (unless
        `forget_names`) the names given by hand; see `caixa.reset`."""
        box = self._require_box()
        busy = [j for j in self._jobs().list(limit=1000) if j["status"] in ("queued", "running")]
        if busy:
            raise ServiceError(
                "busy", "An import is running. Wait for it to finish (or cancel it), then reset."
            )
        self.close()
        done = reset_box(box, forget_names=forget_names)
        self._attach(box)
        self._announce("box.reset", {"removed": done.removed})
        return {"removed": done.removed, "left": done.left, "names_kept": done.names_kept}

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
                flag = spec.get("x-on-when-set")
                if flag:
                    spec["default"] = saved.get(flag) not in (None, "")
            entry["options_schema"] = schema
        return described

    # --- Settings ---------------------------------------------------------------------------

    @method("settings.get")
    def settings_get(self) -> dict[str, Any]:
        box = self._require_box()
        values = settings.load(box)
        endpoint = str(values.get("translation.endpoint") or "")
        schema = copy.deepcopy(settings.SCHEMA)
        mac = apple_intelligence.check(build=False)
        if not mac["ready"] and mac["reason"] != "not_built":  # (not built yet: Test builds it)
            for name in ("summaries.provider", "translation.provider"):
                schema["properties"][name]["x-unavailable"] = {"apple": mac["message"]}
        return {
            "values": values,
            "schema": schema,
            "apple": {"ready": bool(mac["ready"]), "message": mac["message"]},
            "box": {"root": str(box.root), "name": box.name},
            # whether a key is saved for this endpoint; the key itself never leaves the worker
            "translation": {"key_saved": self._keys().get(endpoint) is not None},
        }

    @method("contacts.check")
    def contacts_check(self) -> dict[str, Any]:
        """How many people each source of contacts in the settings can name, so a person can
        see that it works: `mac` and `file` are each `{on, people, problem}`."""
        values = settings.load(self._require_box())
        region = str(values.get("contacts.region") or "US")
        folder = mac_contacts_folder()
        mac: dict[str, Any] = {"on": bool(values.get("contacts.mac")), "people": 0, "problem": ""}
        if mac["on"]:
            if sys.platform != "darwin" and not folder.is_dir():
                mac["problem"] = "not_a_mac"
            else:
                mac["people"] = len(Contacts.from_macos(folder, region))
                if not mac["people"]:
                    mac["problem"] = "no_access" if not _readable(folder) else "empty"
        path = str(values.get("contacts.file") or "").strip()
        file: dict[str, Any] = {"on": bool(path), "people": 0, "problem": ""}
        if path:
            try:
                file["people"] = len(Contacts.from_vcf(Path(path).expanduser(), region))
            except Exception as error:  # a file that is not a vCard, or cannot be read
                file["problem"] = str(error) or type(error).__name__
        return {"mac": mac, "file": file}

    def _keys(self) -> translation.Keys:
        return translation.Keys(self.state.path.parent if self.state is not None else None)

    @method("translation.key")
    def translation_key(self, endpoint: str, key: str) -> dict[str, Any]:
        """Save the key for this endpoint's host (an empty key forgets it). It is kept in
        Caixa's own folder, never in the box."""
        if key.strip() and not is_local_endpoint(endpoint):
            if urlparse(endpoint).scheme != "https":
                raise ServiceError(
                    "invalid_params",
                    "A key is only sent over https. Give an https:// endpoint first.",
                )
        self._keys().set(endpoint, key)
        return {"key_saved": self._keys().get(endpoint) is not None}

    @method("translation.test")
    def translation_test(self, values: dict[str, Any], key: str = "") -> dict[str, Any]:
        """Try the endpoint, model and key (the saved key unless one is given) with one fixed
        sentence. Nothing from the box is sent."""
        return translation.check(values, self._keys(), key or None)

    @method("apple.check")
    def apple_check(self) -> dict[str, Any]:
        """Whether Apple Intelligence (the Mac's own model) can be used now, or why not; the
        helper is not built here (Test builds it)."""
        return apple_intelligence.check(build=False)

    @method("summaries.test")
    def summaries_test(self, values: dict[str, Any], key: str = "") -> dict[str, Any]:
        """Try the summaries endpoint and model (translation's when empty) on a made-up
        conversation. Nothing from the box is sent."""
        return summaries.check(values, self._keys(), key or None)

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

    #: Mail is never imported whole: it is read, cleaned and sorted first, and only the chosen
    #: conversations come in (`mail.import`, which runs the Mail collector itself).
    WHOLE_MBOX = (
        "Mail is cleaned and sorted first, so an mbox is never imported whole: open Clean mail "
        "from the Mail card (or use 'caixa mail read', 'caixa mail clean', 'caixa mail senders' "
        "and 'caixa mail import')."
    )

    def _whole(self, collector_id: str) -> None:
        if collector_id == "mail":
            raise ServiceError("input", self.WHOLE_MBOX)

    def _collector(self, collector_id: str) -> Collector:
        try:
            return self.registry.get(collector_id)
        except KeyError:
            raise ServiceError("not_found", f"No collector '{collector_id}'.") from None

    def _options(self, collector: Collector, options: Optional[dict[str, Any]]) -> dict[str, Any]:
        given = dict(options or {})
        if self.box is not None:
            # an option that is on once a setting is set (transcribe, once a speech model is
            # saved) and was not mentioned at all: the setting decides
            saved = settings.load(self.box)
            for name, spec in collector.info.options_schema["properties"].items():
                flag = spec.get("x-on-when-set")
                if flag and name not in given:
                    given[name] = saved.get(flag) not in (None, "")
        try:
            return validate(collector.info.options_schema, given)
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
        self._whole(collector)
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
        self._whole(collector)
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
        terminal = _Terminal(number)

        def progress(step: Progress) -> None:
            if number in self._cancelled:
                raise JobCancelled()
            terminal(step)
            pace(step)

        outcome: dict[str, Any]
        kind = session_kind(job)
        with open(job["log"], "a", encoding="utf-8", buffering=1) as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                try:
                    with session_log.opened(box, number, kind) if kind else _no_session() as told:
                        result = self._execute(box, job, progress)
                    if isinstance(told, session_log.SessionLog):
                        result["session_log"] = told.path.relative_to(box.root).as_posix()
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
        if job["kind"] in ("import", "mail-import", "undo"):
            # these draw every page: the changes waiting when they began are drawn with them
            waiting = box.pending()
            result = self._execute_job(box, job, progress)
            box.take_pending(waiting)
            return result
        return self._execute_job(box, job, progress)

    def _execute_job(
        self, box: Box, job: dict[str, Any], progress: Callable[[Progress], None]
    ) -> dict[str, Any]:
        if job["kind"] == "undo":
            return self._undo(box, int(job["options"]["job"]), progress)
        if job["kind"] == "mail-read":
            return self._mail_read(box, job, progress)
        if job["kind"] == "mail-clean":
            return self._mail_clean_write(box, job, progress)
        if job["kind"] == "mail-reduce":
            return self._mail_reduce(box, job, progress)
        if job["kind"] == "mail-summarize":
            return self._mail_summarize(box, progress)
        if job["kind"] == "documents-embed":
            from caixa.documents.embeddings import embed_documents

            return embed_documents(box, progress=progress)
        if job["kind"] == "documents-enrich":
            from caixa.documents.enrich import enrich_documents

            options = job.get("options") or {}
            undo.begin(box, job["id"], "pdf", "enrich")
            try:
                read = enrich_documents(
                    box,
                    item_ids=options.get("item_ids") or None,
                    every=bool(options.get("all")),
                    progress=progress,
                )
            finally:
                undo.finish(box, job["id"])
            undo.note_moves(box, read.pop("moved", []))  # the files filed by their new names
            from caixa.documents.pages import draw_documents

            read["pages"] = len(draw_documents(box).written)
            return read
        if job["kind"] == "documents-reprocess":
            from caixa.documents.reprocess import reprocess

            options = job.get("options") or {}
            undo.begin(box, job["id"], "pdf", "reprocess")
            try:
                done = reprocess(
                    box,
                    item_ids=options.get("item_ids") or None,
                    failed_only=bool(options.get("failed")),
                    languages=options.get("languages") or None,
                    progress=progress,
                    keep=lambda relative: undo.keep_file(box, job["id"], relative),
                )
            finally:
                undo.finish(box, job["id"])
            from caixa.documents.pages import draw_documents

            done["pages"] = len(draw_documents(box).written)
            return done
        if job["kind"] == "mail-import":
            imported = self._mail_import(box, job, progress)
            undo.note_moves(box, imported.pop("moved", []))
            return imported
        if job["kind"] == "refresh":
            options = job.get("options") or {}
            moving = int(options.get("layout") or 0)
            if moving:
                progress(Progress("preparing", message="Moving files into Attachments folders"))
            waiting = box.pending()  # what this drawing covers (changes made meanwhile wait on)
            scope = str(options.get("scope") or "pages")
            result = self._refresh_all(box, progress, scope)
            if scope == "pages" or waiting["scope"] in (None, "index"):
                box.take_pending(waiting)
            if moving:
                box.mark_layout(moving)
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

    def _refresh_all(
        self, box: Box, progress: Callable[[Progress], None], scope: str = "pages"
    ) -> dict[str, Any]:
        """Redraw pages for every working folder that can (once each); the last result is kept."""
        result: dict[str, Any] = {}
        for aware in self._people_aware():
            result = asdict(aware.refresh(box, progress, scope))
        if scope == "pages":  # the documents' pages are drawn with the rest
            from caixa.documents.pages import draw_documents

            drawn = draw_documents(box)
            result["pages"] = int(result.get("pages") or 0) + len(drawn.written)
        return result

    # --- Mail -------------------------------------------------------------------------------

    @method("mail.read", write=True)
    def mail_read(
        self, source: str, account: Optional[str] = None, workers: Optional[int] = None
    ) -> dict[str, Any]:
        """Read an mbox (a file, a zip holding mboxes, or a folder) into the box's mail index, as
        a job. Nothing is imported. The account is needed unless the index already knows it."""
        box = self._require_box()
        path = Path(source).expanduser()
        if not path.exists():
            raise ServiceError("input", f"Not found: {path}")
        try:
            given = mail_index.check_account(account) if account is not None else None
        except mail_index.MailError as error:
            raise ServiceError("invalid_params", str(error)) from None
        if given is None:
            with mail_index.MailIndex.for_box(box, read_only=True) as index:
                if index.known_account(path) is None:
                    raise ServiceError(
                        "invalid_params", "An account name is needed (for example Gmail or Work)."
                    )
        options: dict[str, Any] = {"account": given}
        if workers is not None:
            options["workers"] = int(workers)
        return self._enqueue("mail-read", None, str(path), options)

    @method("mail.sources")
    def mail_sources(self) -> dict[str, Any]:
        """Every mbox read into the box's mail index."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            return {"sources": index.sources()}

    def _mail_people(self, box: Box) -> tuple[set[str], set[str], set[str]]:
        """(the owner's addresses, the box's people's addresses, their names) from the master."""
        with box.master(read_only=True) as master:
            people = {p.id: p for p in master.people()}
            owner_addresses, addresses = set(), set()
            for alias in master.aliases():
                if alias.kind != "email" or alias.person_id not in people:
                    continue
                if people[alias.person_id].is_owner:
                    owner_addresses.add(alias.normalized)
                else:
                    addresses.add(alias.normalized)
            names = {p.name for p in people.values() if not p.is_owner}
        return owner_addresses, addresses, names

    def _mail_source(self, index: mail_index.MailIndex, source: int) -> dict[str, Any]:
        row = index.connection.execute(
            "SELECT id, path, member, kind, account, mails, size FROM sources "
            "WHERE id = ? AND status = 'read'",
            (source,),
        ).fetchone()
        if row is None:
            raise ServiceError("not_found", "That mbox has not been read into the box's index.")
        return dict(zip(("id", "path", "member", "kind", "account", "mails", "size"), row))

    @staticmethod
    def _mail_folder(index: mail_index.MailIndex, source: int) -> str:
        """The folder an mbox's mail was exported from: the original mbox's name (for a Cleaned
        or Reduced copy, the one it came from), as Apple Mail and Thunderbird export one file per
        folder: a zip member's, an Apple Mail `<name>.mbox` folder's, or the file's name."""
        row = index.connection.execute(
            "SELECT path, member, parent_id FROM sources WHERE id = ?", (source,)
        ).fetchone()
        seen = {source}
        while row and row[2] and int(row[2]) not in seen:
            seen.add(int(row[2]))
            row = index.connection.execute(
                "SELECT path, member, parent_id FROM sources WHERE id = ?", (int(row[2]),)
            ).fetchone()
        if not row:
            return ""
        name = Path(str(row[1] or row[0]))
        if name.name == "mbox" and name.parent.name:  # Apple Mail: <name>.mbox/mbox
            name = name.parent
        stem = name.name[: -len(".mbox")] if name.name.lower().endswith(".mbox") else name.stem
        stem = re.sub(r"^\(\d{4}-\d{2}-\d{2}\)\s*", "", stem)
        return re.sub(r"\s*\[(Cleaned|Reduced)\]$", "", stem).strip()

    def _mail_owner(self, box: Box, index: mail_index.MailIndex, source: int) -> set[str]:
        """The owner's addresses for this mbox: the ones confirmed for its account (with the
        master's), else the master's and those the owner's Sent mail came from."""
        account = str(self._mail_source(index, source)["account"] or "")
        owner_addresses = self._mail_people(box)[0]
        confirmed = owner_file.mail_owner(box, account)
        if confirmed:
            return owner_addresses | set(confirmed)
        return owner_addresses | mail_clean.owner_addresses_from_sent(index)

    def _classify(self, box: Box, index: mail_index.MailIndex, source: int) -> None:
        self._mail_source(index, source)
        _, addresses, names = self._mail_people(box)
        owner_addresses = self._mail_owner(box, index, source)
        mail_clean.classify(
            index, source, owner_addresses, addresses, names, set(owner_file.mail_kept(box))
        )

    @method("mail.clean", write=True)
    def mail_clean(self, source: int) -> dict[str, Any]:
        """What cleaning this mbox would leave out, by group and sender (and the receipts it keeps),
        with the totals; the senders the owner kept, as far as this mbox has mail from them."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box) as index:
            self._classify(box, index, int(source))
            return self._clean_reply(box, index, int(source))

    def _clean_reply(self, box: Box, index: mail_index.MailIndex, source: int) -> dict[str, Any]:
        db = index.connection
        found = mail_clean.groups(index, source)
        info = self._mail_source(index, source)
        junk = [g for g in found if g.key != "receipts"]
        left_mails = sum(g.mails for g in junk)
        left_senders = len({r.address for g in junk for r in g.rows})
        everyone = db.execute(
            "SELECT COUNT(*) FROM senders WHERE source_id = ?", (source,)
        ).fetchone()[0]
        kept = set(owner_file.mail_kept(box))
        kept_senders = [
            {"address": a, "name": (json.loads(n) or [a])[0], "mails": m, "size": s}
            for a, n, m, s in db.execute(
                "SELECT address, names, mails, size FROM senders WHERE source_id = ? "
                "ORDER BY mails DESC, address",
                (source,),
            )
            if a in kept
        ]
        return {
            "source": info,
            "groups": [asdict(g) for g in found],
            "left_out": {
                "mails": left_mails,
                "size": sum(g.size for g in junk),
                "senders": left_senders,
            },
            "kept": {"mails": int(info["mails"]) - left_mails, "senders": everyone - left_senders},
            "kept_senders": kept_senders,
        }

    def _mail_imported(
        self, box: Box, index: mail_index.MailIndex, source: int, owner_addresses: set[str]
    ) -> set[str]:
        """The senders (and the owner's correspondents) all of whose mail in this mbox is in the
        box already: a sender with mail not yet imported stays to be imported."""
        with box.master(read_only=True) as master:
            in_box = {
                str(r[0])
                for r in master.connection.execute(
                    "SELECT message_id FROM mail WHERE message_id IS NOT NULL"
                )
            }
        if not in_box:
            return set()
        waiting: dict[str, int] = {}
        for sender, message_id, recipients in index.connection.execute(
            "SELECT sender_address, message_id, recipients FROM mails WHERE source_id = ?",
            (source,),
        ):
            missing = int(message_id not in in_box)
            people = [sender] if sender not in owner_addresses else []
            if sender in owner_addresses:
                people += [a for _, _, a in json.loads(recipients)]
            for address in people:
                if address:
                    waiting[address] = waiting.get(address, 0) + missing
        return {address for address, left in waiting.items() if left == 0}

    def _mail_choice(
        self, box: Box, index: mail_index.MailIndex, source: int
    ) -> tuple[set[str], set[str], set[str], mail_senders.Selection]:
        """(the chosen senders, the owner's addresses, the box's people's addresses, what the
        chosen bring) for an mbox, as Sort mail shows them."""
        reply = self._senders_reply(box, index, source)
        chosen = {
            r["address"] for c in reply["categories"] if c["key"] == "to_import" for r in c["rows"]
        }
        owner_addresses = self._mail_owner(box, index, source)
        _, addresses, _ = self._mail_people(box)
        return (
            chosen,
            owner_addresses,
            addresses,
            mail_senders.selection(index, source, chosen, owner_addresses, addresses),
        )

    def _mail_taken(self, box: Box, index: mail_index.MailIndex, source: int) -> set[int]:
        """The positions of an mbox's mails that are in the box: an import took them (and the box
        still has them), or their Message-ID is among the box's mail."""
        with box.master(read_only=True) as master:
            in_box = {
                str(r[0])
                for r in master.connection.execute(
                    "SELECT message_id FROM mail WHERE message_id IS NOT NULL"
                )
            }
        recorded = {
            int(r[0])
            for r in index.connection.execute(
                "SELECT position FROM imported WHERE source_id = ?", (source,)
            )
        }
        return {
            int(position)
            for position, message_id in index.connection.execute(
                "SELECT position, message_id FROM mails WHERE source_id = ?", (source,)
            )
            if message_id in in_box or (message_id is None and position in recorded)
        }

    @method("mail.reduce", write=True)
    def mail_reduce(self, source: int) -> dict[str, Any]:
        """Write the Reduced mbox (every mail not in the box, ignored senders' included) beside its
        source, as a job."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            info = self._mail_source(index, int(source))
        return self._enqueue("mail-reduce", None, str(info["path"]), {"source": int(source)})

    def _mail_reduce(
        self, box: Box, job: dict[str, Any], progress: Callable[[Progress], None]
    ) -> dict[str, Any]:
        source = int(job["options"]["source"])
        workers = int(settings.load(box)["workers"])
        try:
            with mail_index.MailIndex.for_box(box) as index:
                taken = self._mail_taken(box, index, source)
                rows = index.connection.execute(
                    "SELECT position, length FROM mails WHERE source_id = ?", (source,)
                ).fetchall()
                keep = [int(p) for p, _ in rows if int(p) not in taken]
                written = mail_write.write_mbox(
                    index, source, keep, "Reduced", workers=workers, progress=progress
                )
        except mail_index.MailError as error:
            raise ServiceError("input", str(error)) from None
        total = sum(int(n) for _, n in rows)
        return {
            "path": str(written.path),
            "source_id": written.source_id,
            "mails": written.mails,
            "size": written.size,
            "left_out": len(rows) - written.mails,
            "left_out_size": total - written.size,
        }

    @method("mail.import.preview")
    def mail_import_preview(self, source: int) -> dict[str, Any]:
        """What importing an mbox's chosen senders would bring: senders, conversations, mails, the
        files they carry, and their size."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            chosen, _, _, picked = self._mail_choice(box, index, int(source))
            positions = [p for mails in picked.threads.values() for p in mails]
            files = 0
            for start in range(0, len(positions), 500):
                chunk = positions[start : start + 500]
                marks = ", ".join("?" for _ in chunk)
                files += int(
                    index.connection.execute(
                        f"SELECT COALESCE(SUM(attachments), 0) FROM mails WHERE source_id = ? "
                        f"AND position IN ({marks})",
                        (int(source), *chunk),
                    ).fetchone()[0]
                )
        return {
            "senders": len(chosen),
            "conversations": len(picked.threads),
            "mails": picked.mails,
            "files": files,
            "size": picked.size,
        }

    @method("mail.import", write=True)
    def mail_import(
        self, source: int, translate: Optional[bool] = None, summarize: Optional[bool] = None
    ) -> dict[str, Any]:
        """Import the conversations an mbox's chosen senders bring, as a job (it can be undone).
        `translate` and `summarize` choose for this job; left out, the box's settings decide."""
        box = self._require_box()
        saved = settings.load(box)
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            info = self._mail_source(index, int(source))
            picked = self._mail_choice(box, index, int(source))[3]
        if not picked.mails:
            raise ServiceError("input", "Nothing is chosen to import from this mbox.")
        options = {
            "source": int(source),
            "translate": bool(saved.get("translation.enabled")) if translate is None else translate,
            "summarize": bool(saved.get("summaries.enabled")) if summarize is None else summarize,
        }
        return self._enqueue("mail-import", "mail", str(info["path"]), options)

    def _mail_import(
        self, box: Box, job: dict[str, Any], progress: Callable[[Progress], None]
    ) -> dict[str, Any]:
        source = int(job["options"]["source"])
        workers = int(settings.load(box)["workers"])
        progress(Progress("preparing", message="Taking the chosen conversations out of the mbox"))
        target = box.work_dir("mail") / f"import-{job['id']}.mbox"
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            account = str(self._mail_source(index, source)["account"] or "")
            folder = self._mail_folder(index, source)
            chosen, _, _, picked = self._mail_choice(box, index, source)
            positions = sorted(p for mails in picked.threads.values() for p in mails)
            marks = ", ".join("?" for _ in positions) or "NULL"
            seen = {
                str(r[0])
                for r in index.connection.execute(
                    f"SELECT message_id FROM mails WHERE source_id = ? AND position IN ({marks}) "
                    "AND message_id IS NOT NULL",
                    (source, *positions),
                )
            }
            mail_write.extract(index, source, positions, target)
        collector = self._collector("mail")
        undo.begin(box, job["id"], "mail", job["source"])
        try:
            result = asdict(
                collector.run(
                    box,
                    target,
                    {
                        "account": account,
                        "workers": workers,
                        "folder": folder,
                        "translate": job["options"].get("translate", True),
                    },
                    progress,
                )
            )
            with box.master() as master:
                recorded = mail_records.record_mail(
                    master, mail_records.chattr_database(box), account, seen
                )
        finally:
            undo.finish(box, job["id"])
            target.unlink(missing_ok=True)
        with mail_index.MailIndex.for_box(box) as index:  # what this import took, for Reduce
            index.connection.executemany(
                "INSERT OR IGNORE INTO imported (source_id, position, job) VALUES (?, ?, ?)",
                [(source, p, int(job["id"])) for p in positions],
            )
        warnings = list(result.get("warnings") or [])
        result["summaries"] = self._summarize(
            box, progress, warnings, after_import=True, wanted=job["options"].get("summarize", True)
        )
        result["warnings"] = warnings
        return {
            **result,
            "mails": picked.mails,
            "recorded": recorded["new"],
            "conversations": len(picked.threads),
            "senders": len(chosen),
            "account": account,
        }

    @method("mail.summarize", write=True)
    def mail_summarize(self) -> dict[str, Any]:
        """Summarize, as a job, every imported mail conversation that has no summary yet or has
        gained mails since its summary was written (with the endpoint and model in Settings)."""
        box = self._require_box()
        if not summaries.ready(settings.load(box)):
            raise ServiceError(
                "invalid_params",
                "Summaries are off, or have no endpoint or model. Turn them on in Settings, "
                "Summaries, and try them there first.",
            )
        return self._enqueue("mail-summarize", None, None, {})

    def _summarize(
        self,
        box: Box,
        progress: Callable[[Progress], None],
        warnings: list[str],
        after_import: bool = False,
        wanted: bool = True,
    ) -> dict[str, Any]:
        """Write the summaries that are missing, then redraw the pages when any was written.
        After an import nothing here fails it: what went wrong is a warning, the entries show
        the opening words, and `mail.summarize` can add the summaries later."""
        # this job's switch decides; Settings say what it starts as and how summaries are reached
        values = {**settings.load(box), "summaries.enabled": True}
        reason = None
        if not wanted:
            reason = "off_for_job" if settings.load(box).get("summaries.enabled") else "off"
        elif not summaries.ready(values):
            reason = "not_set_up"
        if reason:
            left = len(summaries.pending(box))
            return {"written": 0, "left": left, "model": "", "error": None, "reason": reason}
        later = " The entries show each conversation's first words until then; Summarize mail adds the summaries later."
        try:
            outcome = summaries.run(box, values, progress, self._keys())
        except JobCancelled:
            if not after_import:
                raise
            warnings.append("Summaries were stopped." + later)
            return {
                "written": 0,
                "left": len(summaries.pending(box)),
                "model": "",
                "error": "stopped",
                "reason": "failed",
            }
        except TranslationError as error:  # (the settings could not make a client)
            outcome = {
                "written": 0,
                "left": len(summaries.pending(box)),
                "model": "",
                "error": str(error),
            }
        if outcome["error"]:
            warnings.append(f"Some summaries could not be written: {outcome['error']}." + later)
        if outcome.get("declined"):
            count = int(outcome["declined"])
            warnings.append(
                f"{count} conversation{'s were' if count != 1 else ' was'} declined by "
                f"{outcome['model']}'s safety filter; {'their entries' if count != 1 else 'its entry'} "
                "show the first words instead."
            )
        if outcome["written"]:
            self._refresh_all(box, progress)  # the pages, with the summaries
        outcome["reason"] = (
            "failed" if outcome["error"] and not outcome["written"]
            else "nothing_new" if not outcome["written"] else None
        )  # fmt: skip
        return outcome

    def _mail_summarize(self, box: Box, progress: Callable[[Progress], None]) -> dict[str, Any]:
        warnings: list[str] = []
        outcome = self._summarize(box, progress, warnings)
        if outcome["error"] and not outcome["written"]:
            raise ServiceError("input", f"No summary could be written: {outcome['error']}")
        return {**outcome, "warnings": warnings}

    def _senders_reply(self, box: Box, index: mail_index.MailIndex, source: int) -> dict[str, Any]:
        info = self._mail_source(index, source)
        owner_addresses = self._mail_owner(box, index, source)
        _, addresses, names = self._mail_people(box)
        with box.master(read_only=True) as master:
            people = {p.id: p.name for p in master.people() if not p.is_owner}
            known = {
                a.normalized: people[a.person_id]
                for a in master.aliases()
                if a.kind == "email" and a.person_id in people
            }
        decided = owner_file.load(box)["mail"]
        lineage: dict[str, str] = {}
        parent = index.connection.execute(
            "SELECT parent_id FROM sources WHERE id = ?", (source,)
        ).fetchone()
        while parent and parent[0]:
            ancestor = int(parent[0])
            gone = self._mail_imported(box, index, ancestor, owner_addresses)
            for address, names_json in index.connection.execute(
                "SELECT address, names FROM senders WHERE source_id = ?", (ancestor,)
            ):
                if address in gone:
                    lineage.setdefault(address, (json.loads(names_json) or [address])[0])
            parent = index.connection.execute(
                "SELECT parent_id FROM sources WHERE id = ?", (ancestor,)
            ).fetchone()
        categories = mail_senders.listing(
            index,
            source,
            owner_addresses,
            known,
            {n.casefold(): n for n in names},
            set(decided["chosen"]),
            set(decided["ignored"]),
            self._mail_imported(box, index, source, owner_addresses),
            lineage,
        )
        chosen = {r.address for c in categories if c.key == "to_import" for r in c.rows}
        picked = mail_senders.selection(index, source, chosen, owner_addresses, addresses)
        return {
            "source": info,
            "categories": [asdict(c) for c in categories],
            "selection": {
                "threads": len(picked.threads),
                "mails": picked.mails,
                "size": picked.size,
                "senders": len(chosen),
            },
        }

    @method("mail.senders")
    def mail_senders(self, source: int) -> dict[str, Any]:
        """An mbox's senders in the Sort mail window's categories (Known, To sort, To import,
        Ignored, Imported), and what importing the chosen ones would bring."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            return self._senders_reply(box, index, int(source))

    @method("mail.choose", write=True)
    def mail_choose(self, source: int, addresses: list[str], choose: bool = True) -> dict[str, Any]:
        """Choose senders to import (or forget the choice); remembered in `owner.json`."""
        owner_file.set_mail_decision(self._require_box(), [str(a) for a in addresses], "chosen",
                                     on=bool(choose))  # fmt: skip
        return self.mail_senders(int(source))

    @method("mail.ignore", write=True)
    def mail_ignore(self, source: int, addresses: list[str], ignore: bool = True) -> dict[str, Any]:
        """Ignore senders (or stop ignoring them); remembered in `owner.json`. Their mail stays in
        the mbox (a Reduced mbox keeps it)."""
        owner_file.set_mail_decision(self._require_box(), [str(a) for a in addresses], "ignored",
                                     on=bool(ignore))  # fmt: skip
        return self.mail_senders(int(source))

    @method("mail.selection")
    def mail_selection(self, source: int) -> dict[str, Any]:
        """What importing the chosen senders of an mbox would bring: threads, mails and size."""
        return dict(self.mail_senders(int(source))["selection"])

    @method("mail.owner")
    def mail_owner(self, source: int) -> dict[str, Any]:
        """The owner's addresses for an mbox's account: the ones confirmed, and the ones proposed
        (the box's owner aliases and the addresses of the owner's Sent mail; failing both, the
        commonest sender)."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            account = str(self._mail_source(index, int(source))["account"] or "")
            proposed = self._mail_people(box)[0] | mail_clean.owner_addresses_from_sent(index)
            if not proposed:
                row = index.connection.execute(
                    "SELECT address FROM senders WHERE source_id = ? ORDER BY mails DESC LIMIT 1",
                    (int(source),),
                ).fetchone()
                proposed = {str(row[0])} if row else set()
        return {
            "account": account,
            "confirmed": owner_file.mail_owner(box, account),
            "proposed": sorted(proposed),
        }

    @method("mail.owner.set", write=True)
    def mail_owner_set(self, source: int, addresses: list[str]) -> dict[str, Any]:
        """Confirm the owner's addresses for an mbox's account."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            account = str(self._mail_source(index, int(source))["account"] or "")
        owner_file.set_mail_owner(box, account, [str(a) for a in addresses])
        return self.mail_owner(int(source))

    @method("mail.keep", write=True)
    def mail_keep(self, source: int, addresses: list[str], keep: bool = True) -> dict[str, Any]:
        """Keep senders when cleaning (their mail is never left out), or stop keeping them; the
        owner's choice is remembered in `owner.json`. Answers as `mail.clean` does."""
        box = self._require_box()
        owner_file.set_mail_kept(box, [str(a) for a in addresses], keep=bool(keep))
        return self.mail_clean(int(source))

    @method("mail.preview")
    def mail_preview(self, source: int, address: str, limit: int = 50) -> dict[str, Any]:
        """A sender's mails in an mbox, latest first: date, subject, recipients and a snippet."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            rows = index.connection.execute(
                "SELECT position, date_utc, tz_offset_minutes, subject, recipients, snippet, "
                "length, attachments FROM mails WHERE source_id = ? AND sender_address = ? "
                "ORDER BY date_utc DESC, position DESC LIMIT ?",
                (int(source), str(address).strip().lower(), int(limit)),
            ).fetchall()
        return {
            "mails": [
                {"position": p, "date": d, "offset": o, "subject": s,
                 "recipients": json.loads(r), "snippet": n, "size": z, "attachments": a}
                for p, d, o, s, r, n, z, a in rows
            ]
        }  # fmt: skip

    @method("mail.message")
    def mail_message(self, source: int, position: int) -> dict[str, Any]:
        """One mail, read from its mbox: its headers and its text (never its HTML as such)."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            try:
                data = index.mail_bytes(int(source), int(position))
            except mail_index.MailError as error:
                raise ServiceError("not_found", str(error)) from None
        message = email.message_from_bytes(data.partition(b"\n")[2], policy=email.policy.default)
        assert isinstance(message, email.message.EmailMessage)

        def people(name: str) -> list[list[str]]:
            values = [str(v) for v in message.get_all(name, [])]
            return [[n, a.lower()] for n, a in email.utils.getaddresses(values) if a]

        sender = (people("From") or [["", ""]])[0]
        text = mail_clean.body_text(message)
        return {
            "from": sender,
            "to": people("To"),
            "cc": people("Cc"),
            "subject": str(message.get("Subject", "") or ""),
            "date": str(message.get("Date", "") or ""),
            "text": text[:200_000],
            "attachments": [
                part.get_filename() or part.get_content_type()
                for part in message.iter_attachments()
            ],
        }

    @method("mail.clean.write", write=True)
    def mail_clean_write(self, source: int) -> dict[str, Any]:
        """Write the Cleaned mbox (every mail cleaning keeps) beside its source, as a job."""
        box = self._require_box()
        with mail_index.MailIndex.for_box(box, read_only=True) as index:
            row = index.connection.execute(
                "SELECT path FROM sources WHERE id = ? AND status = 'read'", (int(source),)
            ).fetchone()
        if row is None:
            raise ServiceError("not_found", "That mbox has not been read into the box's index.")
        return self._enqueue("mail-clean", None, str(row[0]), {"source": int(source)})

    def _mail_clean_write(
        self, box: Box, job: dict[str, Any], progress: Callable[[Progress], None]
    ) -> dict[str, Any]:
        source = int(job["options"]["source"])
        workers = int(settings.load(box)["workers"])
        try:
            with mail_index.MailIndex.for_box(box) as index:
                self._classify(box, index, source)
                positions = [
                    int(p)
                    for p, flags, protections in index.connection.execute(
                        "SELECT position, flags, protections FROM mails WHERE source_id = ?",
                        (source,),
                    )
                    if not (json.loads(flags) and not json.loads(protections))
                ]
                total, size = index.connection.execute(
                    "SELECT COUNT(*), SUM(length) FROM mails WHERE source_id = ?", (source,)
                ).fetchone()
                written = mail_write.write_mbox(
                    index, source, positions, "Cleaned", workers=workers, progress=progress
                )
        except mail_index.MailError as error:
            raise ServiceError("input", str(error)) from None
        return {
            "path": str(written.path),
            "source_id": written.source_id,
            "mails": written.mails,
            "size": written.size,
            "left_out": int(total) - written.mails,
            "left_out_size": int(size or 0) - written.size,
        }

    def _mail_read(
        self, box: Box, job: dict[str, Any], progress: Callable[[Progress], None]
    ) -> dict[str, Any]:
        options = job["options"]
        workers = int(options.get("workers") or settings.load(box)["workers"])
        try:
            with mail_index.MailIndex.for_box(box) as index:
                results = index.read(job["source"], options.get("account"), workers, progress)
        except mail_index.MailError as error:
            raise ServiceError("input", str(error)) from None
        return {"mails": sum(r.mails for r in results), "sources": [asdict(r) for r in results]}

    # --- People -----------------------------------------------------------------------------

    def _people_aware(self) -> list[PeopleAware]:
        """One collector for each working folder that can name its missing people."""
        chosen: dict[str, PeopleAware] = {}
        for collector in self.registry.all():
            if isinstance(collector, PeopleAware):
                chosen.setdefault(collector.work_key, collector)
        return list(chosen.values())

    # --- Documents --------------------------------------------------------------------------

    @method("documents.list")
    def documents_list(
        self,
        type: Optional[str] = None,
        author: Optional[str] = None,
        year: Optional[int] = None,
        status: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> dict[str, Any]:
        """The box's documents by date (undated last), optionally only some."""
        box = self._require_box()
        with box.master(read_only=self.read_only) as master:
            found = document_records.list_documents(
                master, type=type, author=author, year=year, status=status, tag=tag
            )
        return {"documents": found}

    @method("documents.get")
    def documents_get(self, item_id: str) -> dict[str, Any]:
        """Everything known about one document: facts, sources, tags, fields, runs."""
        box = self._require_box()
        with box.master(read_only=self.read_only) as master:
            try:
                return document_records.get_document(master, item_id)
            except KeyError:
                raise ServiceError("not_found", f"There is no document {item_id}.") from None

    @method("documents.ask")
    def documents_ask(self, question: str) -> dict[str, Any]:
        """A question answered by the model on this computer from the passages search finds,
        citing each as `[n]` with its document and page; an answer citing a passage it was not
        given is refused (`caixa.documents.ask`)."""
        from caixa.documents.ask import ask_documents

        return ask_documents(self._require_box(), question)

    @method("documents.embed", write=True)
    def documents_embed(self) -> dict[str, Any]:
        """Embed the documents' passages, as a job, so search finds them by meaning too: the
        documents with no vectors yet from the embedding model in Settings."""
        return self._enqueue("documents-embed", "pdf", "embed", {})

    @method("documents.search")
    def documents_search(
        self,
        query: str = "",
        type: Optional[str] = None,
        category: Optional[str] = None,
        author: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
        ocr_status: Optional[str] = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """The pages of documents that hold every word asked for, best first, each with its
        document, page and a snippet; filters narrow by the documents' facts."""
        from caixa.documents import search as document_search

        from caixa.documents import embeddings

        box = self._require_box()
        try:  # with an embedding model, by meaning too
            embed, model = embeddings.embedder(settings.load(box), timeout=SEARCH_WAIT)
        except embeddings.EmbeddingsUnavailable:
            embed, model = None, None
        with box.master(read_only=self.read_only) as master:
            hits = document_search.search(
                master, query, type=type, category=category, author=author,
                date_from=date_from, date_to=date_to, tag=tag, status=status,
                ocr_status=ocr_status, limit=max(1, min(int(limit), 500)),
                embed=embed, model=model,
            )  # fmt: skip
        return {"query": document_search.fts_query(query), "hits": hits}

    @method("documents.log")
    def documents_log(self, job: Optional[int] = None) -> dict[str, Any]:
        """A document job's session log (`caixa.session_log`): the latest, or job `job`'s. Its
        path and its JSON-lines twin's, relative to the box, its job and its text."""
        box = self._require_box()
        folder = box.logs_dir / "sessions"
        found = {}
        for path in folder.glob("*.log") if folder.is_dir() else []:
            named = re.search(r"\(job (\d+)\)\.log$", path.name)
            if named and (job is None or int(named.group(1)) == int(job)):
                found[(path.name[:19], int(named.group(1)))] = path  # started, then job
        if not found:
            raise ServiceError(
                "not_found",
                (
                    f"No session log for job {job}."
                    if job is not None
                    else "No session log yet: "
                    "PDF imports and the documents' enrich, embed and reprocess jobs write one."
                ),
            )
        (_, number), path = max(found.items())
        return {
            "path": path.relative_to(box.root).as_posix(),
            "events_path": path.with_suffix(".jsonl").relative_to(box.root).as_posix(),
            "job": number,
            "text": path.read_text(encoding="utf-8", errors="replace"),
        }

    @method("documents.enrich", write=True)
    def documents_enrich(
        self, item_ids: Optional[list[str]] = None, all: bool = False
    ) -> dict[str, Any]:
        """Read documents with the model, as a job: those named, every one (`all`), or those
        still waiting to be read."""
        options = {"item_ids": list(item_ids or []), "all": bool(all)}
        return self._enqueue("documents-enrich", "pdf", "enrich", options)

    @method("documents.authors")
    def documents_authors(self) -> dict[str, Any]:
        """Every author documents are filed under, with aliases and counts."""
        from caixa.documents import authors

        box = self._require_box()
        with box.master(read_only=self.read_only) as master:
            return {"authors": authors.list_authors(master)}

    def _author_change(
        self, change: Callable[[Box, Any], list[tuple[str, str]]], keep: int
    ) -> dict[str, Any]:
        from caixa.documents import authors

        box = self._require_box()
        with box.master() as master:
            try:
                moved = change(box, master)
            except KeyError:
                raise ServiceError("not_found", "There is no such author.") from None
            except ValueError as error:
                raise ServiceError("conflict", str(error)) from None
            master.commit()
            found = next(a for a in authors.list_authors(master) if a["id"] == keep)
        undo.note_moves(box, moved)
        from caixa.documents.pages import draw_documents

        draw_documents(box)
        return {"author": found, "moved": len(moved)}

    @method("documents.authors.rename", write=True)
    def documents_authors_rename(self, author_id: int, name: str) -> dict[str, Any]:
        """Rename an author: its folders and its documents' names follow."""
        from caixa.documents import authors

        return self._author_change(
            lambda box, master: authors.rename(box, master, int(author_id), name), int(author_id)
        )

    @method("documents.authors.merge", write=True)
    def documents_authors_merge(self, source: int, target: int) -> dict[str, Any]:
        """Give one author's documents and aliases to another, which keeps its name."""
        from caixa.documents import authors

        return self._author_change(
            lambda box, master: authors.merge(box, master, int(source), int(target)), int(target)
        )

    @method("documents.tags", write=True)
    def documents_tags(
        self, item_id: str, add: Optional[list[str]] = None, remove: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """The owner adds tags to a document and removes any (a removed tag stays removed)."""
        from caixa.documents.tags import change_tags

        box = self._require_box()
        with box.master() as master:
            try:
                document_records.get_document(master, item_id)
            except KeyError:
                raise ServiceError("not_found", f"There is no document {item_id}.") from None
            tags = change_tags(master, item_id, add, remove)
        from caixa.documents.pages import draw_documents

        draw_documents(box)
        return {"item_id": item_id, "tags": tags}

    @method("documents.tags.starter", write=True)
    def documents_tags_starter(
        self, add: Optional[list[str]] = None, remove: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """Grow or shrink the starter set of tags the model is shown."""
        from caixa.documents.tags import change_starter

        box = self._require_box()
        with box.master() as master:
            return {"starter": change_starter(master, add, remove)}

    @method("documents.update", write=True)
    def documents_update(
        self,
        item_id: str,
        author: Optional[str] = None,
        date: Optional[str] = None,
        title: Optional[str] = None,
        type: Optional[str] = None,
    ) -> dict[str, Any]:
        """The owner corrects a document (its author, date, title or type): recorded as theirs,
        the file renamed and moved at once; the pages are drawn with the next Update of the pages
        in Caixa's window (at once otherwise)."""
        from caixa.documents.corrections import CorrectionError, correct
        from caixa.documents.pages import draw_documents

        box = self._require_box()
        with box.master() as master:
            try:
                moves = correct(box, master, item_id, author, date, title, type)
            except KeyError:
                raise ServiceError("not_found", f"There is no document {item_id}.") from None
            except CorrectionError as error:
                raise ServiceError("invalid_params", str(error)) from None
            master.commit()
            found = document_records.get_document(master, item_id)
        undo.note_moves(box, moves)
        if self.batch_pages:
            pending = box.add_pending("pages")
            self._announce("pages.pending", pending)
        else:
            draw_documents(box)
            pending = box.pending()
        return {"document": found, "moved": len(moves), "pending": pending}

    @method("documents.review")
    def documents_review(self) -> dict[str, Any]:
        """The documents waiting for the owner: why each waits, and what is known to choose from."""
        from caixa.documents.corrections import candidates
        from caixa.documents.pages import REASONS

        box = self._require_box()
        with box.master(read_only=self.read_only) as master:
            waiting = document_records.list_documents(master, status="needs_review")
            return {
                "documents": [
                    {
                        "item_id": d["item_id"], "title": d["title"],
                        "original_filename": d["original_filename"], "file_path": d["file_path"],
                        "reasons": [REASONS.get(r, r) for r in d["review"]],
                        "candidates": candidates(master, d["item_id"]),
                    }
                    for d in waiting
                ]
            }  # fmt: skip

    @method("documents.reprocess", write=True)
    def documents_reprocess(
        self,
        item_ids: Optional[list[str]] = None,
        failed: bool = False,
        languages: Optional[str] = None,
    ) -> dict[str, Any]:
        """OCR documents again, as a job that can be undone: those named, or (`failed`) every one
        whose OCR failed, was partial or could not run."""
        if not item_ids and not failed:
            raise ServiceError(
                "invalid_params", "Name the documents to reprocess, or ask for the failed ones."
            )
        options = {"item_ids": list(item_ids or []), "failed": bool(failed)}
        if languages:
            options["languages"] = str(languages)
        return self._enqueue("documents-reprocess", "pdf", "reprocess", options)

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
        removed = owner_file.removed_matcher(
            owner_file.load(box)["removed"], str(settings.load(box).get("contacts.region") or "US")
        )
        if removed is not None:  # removed already, gone once the redraw job has run
            handles = [h for h in handles if not removed(h["service"], h["identifier"], None)]
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
        owner_file.save(self._require_box(), master)
        undo.note_people_change(self._require_box())  # undoing the newest import would undo this
        return {"person": summary, **self._redrawn("pages")}

    def _redraw(self, scope: str = "pages") -> Optional[dict[str, Any]]:
        """The job that redraws what a change to people needs drawn (`scope`: "index" for the
        people page alone, "pages" for the person pages too): one already waiting that covers it
        will draw this change too. In Caixa's window (`batch_pages`) the change waits instead, to be
        drawn with the others when the owner asks (`people.update`): no job."""
        if not self._people_aware():
            return None
        if self.batch_pages:
            waiting = self._require_box().add_pending(scope)
            self._announce("pages.pending", waiting)
            return None
        return self._refresh_job(scope)

    def _refresh_job(self, scope: str) -> dict[str, Any]:
        for job in self._jobs().list(limit=50):
            if job["kind"] == "refresh" and job["status"] == "queued":
                if (job.get("options") or {}).get("scope", "pages") == "pages" or scope == "index":
                    return dict(job)
        return self._enqueue("refresh", None, None, {"scope": scope} if scope != "pages" else {})

    def _redrawn(self, scope: str) -> dict[str, Any]:
        """A change's reply: the job drawing it (none while it waits), and what is waiting."""
        job = self._redraw(scope)
        return {"job": job, "pending": self._require_box().pending()}

    @method("pages.pending")
    def pages_pending(self) -> dict[str, Any]:
        """The changes to people not yet drawn on the pages: `{"changes", "scope"}`."""
        return self._require_box().pending()

    @method("people.update", write=True)
    def people_update(self) -> dict[str, Any]:
        """Draw the changes waiting to be drawn, in one pass: the job (the one already queued, if
        any), or none when nothing is waiting."""
        box = self._require_box()
        waiting = box.pending()
        if not waiting["changes"] or not self._people_aware():
            return {"job": None, "pending": waiting}
        return {"job": self._refresh_job(str(waiting["scope"] or "pages")), "pending": waiting}

    @method("people.delete", write=True)
    def people_delete(
        self,
        people: Optional[list[Union[int, str]]] = None,
        handles: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        """Take people out of the box for good: `people` by id or name, `handles` (each a
        `service` and an `identifier`) for numbers and addresses nobody is named for. Their
        one-to-one conversations and the files in them are deleted by the redraw job; what they
        wrote in a group stays. The owner's preference file remembers them, so a later import
        does not bring them back (see `caixa.owner`)."""
        box = self._require_box()
        gone: list[dict[str, Any]] = []
        for handle in handles or []:
            if not isinstance(handle, dict) or not str(handle.get("identifier") or "").strip():
                raise ServiceError("invalid_params", "A handle needs a service and an identifier.")
            gone.append(
                {"identifier": str(handle["identifier"]), "service": handle.get("service") or None}
            )
        with box.master() as master:
            known = {p.id: p for p in master.people()}
            ids: list[int] = []
            for who in people or []:
                found = who if isinstance(who, int) else master.person_id(str(who))
                if found is None or found not in known:
                    raise ServiceError("not_found", f"There is no person '{who}' in this box.")
                if known[found].is_owner:
                    raise ServiceError(
                        "invalid_params", "The owner of the box can't be removed from it."
                    )
                ids.append(found)
            if not ids and not gone:
                raise ServiceError("invalid_params", "Nobody was chosen to remove.")
            chosen = len(gone) + len(dict.fromkeys(ids))  # (who was chosen, not what is recorded)
            for found in dict.fromkeys(ids):
                gone.append({"person": known[found].name})
                # and their numbers and addresses: a name given since the pages were last drawn is
                # not in the archive yet (changes wait for Update), so the name alone could miss them
                gone.extend(
                    {"identifier": a.value, "service": a.service}
                    for a in master.aliases()
                    if a.person_id == found
                )
                master.delete_person(found)
            master.commit()
            added = owner_file.add_removed(box, gone)
            owner_file.save(box, master)
        undo.note_people_change(box)
        return {"removed": chosen, "remembered": added, **self._redrawn("pages")}

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
            master.mark_by_hand(who)
            return self._after_people_change(master, who)

    @method("people.categorize", write=True)
    def people_categorize(
        self,
        people: list[Union[int, str]],
        category: Optional[str],
        subcategory: Optional[int] = None,
    ) -> dict[str, Any]:
        """Sort people (by id or by name) into a category, or back to none (`category` null), and
        into one of its subcategories when given. The pages are redrawn by one refresh job, shared
        by changes made while it waits."""
        box = self._require_box()
        if category is not None and category not in CATEGORIES:
            raise ServiceError(
                "invalid_params",
                f"Unknown category '{category}'; use one of {', '.join(CATEGORIES)}.",
            )
        with box.master() as master:
            ids = []
            for who in people:
                found = who if isinstance(who, int) else master.person_id(str(who))
                if found is None or not any(p.id == found for p in master.people()):
                    raise ServiceError("not_found", f"There is no person '{who}' in this box.")
                ids.append(found)
            try:
                changed = master.set_category(ids, category, subcategory)
            except ValueError as error:
                raise ServiceError("invalid_params", str(error)) from None
            master.commit()
            owner_file.save(box, master)
        return {
            "changed": changed,
            "category": category,
            "subcategory": subcategory,
            **self._redrawn("index"),  # (who is in which category: the people page alone)
        }

    @method("people.join", write=True)
    def people_join(
        self,
        target: Union[int, str, None] = None,
        people: Optional[list[Union[int, str]]] = None,
        handles: Optional[list[dict[str, str]]] = None,
        name: Optional[str] = None,
        target_handles: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        """People dropped on someone on the people page join them, keeping that one's name.

        The one dropped on is `target` (a person, by id or name) or, for a tile with no name,
        its `target_handles` and the `name` it shows (they become that person, a new one or the
        one already called so). Those dropped are `people` (by id or name: merged in, as
        `people.merge` does) and `handles` (numbers and addresses nobody is named for: given to
        them). All of it or nothing."""
        box = self._require_box()

        def checked(given: Optional[list[dict[str, str]]]) -> list[tuple[str, str]]:
            found = []
            for handle in given or []:
                identifier = str((handle or {}).get("identifier") or "").strip()
                if not isinstance(handle, dict) or not identifier:
                    raise ServiceError(
                        "invalid_params", "A handle needs a service and an identifier."
                    )
                found.append((str(handle.get("service") or ""), identifier))
            return found

        incoming, theirs = checked(handles), checked(target_handles)
        if target is None and not (name and name.strip() and theirs):
            raise ServiceError(
                "invalid_params",
                "Say who they join: a person, or a tile's numbers or addresses and its name.",
            )
        if not (people or incoming):
            raise ServiceError("invalid_params", "Nobody was dropped to join them.")
        with box.master() as master:
            known = {p.id: p for p in master.people()}

            def existing(who: Union[int, str]) -> int:
                found = who if isinstance(who, int) else master.person_id(str(who))
                if found is None or found not in known:
                    raise ServiceError("not_found", f"There is no person '{who}' in this box.")
                return int(found)

            joining = [existing(who) for who in people or []]
            if any(known[who].is_owner for who in joining):
                raise ServiceError(
                    "conflict",
                    "The owner can't be merged into someone else; drop the other person on the "
                    "owner instead.",
                )
            try:
                if target is not None:
                    into = existing(target)
                else:
                    into = int(master.add_person(str(name).strip()))  # (or the one so named)
                for service, identifier in [*theirs, *incoming]:
                    kind, scope = alias_kind(service, identifier)
                    master.add_alias(into, identifier, kind, service=scope, move=True)
                for who in dict.fromkeys(joining):
                    if who != into:
                        master.merge_people(who, into)
            except (KeyError, ValueError) as error:
                master.connection.rollback()
                raise ServiceError("conflict", str(error)) from None
            master.mark_by_hand(into)
            done = self._after_people_change(master, into)
        return {**done, "joined": len(set(joining) - {into}) + len(incoming)}

    @method("people.subcategories")
    def people_subcategories(self) -> dict[str, Any]:
        """Every subcategory, each category's in order, with how many people are in it."""
        box = self._require_box()
        with box.master(read_only=self.read_only) as master:
            return {"subcategories": master.subcategories()}

    def _subcategory_change(self, change: Callable[[Any], Any]) -> dict[str, Any]:
        box = self._require_box()
        with box.master() as master:
            try:
                done = change(master)
            except ValueError as error:
                raise ServiceError("invalid_params", str(error)) from None
            master.commit()
            owner_file.save(box, master)
        return {**done, **self._redrawn("index")}

    @method("people.subcategory.add", write=True)
    def people_subcategory_add(
        self, category: str, name: str, parent: Optional[int] = None
    ) -> dict[str, Any]:
        """Add a subcategory under a category, or under one of its subcategories (two levels)."""
        return self._subcategory_change(
            lambda master: {"id": master.add_subcategory(category, parent, name)}
        )

    @method("people.subcategory.rename", write=True)
    def people_subcategory_rename(self, id: int, name: str) -> dict[str, Any]:
        def rename(master: Any) -> dict[str, Any]:
            master.rename_subcategory(int(id), name)
            return {"id": int(id)}

        return self._subcategory_change(rename)

    @method("people.subcategory.delete", write=True)
    def people_subcategory_delete(self, id: int) -> dict[str, Any]:
        """Delete a subcategory and its own; their people move up to its parent."""
        return self._subcategory_change(
            lambda master: {"deleted": master.delete_subcategory(int(id))}
        )

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
            master.mark_by_hand(who)
            return self._after_people_change(master, who)
