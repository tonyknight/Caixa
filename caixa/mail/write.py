"""Writing a Cleaned or Reduced mbox: the chosen mails copied byte for byte, checked, then named.

The original export is never changed: a new mbox is written in the source's own folder, named
`(YYYY-MM-DD) <name> [Cleaned].mbox` or `… [Reduced].mbox`. Its mails are copied from the source in
their original order, byte for byte (so each one is exactly what the export held), into a `.part`
file that is renamed to its final name only after every mail in it has been checked against the
index. A failed check, a cancel or an error leave nothing behind.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import multiprocessing
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import IO, Callable, Iterable, Optional, Sequence

from caixa.collectors.base import Progress
from caixa.mail.index import BLOCK, MailError, MailIndex

TAGS = ("Cleaned", "Reduced")
_DATE = re.compile(r"^\(\d{4}-\d{2}-\d{2}\) ")
_TAG = re.compile(r" \[(?:Cleaned|Reduced)\](?: \(\d+\))?$")
MB = 1 << 20


def _apple(path: PurePosixPath) -> bool:
    """Apple Mail exports a mailbox as a folder `<name>.mbox` holding a file named `mbox`."""
    return path.name == "mbox" and path.parent.suffix.lower() == ".mbox"


def output_name(source: str, tag: str, today: date) -> str:
    """`(today) <base> [<tag>].mbox`: the base is the source's name without `.mbox` and without the
    date and tag of an earlier Cleaned or Reduced copy."""
    if tag not in TAGS:
        raise ValueError(f"tag must be one of {TAGS}")
    path = PurePosixPath(source.replace("\\", "/"))
    name = path.parent.name if _apple(path) else path.name
    base = name[:-5] if name.lower().endswith(".mbox") else name
    base = _TAG.sub("", _DATE.sub("", base)).strip() or "mail"
    return f"({today.isoformat()}) {base} [{tag}].mbox"


def output_path(file: Path, member: str, tag: str, today: date) -> Path:
    """Where the new mbox goes: the source's folder (a zip's folder; the folder holding an Apple
    Mail `<name>.mbox`), under a name no file has yet."""
    if member:
        folder, named = file.parent, member
    elif _apple(PurePosixPath(file.as_posix())):
        folder, named = file.parent.parent, file.as_posix()
    else:
        folder, named = file.parent, file.name
    stem = output_name(named, tag, today)[: -len(".mbox")]
    chosen, number = folder / f"{stem}.mbox", 2
    while chosen.exists() or chosen.with_name(chosen.name + ".part").exists():
        chosen, number = folder / f"{stem} ({number}).mbox", number + 1
    return chosen


def human_size(count: int) -> str:
    """1536 → '1.5 KB'."""
    value = float(count)
    for unit in ("bytes", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:,.0f} {unit}" if unit == "bytes" else f"{value:,.1f} {unit}"
        value /= 1024
    return f"{value:,.1f} TB"


def preflight(folder: Path, needed: int, margin: Optional[int] = None) -> None:
    """Refuse, before any work, a folder that cannot be written or has too little room."""
    if not os.access(folder, os.W_OK):
        raise MailError(
            f"{folder} cannot be written, so the new mbox cannot be put beside its source."
        )
    spare = margin if margin is not None else max(64 * MB, needed // 100)
    free = shutil.disk_usage(folder).free
    if free < needed + spare:
        raise MailError(
            f"There is not enough room in {folder}: the new mbox needs about {human_size(needed + spare)} "
            f"and {human_size(free)} is free."
        )


# --- Copying and checking ----------------------------------------------------------------------


@dataclass(frozen=True)
class WriteResult:
    path: Path
    source_id: int
    mails: int
    size: int


def hash_ranges(path: str, ranges: Sequence[tuple[int, int]]) -> list[str]:
    """The SHA-256 of each (offset, length) range of a file (runs in the workers)."""
    found = []
    with open(path, "rb") as handle:
        for offset, length in ranges:
            handle.seek(offset)
            digest = hashlib.sha256()
            left = length
            while left > 0:
                chunk = handle.read(min(BLOCK, left))
                if not chunk:
                    break
                digest.update(chunk)
                left -= len(chunk)
            found.append(digest.hexdigest())
    return found


def _runs(rows: Sequence[tuple[int, int, int, str]]) -> list[tuple[int, int]]:
    """Neighbouring mails' ranges joined, so they are copied in one go."""
    runs: list[tuple[int, int]] = []
    for _, offset, length, _ in rows:
        if runs and runs[-1][0] + runs[-1][1] == offset:
            runs[-1] = (runs[-1][0], runs[-1][1] + length)
        else:
            runs.append((offset, length))
    return runs


