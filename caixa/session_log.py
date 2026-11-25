"""The session log: what each stage of a document job decided, and why, written as it runs.

One file per job in `.caixa/logs/sessions/`, named `<YYYY-MM-DD HH-MM-SS> <kind> (job <N>).log`,
with a `.jsonl` twin holding the same events, one JSON object per line. Both are owner-only and
written line by line, so `tail -f` follows a job, and a job that stops still leaves its log.

Stages write to `current()`, which is a quiet log when no session is open (tests, library use),
so they need no new parameters.

**Privacy (D26):** extracted values (type, title, author, date, tags), review reasons, page
numbers, sizes, times and errors are written. Quotes copied from a page and the model's raw
replies (`Quote`, `Reply`) are written only when the owner turns on `documents.log_quotes`.
Page text, passages and summaries are never written: a field named for them is refused.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import os
import sys
import threading
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, Optional, Sequence

from caixa.collectors.base import Cancelled

if TYPE_CHECKING:
    from caixa.box import Box

#: Fields that would carry page text, passages or summaries (D26: never in a log).
NEVER = frozenset({"text", "page_text", "passage", "passages", "summary"})
#: The settings that steer a document job's decisions, named in each session's header.
DECIDING = (
    "documents.enrich",
    "summaries.provider",
    "summaries.model",
    "summaries.endpoint",
    "documents.embedding_model",
    "workers",
    "documents.ocr",
    "documents.ocr_languages",
    "documents.log_quotes",
)


class Quote(str):
    """Words a model copied from a page: written only with the owner's opt-in."""


class Reply(str):
    """A model's raw reply: written only with the owner's opt-in."""


@dataclass(frozen=True)
class Document:
    number: int
    total: int
    name: str  # the file's original name

    def __str__(self) -> str:
        return f"[{self.number}/{self.total}] {self.name}"


class QuietLog:
    """The log stages write to when no session is open: it keeps nothing."""

    def event(
        self,
        stage: str,
        name: str,
        document: Optional[Document] = None,
        message: str = "",
        **fields: Any,
    ) -> None:
        pass

    def error(self, stage: str, error: BaseException, document: Optional[Document] = None) -> None:
        pass

    def outcome(
        self,
        document: Document,
        outcome: str,
        reasons: Sequence[str] = (),
        key: Optional[str] = None,
    ) -> None:
        pass

    @contextlib.contextmanager
    def stage(self, name: str) -> Iterator[None]:
        yield

    def close(self, status: str) -> None:
        pass


QUIET = QuietLog()
_current: contextvars.ContextVar[QuietLog] = contextvars.ContextVar("session_log", default=QUIET)


def current() -> QuietLog:
    """The open session's log, or the quiet one."""
    return _current.get()


