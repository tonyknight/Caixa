"""The mail index: an mbox read once, mail by mail, without importing anything.

`<box>/.caixa/mail/index.sqlite` is Caixa's own working file (readable only by the box's owner, and
rebuildable from the mbox at any time):

- `sources`: each mbox read: its path (and the member, for an mbox inside a zip), its kind
  (`original`, `cleaned`, `reduced`), the source it was written from, the account the owner named,
  and what identifies the file (size, modification time, a hash of its first megabyte);
- `mails`: every mail of a source: where its bytes are (offset and length) and their SHA-256, the
  facts in its headers (Message-ID, thread, date, sender, recipients, subject, Gmail labels), how
  many files it carries, and the list and bulk-mail headers cleaning looks at. Bodies are never
  kept;
- `senders`: each sender of a source, summed: the names they used, their number of mails, the space
  those take, their first and last date.

**A mail is the bytes from its `From ` line to the next one** (the rule Python's `mailbox` and mail
programs follow: a body line that begins `From ` is written `>From `). So a source's mails, end to
end, are exactly its file, and a new mbox can be made by copying chosen byte ranges.

**Reading with workers.** A plain mbox is cut into ranges at mail boundaries and the ranges are read
and parsed by worker processes, their results put back in file order. A compressed member of a zip
cannot be cut, so the main process reads it as one stream and sends batches of mails to the workers;
offsets are offsets in the unzipped member, so they also hold for an unzipped copy. One worker means
no pool at all. The result is the same whatever the number of workers.
"""

from __future__ import annotations

import collections
import concurrent.futures
import hashlib
import json
import multiprocessing
import os
import re
import sqlite3
import time
import zipfile
from dataclasses import dataclass
from datetime import timezone
from email.message import EmailMessage
from email.parser import BytesHeaderParser
from email.policy import default as default_policy
from email.utils import getaddresses
from pathlib import Path
from typing import IO, Any, Callable, Iterable, Iterator, Optional, Sequence, Union

from chattr.parsers.mbox_parser import MboxParser, normalize_message_id

from caixa.box import Box
from caixa.collectors.base import Progress