def _copy_runs(handle: IO[bytes], out: IO[bytes], runs: list[tuple[int, int]], seekable: bool,
               report: Callable[[int], None]) -> None:  # fmt: skip
    position = written = 0
    for offset, length in runs:
        if seekable:
            handle.seek(offset)
        else:  # a zip member: read forward to the run
            while position < offset:
                skipped = handle.read(min(BLOCK, offset - position))
                if not skipped:
                    raise MailError("The source ended before the mails the index lists.")
                position += len(skipped)
        left = length
        while left > 0:
            chunk = handle.read(min(BLOCK, left))
            if not chunk:
                raise MailError("The source ended before the mails the index lists.")
            out.write(chunk)
            left -= len(chunk)
            written += len(chunk)
        position = offset + length
        report(written)


def _check(part: Path, rows: Sequence[tuple[int, int, int, str]], workers: int,
           report: Callable[[int], None]) -> None:  # fmt: skip
    """Every mail of the written file against the index: its size, then each mail's SHA-256."""
    offsets, at = [], 0
    for _, _, length, _ in rows:
        offsets.append((at, length))
        at += length
    if part.stat().st_size != at:
        raise MailError(
            "The new mbox did not pass its check (its size is wrong); nothing was kept."
        )
    count = max(1, min(len(offsets), workers * 4))
    chunks = [offsets[i::count] for i in range(count)]
    if workers > 1 and len(offsets) > 1:
        pool = concurrent.futures.ProcessPoolExecutor(
            max_workers=workers, mp_context=multiprocessing.get_context("spawn")
        )
        try:
            hashed = list(pool.map(hash_ranges, [str(part)] * count, chunks))
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    else:
        hashed = [hash_ranges(str(part), chunk) for chunk in chunks]
    for number, (chunk, digests) in enumerate(zip(chunks, hashed)):
        expected = [rows[i * count + number][3] for i in range(len(chunk))]
        if digests != expected:
            raise MailError(
                "The new mbox did not pass its check (a mail differs from its source); "
                "nothing was kept."
            )
    report(at)


def write_mbox(
    index: MailIndex,
    source_id: int,
    keep: Iterable[int],
    tag: str,
    today: Optional[date] = None,
    workers: int = 1,
    progress: Optional[Callable[[Progress], None]] = None,
) -> WriteResult:
    """Write the mails of a source whose positions are in `keep` to a new mbox beside it, checked
    mail by mail, and record it in the index as the source's `cleaned` or `reduced` child."""
    source = index.connection.execute(
        "SELECT path, member, account, status FROM sources WHERE id = ?", (source_id,)
    ).fetchone()
    if source is None or source[3] != "read":
        raise MailError("That mbox has not been read into the index yet.")
    path, member, account = Path(source[0]), str(source[1]), str(source[2])
    wanted = set(keep)
    rows = [
        (int(p), int(o), int(n), str(s))
        for p, o, n, s in index.connection.execute(
            "SELECT position, offset, length, sha256 FROM mails WHERE source_id = ? "
            "ORDER BY position",
            (source_id,),
        )
        if p in wanted
    ]
    needed = sum(n for _, _, n, _ in rows)
    target = output_path(path, member, tag, today or date.today())
    preflight(target.parent, needed)
    part = target.with_name(target.name + ".part")
    name = target.name

    def report(stage: str) -> Callable[[int], None]:
        def tell(done: int) -> None:
            if progress is not None:
                progress(Progress(stage, done, needed, name))

        return tell

    report("writing")(0)
    try:
        with part.open("wb") as out:
            if member:
                with zipfile.ZipFile(path) as archive, archive.open(member) as handle:
                    _copy_runs(handle, out, _runs(rows), False, report("writing"))
            else:
                with path.open("rb") as handle:
                    _copy_runs(handle, out, _runs(rows), True, report("writing"))
            out.flush()
            os.fsync(out.fileno())
        _check(part, rows, max(1, workers), report("checking"))
        os.replace(part, target)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    new_id = index.record_written(target, tag.lower(), source_id, account, [r[0] for r in rows])
    return WriteResult(target, new_id, len(rows), needed)


def extract(index: MailIndex, source_id: int, positions: Iterable[int], target: Path) -> int:
    """Copy the mails at `positions` (byte for byte, in their order) into a new mbox at `target`,
    for an import to read; returns its size. Nothing is recorded in the index."""
    source = index.connection.execute(
        "SELECT path, member FROM sources WHERE id = ?", (source_id,)
    ).fetchone()
    if source is None:
        raise MailError("That mbox has not been read into the index yet.")
    wanted = set(positions)
    rows = [
        (int(p), int(o), int(n), str(s))
        for p, o, n, s in index.connection.execute(
            "SELECT position, offset, length, sha256 FROM mails WHERE source_id = ? "
            "ORDER BY position",
            (source_id,),
        )
        if p in wanted
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    path, member = Path(source[0]), str(source[1])
    with target.open("wb") as out:
        if member:
            with zipfile.ZipFile(path) as archive, archive.open(member) as handle:
                _copy_runs(handle, out, _runs(rows), False, lambda done: None)
        else:
            with path.open("rb") as handle:
                _copy_runs(handle, out, _runs(rows), True, lambda done: None)
    return sum(n for _, _, n, _ in rows)
