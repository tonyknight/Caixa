"""The service layer: everything the interface and the command line can do, in one place.

`Service` holds one open box. `caixa worker` exposes its methods over JSON-RPC and `caixa …` calls
them directly, so anything the browser does can be scripted. Methods take and return plain data
(dicts, lists, strings, numbers) and raise `ServiceError` with a short `kind` a program can act on
and a message a person can read.

Methods that change the box are marked `write`; a read-only service (heir viewing, groundwork for
a later project) refuses every one of them and never writes anywhere in the box.
"""

from __future__ import annotations

import functools
import inspect
import mimetypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, TypeVar, Union

from caixa import settings
from caixa.box import Box, BoxError
from caixa.collectors.options import OptionsError
from caixa.collectors.registry import Registry, discover

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


class Service:
    METHODS = _METHODS

    def __init__(
        self,
        box: Optional[PathLike] = None,
        read_only: bool = False,
        registry: Optional[Registry] = None,
        roots: Optional[Sequence[PathLike]] = None,
    ) -> None:
        self.read_only = read_only
        self.registry = registry or discover()
        self.roots = [Path(r).resolve() for r in (roots if roots is not None else [Path.home()])]
        self.box: Optional[Box] = None
        if box is not None:
            self.box_open(str(box))

    # --- Calling by name (what the worker and tests use) ------------------------------------

    def call(self, name: str, params: Optional[dict[str, Any]] = None) -> Any:
        """Run a method by its protocol name with keyword parameters."""
        known = self.METHODS.get(name)
        if known is None:
            raise ServiceError("unknown_method", f"There is no method '{name}'.")
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
        self.box = box
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
        self.box = box
        return self.box_status()

    @method("box.status")
    def box_status(self) -> dict[str, Any]:
        return self._require_box().status(read_only=self.read_only)

    @method("collectors.list")
    def collectors_list(self) -> list[dict[str, Any]]:
        return self.registry.describe()

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