PathLike = Union[str, Path]
SCHEMA_VERSION = "1"
MB = 1 << 20
#: Ranges of a plain mbox handed to one worker at a time.
MIN_RANGE, MAX_RANGE = 8 * MB, 64 * MB
#: Mails of a zip member sent to a worker at once (about this many bytes).
BATCH = 16 * MB
BLOCK = 4 * MB
#: The headers cleaning looks at (lower case), kept as given (cut to this many characters).
SIGNAL_HEADERS = (
    "list-id",
    "list-unsubscribe",
    "list-post",
    "precedence",
    "auto-submitted",
    "feedback-id",
    "x-auto-response-suppress",
    "x-campaign",
    "x-campaignid",
    "x-mc-user",
    "x-sg-eid",
    "x-mailgun-sid",
    "x-ses-outgoing",
)
SIGNAL_LENGTH = 300
KIND_NAME = re.compile(r"^\(\d{4}-\d{2}-\d{2}\) .+ \[(Cleaned|Reduced)\]\.mbox$")
ACCOUNT_FORBIDDEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
_ATTACHMENT_PART = re.compile(rb"(?im)^content-disposition:[ \t]*(?:attachment|inline)\b")

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    member TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'original' CHECK (kind IN ('original', 'cleaned', 'reduced')),
    parent_id INTEGER REFERENCES sources (id),
    account TEXT,
    size INTEGER,
    mtime_ns INTEGER,
    head_hash TEXT,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'read')),
    read_at TEXT,
    mails INTEGER NOT NULL DEFAULT 0,
    UNIQUE (path, member)
);
CREATE TABLE mails (
    source_id INTEGER NOT NULL REFERENCES sources (id),
    position INTEGER NOT NULL,
    offset INTEGER NOT NULL,
    length INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    message_id TEXT,
    in_reply_to TEXT,
    references_root TEXT,
    thread_id TEXT,
    thread_key TEXT,
    date_utc TEXT,
    tz_offset_minutes INTEGER,
    date_assumed INTEGER NOT NULL DEFAULT 0,
    sender_address TEXT,
    sender_name TEXT,
    recipients TEXT NOT NULL DEFAULT '[]',
    subject TEXT NOT NULL DEFAULT '',
    labels TEXT NOT NULL DEFAULT '[]',
    attachments INTEGER NOT NULL DEFAULT 0,
    signals TEXT NOT NULL DEFAULT '{}',
    flags TEXT,
    protections TEXT,
    by_owner INTEGER,
    PRIMARY KEY (source_id, position)
);
CREATE INDEX mails_by_message_id ON mails (source_id, message_id);
CREATE INDEX mails_by_sender ON mails (source_id, sender_address);
CREATE INDEX mails_by_thread ON mails (source_id, thread_key);
CREATE TABLE senders (
    source_id INTEGER NOT NULL REFERENCES sources (id),
    address TEXT NOT NULL,
    names TEXT NOT NULL DEFAULT '[]',
    mails INTEGER NOT NULL DEFAULT 0,
    size INTEGER NOT NULL DEFAULT 0,
    first_utc TEXT,
    last_utc TEXT,
    owner_wrote INTEGER NOT NULL DEFAULT 0,
    person TEXT,
    matched_by TEXT,
    grp TEXT,
    PRIMARY KEY (source_id, address)
);
"""

#: The columns a worker fills, in the order it returns them.
PARSED = (
    "offset",
    "length",
    "sha256",
    "message_id",
    "in_reply_to",
    "references_root",
    "thread_id",
    "date_utc",
    "tz_offset_minutes",
    "date_assumed",
    "sender_address",
    "sender_name",
    "recipients",
    "subject",
    "labels",
    "attachments",
    "signals",
)
Row = tuple[Any, ...]


class MailError(ValueError):
    """An mbox that cannot be read as asked (not found, not an mbox, no account …)."""


@dataclass(frozen=True)
class ReadResult:
    source_id: int
    path: str
    member: str
    account: str
    kind: str
    mails: int
    reused: bool
    seconds: float


def check_account(name: Optional[str]) -> str:
    """The account name, trimmed; it names a folder in the box, so it must be usable as one."""
    text = (name or "").strip()
    if not text:
        raise MailError("An account name is needed (for example Gmail or Work).")
    if (
        len(text) > 64
        or text in (".", "..")
        or text.startswith(".")
        or ACCOUNT_FORBIDDEN.search(text)
    ):
        raise MailError(
            f"'{text}' cannot be an account name: use up to 64 characters, no / \\ : * ? \" < > |, "
            "and do not begin with a dot."
        )
    return text


def kind_of(name: str) -> str:
    """`original`, or `cleaned`/`reduced` for a file named as Caixa names those."""
    match = KIND_NAME.match(name)
    return match.group(1).lower() if match else "original"


# --- Parsing (runs in the workers) -------------------------------------------------------------


def entries(chunks: Iterable[bytes], start: int) -> Iterator[tuple[int, bytes]]:
    """The mails in a stream of bytes that begins at a mail: (offset, bytes) for each."""
    buffer = bytearray()
    offset = start
    search = 1
    for chunk in chunks:
        buffer += chunk
        while True:
            found = buffer.find(b"\nFrom ", search)
            if found < 0:
                search = max(1, len(buffer) - 5)
                break
            yield offset, bytes(buffer[: found + 1])
            del buffer[: found + 1]
            offset += found + 1
            search = 1
    if buffer:
        yield offset, bytes(buffer)


def _text(message: EmailMessage, name: str) -> str:
    try:
        value = message.get(name)
        return str(value) if value is not None else ""
    except (LookupError, UnicodeError, ValueError, IndexError, TypeError):
        raw = message.get_all(name, failobj=[""])
        return str(raw[0]) if raw else ""


def _addresses(message: EmailMessage, name: str) -> list[tuple[str, str]]:
    try:
        values = [str(v) for v in message.get_all(name, [])]
    except (LookupError, UnicodeError, ValueError, IndexError, TypeError):
        return []
    return [(n.strip(), a.strip().lower()) for n, a in getaddresses(values) if a.strip()]


def parse(offset: int, data: bytes) -> Row:
    """One mail's facts, from its bytes (headers only, plus a count of its file parts)."""
    first_line, _, rest = data.partition(b"\n")
    head_end = rest.find(b"\n\n")
    head = rest if head_end < 0 else rest[: head_end + 1]
    message = BytesHeaderParser(policy=default_policy).parsebytes(head)
    assert isinstance(message, EmailMessage)
    from_line = first_line[5:].decode("latin-1").strip() if first_line.startswith(b"From ") else ""
    moment, assumed = MboxParser._time(message, from_line)
    sender = (_addresses(message, "From") or [("", "")])[0]
    references = [m for m in re.findall(r"<([^<>]+)>", _text(message, "References"))]
    root = normalize_message_id(f"<{references[0]}>") if references else None
    in_reply = re.findall(r"<([^<>]+)>", _text(message, "In-Reply-To"))
    offset_delta = moment.utcoffset()
    recipients = [
        [field.lower(), name, address]
        for field in ("To", "Cc")
        for name, address in _addresses(message, field)
    ]
    labels = [l.strip() for l in _text(message, "X-Gmail-Labels").split(",") if l.strip()]
    signals = {
        name: _text(message, name)[:SIGNAL_LENGTH] for name in SIGNAL_HEADERS if name in message
    }
    return (
        offset,
        len(data),
        hashlib.sha256(data).hexdigest(),
        normalize_message_id(_text(message, "Message-ID")),
        normalize_message_id(f"<{in_reply[0]}>") if in_reply else None,
        root,
        _text(message, "X-GM-THRID").strip() or None,
        moment.astimezone(timezone.utc).isoformat(timespec="seconds"),
        int(offset_delta.total_seconds() // 60) if offset_delta is not None else None,
        int(assumed),
        sender[1] or None,
        sender[0] or None,
        json.dumps(recipients, ensure_ascii=False),
        _text(message, "Subject"),
        json.dumps(labels, ensure_ascii=False),
        len(_ATTACHMENT_PART.findall(data)),
        json.dumps(signals, ensure_ascii=False),
    )


def _blocks(handle: IO[bytes], length: Optional[int] = None) -> Iterator[bytes]:
    left = length
    while left is None or left > 0:
        chunk = handle.read(BLOCK if left is None else min(BLOCK, left))
        if not chunk:
            return
        if left is not None:
            left -= len(chunk)
        yield chunk


def parse_range(path: str, start: int, end: int) -> list[Row]:
    """Every mail that begins in `[start, end)` of a plain mbox (`start` is a mail boundary)."""
    with open(path, "rb") as handle:
        handle.seek(start)
        return [parse(o, d) for o, d in entries(_blocks(handle, end - start), start)]


def parse_batch(batch: Sequence[tuple[int, bytes]]) -> list[Row]:
    return [parse(offset, data) for offset, data in batch]


# --- The index ---------------------------------------------------------------------------------


Report = Optional[Callable[[Progress], None]]


class MailIndex:
    def __init__(self, path: PathLike, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        if read_only:  # look, never change (and never create): a missing index reads as empty
            if self.path.is_file():
                uri = f"{self.path.resolve().as_uri()}?mode=ro"
                self.connection = sqlite3.connect(uri, uri=True, check_same_thread=False)
            else:
                self.connection = sqlite3.connect(":memory:", check_same_thread=False)
                self.connection.executescript(SCHEMA)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self.connection = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        os.chmod(self.path, 0o600)
        self._schema()

    @classmethod
    def for_box(cls, box: Box, read_only: bool = False) -> "MailIndex":
        return cls(box.caixa_dir / "mail" / "index.sqlite", read_only=read_only)

    def __enter__(self) -> "MailIndex":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def known_account(self, source: PathLike) -> Optional[str]:
        """The account the index already has for every mbox `source` stands for, if one."""
        path = Path(source).expanduser()
        if not path.exists():
            return None
        accounts = {
            row[1] if row else None
            for file, member in _mboxes(path.resolve())
            for row in [self._known(str(file), member)]
        }
        if len(accounts) == 1:
            (account,) = accounts
            return str(account) if account else None
        return None

    def close(self) -> None:
        self.connection.close()

    def _schema(self) -> None:
        db = self.connection
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "meta" in tables:
            row = db.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()
            if row and row[0] == SCHEMA_VERSION:
                return
        for table in tables - {"sqlite_sequence"}:
            db.execute(f'DROP TABLE "{table}"')
        db.executescript(
            SCHEMA + f"INSERT INTO meta (key, value) VALUES ('schema', '{SCHEMA_VERSION}');"
        )

    # --- Sources --------------------------------------------------------------------------------

    def sources(self) -> list[dict[str, Any]]:
        db = self.connection
        db.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in db.execute("SELECT * FROM sources ORDER BY id")]
        finally:
            db.row_factory = None

    def _known(self, path: str, member: str) -> Optional[tuple[Any, ...]]:
        cursor = self.connection.cursor()
        cursor.row_factory = None  # plain tuples, whatever the connection's factory
        row: Optional[tuple[Any, ...]] = cursor.execute(
            "SELECT id, account, status, size, mtime_ns, head_hash, kind FROM sources "
            "WHERE path = ? AND member = ?",
            (path, member),
        ).fetchone()
        return row

    # --- Reading --------------------------------------------------------------------------------

    def read(
        self,
        source: PathLike,
        account: Optional[str],
        workers: int = 1,
        progress: Report = None,
        range_size: Optional[int] = None,
    ) -> list[ReadResult]:
        """Read an `.mbox` into the index. Returns what was read, one result per mbox."""
        path = Path(source).expanduser()
        if not path.exists():
            raise MailError(f"Not found: {path}")
        given = check_account(account) if account is not None else None
        workers = max(1, workers)
        found = _mboxes(path.resolve())
        if not found:
            raise MailError(f"{path.name}: there is no .mbox in it.")
        results = []
        for file, member in found:
            if member:
                results.append(
                    self._read_member(file, member, given, workers, progress, range_size)
                )
            else:
                results.append(self._read_file(file, given, workers, progress, range_size))
        return results

    def _account(self, known: Optional[tuple[Any, ...]], given: Optional[str]) -> str:
        if given is not None:
            return given
        if known is not None and known[1]:
            return str(known[1])
        raise MailError("An account name is needed (for example Gmail or Work).")

    def _read_file(
        self,
        path: Path,
        given: Optional[str],
        workers: int,
        progress: Report,
        range_size: Optional[int],
    ) -> ReadResult:
        started = time.monotonic()
        with path.open("rb") as handle:
            head = handle.read(MB)
        if not head.startswith(b"From "):
            raise MailError(f"{path.name} is not an mbox: it does not begin with a 'From ' line.")
        stat = path.stat()
        head_hash = hashlib.sha256(head).hexdigest()
        known = self._known(str(path), "")
        account = self._account(known, given)
        identity = (stat.st_size, stat.st_mtime_ns, head_hash)
        if known and known[2] == "read" and tuple(known[3:6]) == identity:
            return self._reused(known, given, str(path), "", account)
        size = stat.st_size
        chosen = range_size or min(MAX_RANGE, max(MIN_RANGE, size // (workers * 4)))
        ranges = _ranges(path, size, chosen)
        rows = self._parsed_ranges(str(path), ranges, workers, size, path.name, progress)
        kind = known[6] if known else kind_of(path.name)
        source_id, count = self._store(str(path), "", kind, account, identity, rows)
        return ReadResult(
            source_id, str(path), "", account, kind, count, False, time.monotonic() - started
        )

    def _read_member(
        self,
        path: Path,
        member: str,
        given: Optional[str],
        workers: int,
        progress: Report,
        batch_size: Optional[int],
    ) -> ReadResult:
        """An mbox inside a zip, read as one stream; offsets are offsets in the unzipped member."""
        started = time.monotonic()
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo(member)
            with archive.open(info) as handle:
                if not handle.read(5).startswith(b"From "):
                    raise MailError(
                        f"{member} in {path.name} is not an mbox: it does not begin with a "
                        "'From ' line."
                    )
            identity = (info.file_size, path.stat().st_mtime_ns, f"crc:{info.CRC:08x}")
            known = self._known(str(path), member)
            account = self._account(known, given)
            kind = known[6] if known else kind_of(Path(member).name)
            if known and known[2] == "read" and tuple(known[3:6]) == identity:
                return self._reused(known, given, str(path), member, account)
            with archive.open(info) as handle:
                rows = _parsed_stream(
                    handle,
                    workers,
                    batch_size or BATCH,
                    info.file_size,
                    Path(member).name,
                    progress,
                )
                source_id, count = self._store(str(path), member, kind, account, identity, rows)
        return ReadResult(
            source_id, str(path), member, account, kind, count, False, time.monotonic() - started
        )

    def _reused(
        self, known: tuple[Any, ...], given: Optional[str], path: str, member: str, account: str
    ) -> ReadResult:
        if given is not None and given != known[1]:
            self.connection.execute(
                "UPDATE sources SET account = ? WHERE id = ?", (given, known[0])
            )
        mails = self.connection.execute(
            "SELECT mails FROM sources WHERE id = ?", (known[0],)
        ).fetchone()[0]
        return ReadResult(known[0], path, member, account, known[6], mails, True, 0.0)

    def _parsed_ranges(
        self,
        path: str,
        ranges: list[tuple[int, int]],
        workers: int,
        size: int,
        name: str,
        progress: Report,
    ) -> Iterator[list[Row]]:
        """Each range's rows, in file order, reporting progress as each one is done."""

        def report(done: int, count: int) -> None:
            if progress is not None:
                progress(Progress("reading", done, size, f"{name}: {count:,} mails"))

        report(0, 0)
        if workers == 1 or len(ranges) == 1:
            count = 0
            for start, end in ranges:
                parsed = parse_range(path, start, end)
                count += len(parsed)
                yield parsed
                report(end, count)
            return
        pool = concurrent.futures.ProcessPoolExecutor(
            max_workers=min(workers, len(ranges)), mp_context=multiprocessing.get_context("spawn")
        )
        try:
            futures = [pool.submit(parse_range, path, start, end) for start, end in ranges]
            count = 0
            for future, (_, end) in zip(futures, ranges):
                parsed = future.result()
                count += len(parsed)
                yield parsed
                report(end, count)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _store(
        self,
        path: str,
        member: str,
        kind: str,
        account: str,
        identity: tuple[int, int, str],
        parts: Iterable[list[Row]],
    ) -> tuple[int, int]:
        """Write a source's mails in one transaction (a cancelled read leaves nothing behind)."""
        db = self.connection
        db.execute("BEGIN")
        try:
            known = self._known(path, member)
            if known:
                source_id = int(known[0])
                db.execute("DELETE FROM mails WHERE source_id = ?", (source_id,))
                db.execute("DELETE FROM senders WHERE source_id = ?", (source_id,))
            else:
                source_id = int(
                    db.execute(
                        "INSERT INTO sources (path, member, kind) VALUES (?, ?, ?)",
                        (path, member, kind),
                    ).lastrowid
                    or 0
                )
            position = 0
            placeholders = ", ".join("?" for _ in range(len(PARSED) + 2))
            insert = (
                f"INSERT INTO mails (source_id, position, {', '.join(PARSED)}) "
                f"VALUES ({placeholders})"
            )
            for rows in parts:
                db.executemany(
                    insert, [(source_id, position + i, *row) for i, row in enumerate(rows)]
                )
                position += len(rows)
            _thread_keys(db, source_id)
            db.execute(
                "INSERT INTO senders (source_id, address, names, mails, size, first_utc, last_utc) "
                "SELECT source_id, sender_address, "
                "json_group_array(DISTINCT sender_name) FILTER (WHERE sender_name IS NOT NULL), "
                "COUNT(*), SUM(length), MIN(date_utc), MAX(date_utc) FROM mails "
                "WHERE source_id = ? AND sender_address IS NOT NULL GROUP BY sender_address",
                (source_id,),
            )
            db.execute(
                "UPDATE sources SET account = ?, size = ?, mtime_ns = ?, head_hash = ?, "
                "status = 'read', read_at = datetime('now'), mails = ? WHERE id = ?",
                (account, *identity, position, source_id),
            )
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        return source_id, position


def _mboxes(path: Path) -> list[tuple[Path, str]]:
    """(file, member) for every mbox `path` stands for: itself, the `.mbox` members of a zip, or
    every `.mbox` and zip holding one inside a folder, including Apple Mail's `<name>.mbox/mbox`
    (member is '' for a plain file)."""
    if path.is_dir():
        found: list[tuple[Path, str]] = []
        for file in sorted(p for p in path.rglob("*") if p.is_file()):
            apple = file.name == "mbox" and file.parent.suffix.lower() == ".mbox"  # Apple Mail
            if file.suffix.lower() in (".mbox", ".zip") or apple:
                found += _mboxes(file)
        return found
    if path.suffix.lower() == ".zip" and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return [
                (path, i.filename)
                for i in archive.infolist()
                if not i.is_dir() and i.filename.lower().endswith(".mbox")
            ]
    return [(path, "")]


def _parsed_stream(
    handle: IO[bytes],
    workers: int,
    batch_size: int,
    size: int,
    name: str,
    progress: Report,
) -> Iterator[list[Row]]:
    """The rows of a stream of mails, in order: batches parsed by the workers, at most two per
    worker waiting, so memory stays bounded however large the stream."""

    def report(done: int, count: int) -> None:
        if progress is not None:
            progress(Progress("reading", done, size, f"{name}: {count:,} mails"))

    def batches() -> Iterator[list[tuple[int, bytes]]]:
        batch: list[tuple[int, bytes]] = []
        held = 0
        for offset, data in entries(_blocks(handle), 0):
            batch.append((offset, data))
            held += len(data)
            if held >= batch_size:
                yield batch
                batch, held = [], 0
        if batch:
            yield batch

    def end_of(batch: list[tuple[int, bytes]]) -> int:
        return batch[-1][0] + len(batch[-1][1])

    report(0, 0)
    count = 0
    if workers == 1:
        for batch in batches():
            parsed = parse_batch(batch)
            count += len(parsed)
            yield parsed
            report(end_of(batch), count)
        return
    pool = concurrent.futures.ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    )
    waiting: collections.deque[tuple[concurrent.futures.Future[list[Row]], int]]
    waiting = collections.deque()
    try:
        for batch in batches():
            waiting.append((pool.submit(parse_batch, batch), end_of(batch)))
            while len(waiting) >= workers * 2:
                future, end = waiting.popleft()
                parsed = future.result()
                count += len(parsed)
                yield parsed
                report(end, count)
        while waiting:
            future, end = waiting.popleft()
            parsed = future.result()
            count += len(parsed)
            yield parsed
            report(end, count)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _ranges(path: Path, size: int, range_size: int) -> list[tuple[int, int]]:
    """The file cut into ranges of about `range_size`, each beginning at a mail."""
    starts = [0]
    with path.open("rb") as handle:
        point = range_size
        while point < size:
            handle.seek(point - 1)
            found = -1
            seen = point - 1
            carry = b""
            while found < 0:
                chunk = handle.read(BLOCK)
                if not chunk:
                    break
                window = carry + chunk
                hit = window.find(b"\nFrom ")
                if hit >= 0:
                    found = seen - len(carry) + hit + 1
                    break
                carry = window[-5:]
                seen += len(chunk)
            if found < 0 or found >= size:
                break
            if found > starts[-1]:
                starts.append(found)
            point = max(found + 1, point + range_size)
    return list(zip(starts, starts[1:] + [size]))


def _thread_keys(db: sqlite3.Connection, source_id: int) -> None:
    """Gmail's thread id; else the root of the References; else the thread of the mail it
    answers (followed through mails of this source), else its own Message-ID."""
    db.execute(
        "UPDATE mails SET thread_key = CASE "
        "WHEN thread_id IS NOT NULL THEN 'gmail:' || thread_id "
        "WHEN references_root IS NOT NULL THEN 'msgid:' || references_root "
        "WHEN in_reply_to IS NOT NULL THEN 'msgid:' || in_reply_to "
        "WHEN message_id IS NOT NULL THEN 'msgid:' || message_id "
        "ELSE 'mail:' || source_id || ':' || position END WHERE source_id = ?",
        (source_id,),
    )
    for _ in range(20):
        changed = db.execute(
            "UPDATE mails SET thread_key = (SELECT p.thread_key FROM mails p "
            "WHERE p.source_id = mails.source_id AND p.message_id = mails.in_reply_to LIMIT 1) "
            "WHERE source_id = ? AND thread_id IS NULL AND references_root IS NULL "
            "AND in_reply_to IS NOT NULL AND EXISTS (SELECT 1 FROM mails p "
            "WHERE p.source_id = mails.source_id AND p.message_id = mails.in_reply_to "
            "AND p.thread_key != mails.thread_key)",
            (source_id,),
        ).rowcount
        if not changed:
            return