class SessionLog(QuietLog):
    def __init__(self, box: Box, job: int, kind: str) -> None:
        from caixa import settings

        folder = box.logs_dir / "sessions"
        folder.mkdir(parents=True, exist_ok=True)
        folder.chmod(0o700)
        self.started = datetime.now()
        self.path = folder / f"{self.started:%Y-%m-%d %H-%M-%S} {kind} (job {job}).log"
        self.events_path = self.path.with_suffix(".jsonl")
        self._lock = threading.Lock()
        self._clock = time.monotonic()
        self._text = _owner_only(self.path)
        self._events = _owner_only(self.events_path)
        saved = settings.load(box)
        self.quotes = bool(saved.get("documents.log_quotes"))
        self._outcomes: dict[str, tuple[str, tuple[str, ...]]] = {}
        self._stages: dict[str, float] = {}  # seconds spent in each stage
        self._errors: list[dict[str, Any]] = []
        self._header(job, kind, saved)

    def event(
        self,
        stage: str,
        name: str,
        document: Optional[Document] = None,
        message: str = "",
        **fields: Any,
    ) -> None:
        refused = sorted(NEVER.intersection(fields))
        if refused:
            raise ValueError(f"{', '.join(refused)}: page text never goes into a log")
        kept = fields if self.quotes else _without_private(fields)
        head = " ".join(part for part in (str(document or ""), message) if part)
        parts = [head] if head else []
        parts += [f"{_words(key)}: {_show(value)}" for key, value in kept.items()]
        body = " · ".join(parts)
        record: dict[str, Any] = {"stage": stage, "event": name}
        if document is not None:
            record["document"] = {
                "number": document.number,
                "total": document.total,
                "name": document.name,
            }
        if message:
            record["message"] = message
        self._write(f"{datetime.now():%H:%M:%S} {name:<10} {body}".rstrip(), record | kept)

    def error(self, stage: str, error: BaseException, document: Optional[Document] = None) -> None:
        trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        found = {
            "stage": stage,
            "document": str(document) if document else None,
            "type": type(error).__name__,
            "message": str(error),
        }
        self._errors.append(found)
        head = " ".join(part for part in (str(document or ""), f"in {stage}:") if part)
        lines = [f"{datetime.now():%H:%M:%S} {'error':<10} {head} {found['type']}: {error}"]
        lines += [f"    {line}" for line in trace.rstrip().splitlines()]
        self._write("\n".join(lines), {"event": "error", **found, "traceback": trace})

    def outcome(
        self,
        document: Document,
        outcome: str,
        reasons: Sequence[str] = (),
        key: Optional[str] = None,
    ) -> None:
        """Where a document ended up, and why; a later stage's outcome for the same `key` (its
        item id, when it has one) replaces an earlier one."""
        self._outcomes[key or str(document)] = (outcome, tuple(reasons))

    @contextlib.contextmanager
    def stage(self, name: str) -> Iterator[None]:
        began = time.monotonic()
        try:
            yield
        finally:
            self._stages[name] = self._stages.get(name, 0.0) + time.monotonic() - began

    def close(self, status: str) -> None:
        if self._text.closed:
            return
        outcomes = Counter(outcome for outcome, _ in self._outcomes.values())
        reasons: dict[str, Counter[str]] = {}
        for outcome, given in self._outcomes.values():
            reasons.setdefault(outcome, Counter()).update(given)
        took = time.monotonic() - self._clock

        def tally(outcome: str, count: int) -> str:
            named = ", ".join(f"{r} {n}" for r, n in reasons[outcome].most_common())
            return f"{outcome} {count}" + (f" ({named})" if named else "")

        lines = [
            "",
            f"--- summary: {status}, after {_duration(took)} ---",
            "outcomes: " + (" · ".join(tally(o, n) for o, n in outcomes.most_common()) or "none"),
            "stages: "
            + (" · ".join(f"{s} {_duration(t)}" for s, t in self._stages.items()) or "none"),
            f"errors: {len(self._errors) or 'none'}",
        ]
        lines += [
            f"  {e['document'] + ' ' if e['document'] else ''}in {e['stage']}: "
            f"{e['type']}: {e['message']}"
            for e in self._errors
        ]
        self._write(
            "\n".join(lines),
            {
                "event": "summary",
                "status": status,
                "seconds": round(took, 1),
                "outcomes": dict(outcomes),
                "reasons": {o: dict(r) for o, r in reasons.items() if r},
                "stages": {s: round(t, 1) for s, t in self._stages.items()},
                "errors": self._errors,
            },
        )
        with self._lock:
            self._text.close()
            self._events.close()

    def _header(self, job: int, kind: str, saved: dict[str, Any]) -> None:
        import caixa
        from caixa import requirements
        from caixa.documents.pdf import ocr

        packages = {
            module: requirements.version(module)
            for module in (*requirements.REQUIRED, *requirements.OPTIONAL)
        }
        tools = ocr.tools()
        deciding = {key: saved.get(key) for key in DECIDING}
        lines = [
            f"Caixa {caixa.__version__} · {kind} (job {job}) · started {self.started:%Y-%m-%d %H:%M:%S}",
            f"python: {sys.executable} ({sys.version.split()[0]})",
            "packages: "
            + ", ".join(f"{m} {v}" if v else f"{m}: not installed" for m, v in packages.items()),
            f"tesseract: {tools.versions.get('tesseract') or 'not installed'}"
            + (f" (languages: {', '.join(tools.languages)})" if tools.languages else ""),
            "settings: " + " · ".join(f"{_words(k)}: {_show(v)}" for k, v in deciding.items()),
            "",
        ]
        self._write(
            "\n".join(lines),
            {
                "event": "session",
                "job": job,
                "kind": kind,
                "caixa": caixa.__version__,
                "python": sys.executable,
                "started": self.started.astimezone().isoformat(timespec="seconds"),
                "packages": packages,
                "tools": {**tools.versions, "tesseract_languages": list(tools.languages)},
                "settings": deciding,
            },
        )

    def _write(self, text: str, record: dict[str, Any]) -> None:
        record = {"time": datetime.now().astimezone().isoformat(timespec="seconds"), **record}
        with self._lock:
            self._text.write(text + "\n")
            self._events.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


@contextlib.contextmanager
def opened(box: Box, job: int, kind: str) -> Iterator[QuietLog]:
    """A session for one job: current while it runs, closed with how the job ended (an error with
    its traceback first). A log that cannot be written costs only the log."""
    log: QuietLog
    try:
        log = SessionLog(box, job, kind)
    except Exception:
        traceback.print_exc()
        log = QUIET
    token = _current.set(log)
    status = "failed"
    try:
        yield log
        status = "done"
    except Cancelled:
        status = "cancelled"
        raise
    except BaseException as error:
        log.error("job", error)
        raise
    finally:
        _current.reset(token)
        try:
            log.close(status)
        except Exception:
            traceback.print_exc()


def _owner_only(path: Path) -> Any:
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.chmod(path, 0o600)
    return os.fdopen(handle, "a", encoding="utf-8", buffering=1)


def _without_private(value: Any) -> Any:
    """`value` without its quotes and raw replies, at any depth."""
    if isinstance(value, dict):
        return {
            key: _without_private(item)
            for key, item in value.items()
            if not isinstance(item, (Quote, Reply))
        }
    if isinstance(value, (list, tuple)):
        return [_without_private(item) for item in value if not isinstance(item, (Quote, Reply))]
    return value


def _words(key: str) -> str:
    return key.removeprefix("documents.").replace("_", " ")


def _show(value: Any) -> str:
    if value is None or value == "":
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (Quote, Reply)):
        return json.dumps(str(value), ensure_ascii=False)  # quoted, on one line
    if isinstance(value, float):
        return f"{value:.1f}"
    if isinstance(value, (list, tuple, set)):
        items = [_show(item) for item in value]
        between = "; " if any(", " in item for item in items) else ", "
        return between.join(items) or "none"
    if isinstance(value, dict):
        return ", ".join(f"{k} {_show(v)}" for k, v in value.items()) or "none"
    return str(value)


def _duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes} min {rest} s"


__all__ = ["Document", "QuietLog", "Quote", "Reply", "SessionLog", "current", "opened"]
