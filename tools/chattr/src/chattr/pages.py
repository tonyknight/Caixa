"""Render the planned pages as self-contained HTML.

Every person and group has **one page** with everything from them, every platform and every year:
a summary (how much, from when to when, from which sources, their groups and mail), a bar of years,
a heat-map calendar per year, a block per date, and an entry per message with a platform badge, a
stable `id="m-<id>"` anchor, the sender, and the local time with its offset (or "UTC" / "zone
unknown") at the stored precision.

A page can hold a whole life's messages with someone, so it is built to open at once however long it
is: the browser draws it as it reads it (the top is on screen before the end has arrived), it lays
out only the dates that are on screen (`content-visibility`), and pictures, video and audio load
only when they are scrolled to. A bar of years stays at the top while reading; each year begins with
its calendar. The page needs no script; one small script (`templates/lightbox.js`) adds a
full-size view of the pictures, and without it each picture is still a link to its file. Caixa's
viewer allows that one script, by its hash, and no other. Text is always
escaped; links are only made from http(s) addresses; attachment links are only made to files that
exist inside the given attachment folders. A JSON data island (`#chattr-data`) carries every stored
column of the page's messages so the database can be rebuilt from the pages.
"""

from __future__ import annotations

import base64
import calendar
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, Union
from urllib.parse import quote, urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from chattr import blobs, mail_html
from chattr.database_manager import DatabaseManager
from chattr.filing import playable_copy
from chattr.render import GROUPS, PEOPLE, PageSpec, Renderer, compact

PathLike = Union[str, Path]
_TEMPLATES = Path(__file__).resolve().parent / "templates"
_MINUS = "−"
_ISLAND_ESCAPES = {
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
    " ": "\\u2028",
    " ": "\\u2029",
}
_ISLAND_TABLE = str.maketrans(_ISLAND_ESCAPES)


def _nl2br(value: Optional[str]) -> Markup:
    """Escape text, then keep its line breaks."""
    return Markup("<br>\n").join(escape(line) for line in (value or "").split("\n"))


#: Raised when what the pages hold changes outside the templates (who a mail is filed with, what
#: removing someone takes away), so that boxes drawn before are redrawn when they are opened.
#: 2: the mail of people removed from the box is kept under People/Removed.
DRAWING = 2


def templates_fingerprint() -> str:
    """A short hash of every page template, script and style Chattr draws with (and of `DRAWING`):
    pages drawn with a different one were drawn by another version and lack what this one draws."""
    digest = hashlib.sha256(f"drawing {DRAWING}\0".encode())
    for file in sorted(p for p in _TEMPLATES.rglob("*") if p.is_file()):
        digest.update(file.relative_to(_TEMPLATES).as_posix().encode() + b"\0" + file.read_bytes())
    return digest.hexdigest()[:16]


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES)), autoescape=select_autoescape(["html"])
    )
    env.filters["nl2br"] = _nl2br
    return env


def island_json(document: dict[str, Any]) -> str:
    """The data island's JSON, safe to place inside a `<script>` element."""
    text = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    return text.translate(_ISLAND_TABLE)  # (one pass: a page's data can run to megabytes)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "other"


def _duration(seconds: Optional[int]) -> Optional[str]:
    if seconds is None:
        return None
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _offset_text(message: dict[str, Any]) -> str:
    offset = message["tz_offset_minutes"]
    if message["tz_assumed"] and not offset:
        return "zone unknown"
    if offset is None:
        return "zone unknown"
    if offset == 0:
        return "UTC"
    sign = "+" if offset > 0 else _MINUS
    hours, minutes = divmod(abs(offset), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _time_text(message: dict[str, Any]) -> str:
    local: datetime = message["local"]
    return local.strftime("%H:%M" if message["time_precision"] == "minute" else "%H:%M:%S")


def _attachment_kind(mime: Optional[str], name: str) -> str:
    major = (mime or "").split("/")[0]
    if major in ("image", "video", "audio"):
        return major
    suffix = Path(name).suffix.lower()
    if suffix in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"):
        return "image"
    if suffix in (".mp4", ".mov", ".webm"):
        return "video"
    if suffix in (".mp3", ".m4a", ".aac", ".wav", ".amr", ".opus", ".caf"):
        return "audio"
    return "file"


class _Unchanged(Exception):
    """A page is just as it was written the last time: leave its file be."""


def _plain(value: Any) -> Any:
    """What JSON cannot say, said steadily (a page's fingerprint must not vary between runs)."""
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=repr)
    if isinstance(value, Path):
        return value.as_posix()
    return str(value)


class _Site:
    """Everything a page needs beyond the Renderer: where files are and how to link to them."""

    def __init__(self, renderer: Renderer, out_root: Path, attachment_roots: Iterable[PathLike]):
        self.renderer = renderer
        self.out_root = out_root
        # the output folder first: filed attachments are recorded relative to it
        self.roots = [out_root.resolve(), *(Path(r).resolve() for r in attachment_roots)]
        self.env = _environment()
        #: Mail conversations' summaries: {thread (its conversation's source id): (text, model)}.
        self.summaries: dict[str, tuple[str, str]] = {}
        self._finder = blobs.Finder()
        self._page_dirs: dict[Path, str] = {}
        #: What each page was drawn from the last time it was written: {path: [fingerprint, size,
        #: mtime_ns]} (see `draw`); and what this run drew, to record for the next.
        self.known: dict[str, list[Any]] = {}
        self.drawn: dict[str, list[Any]] = {}
        self._templates = templates_fingerprint()
        self._page: Optional[str] = None  # the page being drawn (its path under out_root)

    def draw(self, template: str, **context: Any) -> str:
        """The page from its template and its data, unless both are what it was drawn from the last
        time and its file is still as written then: then `_Unchanged` (leave the file be)."""
        digest = hashlib.sha256(f"{self._templates}\0{template}\0".encode())
        digest.update(
            json.dumps(context, sort_keys=True, default=_plain, ensure_ascii=False).encode()
        )
        fingerprint = digest.hexdigest()
        page = self._page
        if page is not None:
            self.drawn[page] = [fingerprint]
            was = self.known.get(page)
            if was and was[0] == fingerprint:
                try:
                    status = os.stat(self.out_root / page)
                except OSError:
                    status = None
                if status and [status.st_size, status.st_mtime_ns] == was[1:3]:
                    self.drawn[page] = was
                    raise _Unchanged()
        return self.env.get_template(template).render(**context)

    def _file(self, storage_path: Optional[str]) -> Optional[Path]:
        if not storage_path:
            return None
        found = self._finder.find(storage_path, self.roots)
        return found[0] if found else None

    def _link(self, file: Path, page_dir: Path) -> str:
        real = self._page_dirs.get(page_dir)
        if real is None:
            real = self._page_dirs[page_dir] = str(page_dir.resolve())
        relative = os.path.relpath(file, real).replace(os.sep, "/")
        return quote(relative, safe="/()")

    def playable(self, storage_path: Optional[str], page_dir: Path) -> Optional[str]:
        """A link to the browser-playable copy of an audio file, when one has been made."""
        file = self._file(storage_path)
        copy = playable_copy(file) if file else None
        return self._link(copy, page_dir) if copy and copy.is_file() else None

    def href(self, storage_path: Optional[str], page_dir: Path) -> Optional[str]:
        """A relative link to an archived file, only if it exists inside one of the roots."""
        file = self._file(storage_path)
        return self._link(file, page_dir) if file else None

    def label(self, handle_id: Optional[int]) -> str:
        if not handle_id:
            return "Me"
        handle = self.renderer.handles[handle_id]
        return handle["person"] or handle["display_name"] or handle["identifier"]


def _standing_reactions(site: _Site, message_id: str) -> list[dict[str, str]]:
    """Reactions still in force: a later removal cancels the same sender's earlier one."""
    standing: dict[tuple[Any, ...], dict[str, Any]] = {}
    for reaction in sorted(
        site.renderer.reactions.get(message_id, []),
        key=lambda r: (r["timestamp_utc"] or "", r["id"]),
    ):
        key = (
            reaction["sender_handle_id"],
            reaction["type"],
            reaction["emoji"],
            reaction["target_part"],
        )
        if reaction["action"] == "removed":
            standing.pop(key, None)
        else:
            standing[key] = reaction
    return [
        {
            "label": r["emoji"] or r["type"],
            "who": site.label(r["sender_handle_id"]),
        }
        for r in standing.values()
    ]


def _entry(site: _Site, message: dict[str, Any], page_dir: Path) -> dict[str, Any]:
    specific = json.loads(message["service_specific"]) if message["service_specific"] else {}
    kind = message["content_type"]
    sender = message["sender_handle_id"]
    if kind == "system" or (not sender and not message["is_from_owner"]):
        direction = "system"
    else:
        direction = "sent" if message["is_from_owner"] else "received"
    link = None
    if specific.get("shared_link") and urlparse(specific["shared_link"]).scheme in (
        "http",
        "https",
    ):
        link = {
            "href": specific["shared_link"],
            "text": specific.get("link_text") or specific["shared_link"],
            "summary": specific.get("link_summary") or "",
            "site": specific.get("link_site") or "",
        }
    call_label = {
        "received": "Received call",
        "placed": "Placed call",
        "missed": "Missed call",
    }.get(specific.get("direction", ""), "Call")
    service = message["service"]
    return {
        "id": message["id"],
        "service": service,
        "service_slug": _slug(service),
        "direction": direction,
        "kind": kind if kind in ("call", "voicemail", "system") else "text",
        "author": site.label(sender) if sender else ("Me" if message["is_from_owner"] else ""),
        "iso": message["timestamp_utc"],
        "time": _time_text(message),
        "offset": _offset_text(message),
        "body": message["body"],
        "translation": message["translation"],
        "transcript": message["transcript"],
        "call_label": call_label,
        "duration": _duration(specific.get("duration_seconds")),
        "link": link,
        "link_text": None if link else specific.get("link_text"),
        "attachments": [
            {
                "name": a["original_filename"]
                or (a["storage_path"] or "").rsplit("/", 1)[-1]
                or "file",
                "href": site.href(a["storage_path"], page_dir),
                "kind": _attachment_kind(
                    a["mime_type"], a["original_filename"] or a["storage_path"] or ""
                ),
                "playable": site.playable(a["storage_path"], page_dir),
                "format": Path(a["storage_path"] or a["original_filename"] or "").suffix.lower(),
                "needs_copy": playable_copy(Path(a["storage_path"] or "x")) is not None,
            }
            for a in site.renderer.attachments.get(message["id"], [])
        ],
        "reactions": _standing_reactions(site, message["id"]),
        "reply": _reply(site, message, page_dir),
        "edits": [
            {"text": e.get("text") or "", "at": _when(e.get("at"), message)}
            for e in specific.get("edits", [])[:-1]  # the last is the text shown
        ],
        "edited": bool(specific.get("edits") or specific.get("edited_at")),
        "marks": [
            *(["Deleted in Messages"] if specific.get("recently_deleted") else []),
            *([str(specific["effect"])] if specific.get("effect") else []),
            *([str(specific["apple_filter"]).capitalize()] if specific.get("apple_filter") else []),
        ],
    }


def _when(iso: Optional[str], message: dict[str, Any]) -> str:
    """An edit's time in the message's own zone, as the page shows times."""
    try:
        moment = datetime.fromisoformat(str(iso))
    except ValueError:
        return ""
    offset = message["tz_offset_minutes"]
    if offset is not None:
        moment = moment + timedelta(minutes=offset)
    return f"{moment:%Y-%m-%d %H:%M:%S}"


def _reply(site: _Site, message: dict[str, Any], page_dir: Path) -> Optional[dict[str, str]]:
    """What a reply answers: who said it, its first words, and a link to it (on any page)."""
    target_id = site.renderer.by_source.get(message["reply_to"] or "")
    target = site.renderer.messages.get(target_id or "")
    if target is None:
        return None
    spec = site.renderer.page_of.get(target["id"])
    here = site.renderer.page_of.get(message["id"])
    href = f"#m-{target['id']}"
    if spec is not None and here is not None and spec.path != here.path:
        other = os.path.relpath(site.out_root / spec.path, page_dir).replace(os.sep, "/")
        href = quote(other, safe="/()") + href
    words = (target["body"] or target["transcript"] or "").strip().replace("\n", " ")
    sender = target["sender_handle_id"]
    return {
        "href": href,
        "author": site.label(sender) if sender else ("Me" if target["is_from_owner"] else ""),
        "text": (words[:120] + "…") if len(words) > 120 else (words or "(no text)"),
    }


def _calendar(year: int, counts: dict[str, int]) -> list[dict[str, Any]]:
    busiest = max(counts.values(), default=1)
    months = []
    for month in range(1, 13):
        cells = []
        for week in calendar.monthcalendar(year, month):
            for day in week:
                date = f"{year}-{month:02d}-{day:02d}" if day else ""
                count = counts.get(date, 0)
                level = 0 if not count else max(1, min(4, -(-count * 4 // busiest)))
                cells.append({"day": day, "date": date, "count": count, "level": level})
        months.append({"name": calendar.month_name[month], "cells": cells})
    return months


def _day_label(date: datetime) -> str:
    return f"{date:%A}, {date:%B} {date.day}, {date.year}"


#: How many words of a conversation's first mail its entry shows when it has no summary.
OPENING_WORDS = 40


def _opening(text: str) -> str:
    """The first words of a mail, before any quoted earlier mail."""
    own = []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        if line.lstrip().startswith(">") or re.match(r"^On .+ wrote:$", line.strip()):
            break
        own.append(line)
    words = " ".join(own).split()
    return " ".join(words[:OPENING_WORDS]) + ("…" if len(words) > OPENING_WORDS else "")


def _conversation_entry(site: _Site, mail: PageSpec, page_dir: Path) -> dict[str, Any]:
    """A mail conversation on a person's page: who began it and when, its subject, its summary
    (or its first words until it has one), its counts, and a link to its page."""
    renderer = site.renderer
    first = renderer.messages[mail.message_ids[0]]
    files = 0
    for message_id in mail.message_ids:
        for row in renderer.attachments.get(message_id, []):
            info = json.loads(row["processing_info"] or "{}")
            files += not (info.get("dropped") or info.get("signature"))
    sender = first["sender_handle_id"]
    counts = _plural(len(mail.message_ids), "mail") + (
        f" · {_plural(files, 'file')}" if files else ""
    )
    href = os.path.relpath(site.out_root / mail.path, page_dir).replace(os.sep, "/")
    thread = renderer.conversations[mail.conversation_ids[0]]["source_id"]
    summary = site.summaries.get(thread)
    return {
        "kind": "conversation",
        "id": first["id"],
        "direction": "sent" if first["is_from_owner"] else "received",
        "account": mail.account,
        "author": "Me" if first["is_from_owner"] or not sender else site.label(sender),
        "iso": first["timestamp_utc"],
        "time": _time_text(first),
        "offset": _offset_text(first),
        "subject": mail.title,
        "summary": summary[0] if summary else _opening(first["body"] or ""),
        "model": summary[1] if summary else "",
        "counts": counts,
        "href": quote(href, safe="/()"),
    }


def _message_page(site: _Site, spec: PageSpec, relations: "_Relations") -> str:
    renderer = site.renderer
    page_dir = site.out_root / spec.folder
    up = "../" * (spec.folder.count("/") + 1)
    years: dict[int, dict[str, Any]] = {}
    services: dict[str, int] = {}
    # what the timeline shows: each message, and each mail conversation (as one entry, at its
    # first mail, standing for all its mails)
    shown: list[tuple[dict[str, Any], int, str, Optional[PageSpec]]] = [
        (renderer.messages[m], 1, renderer.messages[m]["service"], None) for m in spec.message_ids
    ]
    shown += [
        (renderer.messages[m.message_ids[0]], len(m.message_ids), "Mail", m) for m in spec.mail
    ]
    shown.sort(key=lambda s: (s[0]["timestamp_utc"], s[0]["id"]))
    for message, items, service, mail in shown:
        local: datetime = message["local"]
        year = years.setdefault(
            local.year, {"year": local.year, "count": 0, "counts": {}, "days": {}}
        )
        key = f"{local:%Y-%m-%d}"
        year["count"] += items
        year["counts"][key] = year["counts"].get(key, 0) + 1
        day = year["days"].setdefault(key, {"date": key, "label": _day_label(local), "entries": []})
        day["entries"].append(
            _conversation_entry(site, mail, page_dir) if mail else _entry(site, message, page_dir)
        )
        services[service] = services.get(service, 0) + items
    ordered = []
    for number in sorted(years):
        year = years[number]
        ordered.append(
            {
                "year": number,
                "count": _plural(year["count"], "item"),
                "months": _calendar(number, year["counts"]),
                "days": list(year["days"].values()),
            }
        )
    first, last = shown[0][0]["local"], shown[-1][0]["local"]
    return site.draw(
        "page.html",
        title=spec.title,
        kind=spec.kind,
        total=_plural(sum(s[1] for s in shown), "item"),
        first=f"{first:%Y-%m-%d}",
        last=f"{last:%Y-%m-%d}",
        sources=[
            {"name": name, "slug": _slug(name), "count": _plural(count, "item")}
            for name, count in sorted(services.items())
        ],
        related=relations.related(spec, up),
        mail=relations.mail(spec, up),
        conversations=bool(spec.mail),
        years=ordered,
        back=f"{up}index.html",
        island=Markup(island_json(compact(renderer.document(spec)))),
    )


def _people_line(people: Iterable[dict[str, str]]) -> str:
    return ", ".join(
        f"{p['name']} <{p['address']}>" if p.get("name") else p["address"] for p in people
    )


#: The largest picture embedded in a mail's frame; a larger one is listed with the mail's files.
EMBED_BYTES = 4 * 1024 * 1024


def _people(people: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    return [{"name": p.get("name") or "", "address": p.get("address") or ""} for p in people]


def _embedded(site: _Site, specific: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, str]:
    """The pictures a mail's HTML shows by Content-ID, as `data:` addresses (a frame that runs
    nothing cannot load a file from disk)."""
    by_sha = {f["sha256"]: f for f in files}
    images: dict[str, str] = {}
    for cid, sha in (specific.get("content_ids") or {}).items():
        row = by_sha.get(sha)
        file = site._file(row["storage_path"]) if row else None
        if row is None or file is None or file.stat().st_size > EMBED_BYTES:
            continue
        mime = row["mime_type"] or "application/octet-stream"
        images[cid] = f"data:{mime};base64," + base64.b64encode(file.read_bytes()).decode()
    return images


def _conversation_page(site: _Site, spec: PageSpec) -> str:
    """An account's conversation: each mail a card, its own HTML made safe in a frame that runs
    nothing, its files beneath it, and every header it came with folded away."""
    renderer = site.renderer
    page_dir = site.out_root / spec.folder
    cards = []
    for message_id in spec.message_ids:
        message = renderer.messages[message_id]
        headers = json.loads(message["mail_headers"]) if message["mail_headers"] else {}
        specific = json.loads(message["service_specific"]) if message["service_specific"] else {}
        handle = renderer.handles.get(message["sender_handle_id"] or 0)
        rows = renderer.attachments.get(message["id"], [])
        kept = [r for r in rows if "dropped" not in json.loads(r["processing_info"] or "{}")]
        images = _embedded(site, specific, kept)
        shown = {(specific.get("content_ids") or {})[cid] for cid in images}
        html_body = specific.get("body_html")
        body = (
            mail_html.original(html_body, images) if html_body
            else mail_html.plain(message["body"] or "")
        )  # fmt: skip
        files = []
        for row in kept:
            if row["sha256"] in shown:
                continue
            name = row["original_filename"] or "attachment"
            href = site.href(row["storage_path"], page_dir)
            kind = _attachment_kind(row["mime_type"], name)
            files.append({"name": name, "href": href, "picture": kind == "image" and href})
        local: datetime = message["local"]
        cards.append(
            {
                "id": message["id"],
                "direction": "sent" if message["is_from_owner"] else "received",
                "subject": headers.get("subject") or "(no subject)",
                "iso": message["timestamp_utc"],
                "date": f"{local:%Y-%m-%d}",
                "time": _time_text(message),
                "offset": _offset_text(message),
                "name": site.label(message["sender_handle_id"]) if handle else "unknown sender",
                "address": handle["identifier"] if handle else "",
                "to": _people(headers.get("to", [])),
                "cc": _people(headers.get("cc", [])),
                "body": Markup(body),
                "files": files,
                "headers": specific.get("headers") or "",
            }
        )
    depth = spec.folder.count("/") + 1
    return site.draw(
        "conversation.html",
        title=spec.title,
        account=spec.account,
        cards=cards,
        back="../" * depth + "index.html",
        island=Markup(island_json(compact(renderer.document(spec)))),
    )


def _mail_page(site: _Site, spec: PageSpec) -> str:
    if spec.account:
        return _conversation_page(site, spec)
    renderer = site.renderer
    page_dir = site.out_root / spec.folder
    mails = []
    for message_id in spec.message_ids:
        message = renderer.messages[message_id]
        headers = json.loads(message["mail_headers"]) if message["mail_headers"] else {}
        specific = json.loads(message["service_specific"]) if message["service_specific"] else {}
        handle = renderer.handles.get(message["sender_handle_id"] or 0)
        address = handle["identifier"] if handle else ""
        name = site.label(message["sender_handle_id"]) if handle else "unknown sender"
        local: datetime = message["local"]
        mails.append(
            {
                "id": message["id"],
                "direction": "sent" if message["is_from_owner"] else "received",
                "author": name,
                "iso": message["timestamp_utc"],
                "date": f"{local:%Y-%m-%d}",
                "time": _time_text(message),
                "offset": _offset_text(message),
                "from_line": f"{name} <{address}>" if address and address != name else name,
                "to": _people_line(headers.get("to", [])),
                "cc": _people_line(headers.get("cc", [])),
                "subject": headers.get("subject") or "(no subject)",
                "labels": ", ".join(headers.get("labels", [])),
                "body": message["body"] or "",
                "has_html": bool(specific.get("body_html")),
                "attachments": [
                    {
                        "name": a["original_filename"] or "attachment",
                        "href": site.href(a["storage_path"], page_dir),
                    }
                    for a in renderer.attachments.get(message["id"], [])
                ],
            }
        )
    depth = spec.folder.count("/") + 1
    return site.draw(
        "mail.html",
        title=spec.title,
        mails=mails,
        back="../" * depth + "index.html",
        island=Markup(island_json(compact(renderer.document(spec)))),
    )


#: The categories the index sorts people into (a person in none is "unassigned"), and their names.
CATEGORIES = (
    ("family", "Family"),
    ("friends", "Friends"),
    ("business", "Business"),
    ("acquaintance", "Acquaintances"),
    ("unrecognized", "Unrecognized"),
)
_HUES = 8


def _initials(title: str) -> str:
    words = [w for w in re.split(r"[\s\-_.]+", title) if w and (w[0].isalnum())]
    if not words:
        return "#"
    if not any(c.isalpha() for c in title):  # a number: its last two digits
        digits = re.sub(r"\D", "", title)
        return digits[-2:] or "#"
    letters = [w[0] for w in words if w[0].isalpha()] or [words[0][0]]
    return (letters[0] + (letters[-1] if len(letters) > 1 else "")).upper()


def _hue(title: str) -> str:
    return f"h{sum(title.encode('utf-8')) % _HUES}"


def _size(bytes_: int) -> str:
    size = float(bytes_)
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:,.0f} {unit}" if unit == "bytes" else f"{size:,.1f} {unit}"
        size /= 1024
    return f"{size:,.1f} TB"


def _page_handles(renderer: Renderer, spec: PageSpec) -> set[int]:
    """The handles a person's or group's page is about (not the owner's): its conversations'
    people and senders, and, for the mail entries on a person's page, the handles that are them."""
    handles: set[int] = set()
    for conversation_id in spec.conversation_ids:
        handles |= set(renderer.participants.get(conversation_id, []))
    handles |= {
        renderer.messages[m]["sender_handle_id"]
        for m in spec.message_ids
        if renderer.messages[m]["sender_handle_id"]
    }
    for mail in spec.mail:
        for conversation_id in mail.conversation_ids:
            for handle in renderer.participants.get(conversation_id, []):
                if renderer.label(handle) == spec.title:
                    handles.add(handle)
        for m in mail.message_ids:
            handle = renderer.messages[m]["sender_handle_id"]
            if handle and renderer.label(handle) == spec.title:
                handles.add(handle)
    return {h for h in handles if h not in renderer.owner_handles and h in renderer.handles}


def _named(renderer: Renderer, spec: PageSpec) -> bool:
    """Whether a person's page is someone named (not a number, an address or an account that
    no longer has a name, which are 'unrecognized' until someone names them)."""
    return any(renderer.handles[h]["person"] for h in _page_handles(renderer, spec))


def _handles(renderer: Renderer, spec: PageSpec) -> str:
    """The numbers, addresses and accounts on a person's page (not the owner's), as JSON for the
    index's tile: naming or removing someone nobody named works on these."""
    found = sorted(
        {
            (renderer.handles[h]["service"], renderer.handles[h]["identifier"])
            for h in _page_handles(renderer, spec)
        }
    )
    return json.dumps([{"service": s, "identifier": i} for s, i in found], ensure_ascii=False)


def _card(renderer: Renderer, page: PageSpec, href: str) -> dict[str, Any]:
    """What a tile shows about a person or group: counts, years, and each source's share."""
    by_source: dict[str, int] = {}
    ids = [*page.message_ids, *(m for mail in page.mail for m in mail.message_ids)]
    for message_id in ids:
        service = renderer.messages[message_id]["service"]
        by_source[service] = by_source.get(service, 0) + 1
    moments = sorted(
        (renderer.messages[m]["timestamp_utc"], renderer.messages[m]["local"]) for m in ids
    )
    first, last = moments[0][1], moments[-1][1]
    return {
        "title": page.title,
        "href": href,
        "count": _plural(len(ids), "item"),
        "item_count": len(ids),
        "span": str(first.year) if first.year == last.year else f"{first.year}–{last.year}",
        "first": f"{first:%Y-%m-%d}",
        "last": f"{last:%Y-%m-%d}",
        "sources": [
            {"name": name, "slug": _slug(name), "count": f"{count:,}"}
            for name, count in sorted(by_source.items(), key=lambda item: -item[1])
        ],
        "initials": _initials(page.title),
        "hue": _hue(page.title),
    }


def _stats(site: _Site) -> dict[str, Any]:
    """The dashboard: how much came from each source, and how much room its files take."""
    renderer = site.renderer
    sources: dict[str, dict[str, Any]] = {}
    seen_files: set[Path] = set()
    for message in renderer.messages.values():
        entry = sources.setdefault(
            message["service"],
            {
                "items": 0,
                "conversations": set(),
                "files": 0,
                "bytes": 0,
                "first": None,
                "last": None,
            },
        )
        entry["items"] += 1
        entry["conversations"].add(message["conversation_id"])
        local = message["local"]
        entry["first"] = (
            local if entry["first"] is None or local < entry["first"] else entry["first"]
        )
        entry["last"] = local if entry["last"] is None or local > entry["last"] else entry["last"]
        for attachment in renderer.attachments.get(message["id"], []):
            file = site._file(attachment["storage_path"])
            if file is None or file in seen_files:
                continue
            seen_files.add(file)
            entry["files"] += 1
            entry["bytes"] += file.stat().st_size
    rows = []
    for name, entry in sorted(sources.items(), key=lambda item: -item[1]["items"]):
        rows.append(
            {
                "name": name,
                "slug": _slug(name),
                "items": f"{entry['items']:,}",
                "conversations": f"{len(entry['conversations']):,}",
                "files": f"{entry['files']:,}",
                "size": _size(entry["bytes"]),
                "first": f"{entry['first']:%Y-%m-%d}",
                "last": f"{entry['last']:%Y-%m-%d}",
            }
        )
    firsts = [e["first"] for e in sources.values()]
    lasts = [e["last"] for e in sources.values()]
    first, last = (min(firsts), max(lasts)) if firsts else (None, None)
    pages = renderer.pages
    return {
        "items": f"{len(renderer.messages):,}",
        "conversations": f"{sum(len(e['conversations']) for e in sources.values()):,}",
        "people": f"{sum(1 for p in pages if p.kind == 'person' and _named(renderer, p)):,}",
        "groups": f"{sum(1 for p in pages if p.kind == 'group'):,}",
        "mail": f"{sum(1 for p in pages if p.kind == 'mail'):,}",
        "by_account": [
            {"account": account, "count": f"{count:,}"}
            for account, count in sorted(
                Counter(p.account for p in pages if p.kind == "mail" and p.account).items(),
                key=lambda item: str(item[0]).casefold(),
            )
        ],
        "files": f"{sum(e['files'] for e in sources.values()):,}",
        "size": _size(sum(e["bytes"] for e in sources.values())),
        "first": f"{first:%Y-%m-%d}" if first else "",
        "last": f"{last:%Y-%m-%d}" if last else "",
        "years": f"{last.year - first.year + 1:,} years" if first and last else "",
        "span": (
            f"{first.year}–{last.year}"
            if first and last and first.year != last.year
            else (str(first.year) if first else "empty")
        ),
        "sources": rows,
    }


#: The categories that have subcategories (all but Unrecognized).
WITH_SUBCATEGORIES = ("family", "friends", "business", "acquaintance")


def _subcategory_tree(given: Optional[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """{category: [subcategory, with its own under `children`]}, in the order given (by name)."""
    tree: dict[str, list[dict[str, Any]]] = {key: [] for key in WITH_SUBCATEGORIES}
    rows = list((given or {}).get("tree") or [])
    tops = {int(r["id"]): {**r, "children": []} for r in rows if r.get("parent_id") is None}
    for row in rows:
        if row.get("parent_id") is not None and int(row["parent_id"]) in tops:
            tops[int(row["parent_id"])]["children"].append(dict(row))
    for top in tops.values():
        if top["category"] in tree:
            tree[top["category"]].append(top)
    for subs in tree.values():
        subs.sort(key=lambda s: str(s["name"]).casefold())
        for top in subs:
            top["children"].sort(key=lambda s: str(s["name"]).casefold())
    return tree


def _index(
    site: _Site,
    categories: Optional[Mapping[str, str]] = None,
    title: str = "Chattr archive",
    subcategories: Optional[Mapping[str, Any]] = None,
    links: Optional[Sequence[Mapping[str, Any]]] = None,
) -> str:
    """The index: people as tiles sorted into categories (and their subcategories), groups, mail,
    and the box's numbers; `links` (`[{group, links: [{label, href, count}]}]`) are plain links a
    program using Chattr adds to the sidebar, under their group."""
    renderer = site.renderer
    chosen = {name.casefold(): category for name, category in (categories or {}).items()}
    placed = {
        str(name).casefold(): str(sub)
        for name, sub in ((subcategories or {}).get("placed") or {}).items()
    }
    keys = {key for key, _ in CATEGORIES}
    people: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    mail: list[dict[str, Any]] = []
    for page in renderer.pages:
        href = quote(page.path, safe="/()")
        if page.kind == "mail":
            first = renderer.messages[page.message_ids[0]]
            if page.account:  # by account: when it began, its subject, its person, its mails
                entry = {
                    "title": page.title,
                    "date": f"{first['local']:%Y-%m-%d}",
                    "person": page.home or page.correspondent or "",
                    "count": _plural(len(page.message_ids), "mail"),
                    "labels": _mail_labels(renderer, page),
                }
            else:  # Phase 1: one list
                entry = {
                    "title": page.filename.removesuffix(".html"),
                    "date": "",
                    "person": "",
                    "count": _plural(len(page.message_ids), "message"),
                    "labels": [],
                }
            mail.append(
                {**entry, "href": href, "account": page.account or "", "at": first["timestamp_utc"]}
            )
            continue
        card = _card(renderer, page, href)
        if page.kind == "group":
            groups.append(card)
            continue
        card["named"] = _named(renderer, page)
        card["handles"] = "" if card["named"] else _handles(renderer, page)
        category = chosen.get(page.title.casefold(), "")
        card["category"] = (
            (category if category in keys else "") if card["named"] else "unrecognized"
        )
        card["sub"] = placed.get(page.title.casefold(), "") if card["category"] else ""
        people.append(card)
    people.sort(key=lambda p: str(p["title"]).casefold())
    groups.sort(key=lambda g: str(g["title"]).casefold())
    counts = {key: sum(1 for p in people if p["category"] == key) for key, _ in CATEGORIES}
    counts["all"] = sum(1 for p in people if p["category"] != "unrecognized")
    counts["unassigned"] = sum(1 for p in people if p["category"] == "")
    return site.env.get_template("index.html").render(
        title=title,
        categories=[{"key": key, "label": label} for key, label in CATEGORIES],
        subcategories=_subcategory_tree(subcategories),
        counts={key: f"{value:,}" for key, value in counts.items()},
        people=people,
        groups=groups,
        mail=_mail_lists(mail),
        mail_count=len(mail),
        mail_tree=_mail_tree(mail),
        links=[dict(group) for group in (links or [])],
        stats=_stats(site),
    )


#: Gmail labels that say how a mail was read, not where it belongs.
NOT_LABELS = {"unread", "opened"}
#: The labels listed first under an account, in this order; the rest by name.
FIRST_LABELS = ("Inbox", "Sent")


def _mail_labels(renderer: Renderer, page: PageSpec) -> list[str]:
    """A mail conversation's labels: Gmail's own labels on its mails (not Unread, Opened or
    IMAP_…); a mail without them has the folder it was exported from (its mbox file's name)."""
    found: list[str] = []
    for message_id in page.message_ids:
        message = renderer.messages[message_id]
        headers = json.loads(message["mail_headers"]) if message["mail_headers"] else {}
        own = [
            str(label) for label in headers.get("labels", [])
            if str(label).strip() and str(label).casefold() not in NOT_LABELS
            and not str(label).upper().startswith("IMAP_")
        ]  # fmt: skip
        if not own:
            specific = (
                json.loads(message["service_specific"]) if message["service_specific"] else {}
            )
            own = [str(specific["folder"])] if specific.get("folder") else []
        found += [label for label in own if label not in found]
    first = [label for label in FIRST_LABELS if label in found]
    return first + sorted((l for l in found if l not in FIRST_LABELS), key=str.casefold)


def _mail_tree(mail: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The sidebar's Mail: each account (by name) with its conversations' labels and counts."""
    accounts = sorted({m["account"] for m in mail if m["account"]}, key=str.casefold)
    tree = []
    for number, account in enumerate(accounts, 1):
        mine = [m for m in mail if m["account"] == account]
        names: list[str] = []
        for m in mine:
            names += [label for label in m["labels"] if label not in names]
        first = [label for label in FIRST_LABELS if label in names]
        ordered = first + sorted((l for l in names if l not in FIRST_LABELS), key=str.casefold)
        tree.append(
            {
                "id": number,
                "account": account,
                "count": len(mine),
                "labels": [
                    {"id": n, "name": label, "count": sum(label in m["labels"] for m in mine)}
                    for n, label in enumerate(ordered, 1)
                ],
            }
        )
    return tree


def _mail_lists(mail: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The index's Mail view: a list per account (newest first), then mail without one."""
    accounts = sorted({m["account"] for m in mail if m["account"]}, key=str.casefold)
    lists = [
        {
            "account": account,
            "mails": sorted(
                (m for m in mail if m["account"] == account), key=lambda m: m["at"], reverse=True
            ),
        }
        for account in accounts
    ]
    rest = [m for m in mail if not m["account"]]
    return lists + ([{"account": "", "mails": rest}] if rest else [])


def _plural(count: int, word: str) -> str:
    return f"{count:,} {word}" if count == 1 else f"{count:,} {word}s"


class _Relations:
    """Who is in what, worked out once for every page (an archive can hold thousands of people):
    the groups each person is in, the people in each group, the mail each person is in."""

    def __init__(self, renderer: Renderer) -> None:
        self.renderer = renderer
        self.homes: dict[str, str] = {}  # person → their page
        self.groups_of: dict[str, dict[str, str]] = {}  # person → {group page: group title}
        self.members_of: dict[str, set[str]] = {}  # group page → its people
        self.mail_of: dict[str, list[PageSpec]] = {}  # person → mail threads they are in
        for spec in renderer.pages:
            if spec.kind == "person":
                self.homes[spec.title] = spec.path
            elif spec.kind == "group":
                names = self._members(spec)
                self.members_of.setdefault(spec.path, set()).update(names)
                for name in names:
                    self.groups_of.setdefault(name, {})[spec.path] = spec.title
            elif spec.kind == "mail" and not spec.account:  # (account mail: entries instead)
                for name in self._members(spec):
                    self.mail_of.setdefault(name, []).append(spec)

    def _members(self, spec: PageSpec) -> set[str]:
        renderer = self.renderer
        handles: set[int] = set()
        for conversation_id in spec.conversation_ids:
            handles |= set(renderer.participants.get(conversation_id, []))
        handles |= {
            renderer.messages[m]["sender_handle_id"]
            for m in spec.message_ids
            if renderer.messages[m]["sender_handle_id"]
        }
        return {renderer.label(h) for h in handles if h not in renderer.owner_handles}

    def related(self, spec: PageSpec, up: str) -> list[dict[str, Optional[str]]]:
        """A person's groups, or a group's people, each with a link to their page."""
        if spec.kind == "person":
            return [
                {"title": title, "href": quote(f"{up}{path}", safe="/().")}
                for path, title in sorted(self.groups_of.get(spec.title, {}).items())
            ]
        found: list[dict[str, Optional[str]]] = []
        for name in sorted(self.members_of.get(spec.path, set()), key=str.casefold):
            home = self.homes.get(name)
            found.append(
                {"title": name, "href": quote(f"{up}{home}", safe="/().") if home else None}
            )
        return found

    def mail(self, spec: PageSpec, up: str) -> list[dict[str, str]]:
        if spec.kind != "person":
            return []
        return [
            {"title": m.filename.removesuffix(".html"), "href": quote(f"{up}{m.path}", safe="/().")}
            for m in self.mail_of.get(spec.title, [])
        ]


PAGES_LIST = ".chattr-pages"


def _forget_old_pages(out_root: Path, record: Path, written: list[Path]) -> None:
    """Delete pages written last time that were not written now (a person was renamed or merged,
    a conversation went away), then any folder that leaves empty. Only `.html` files this
    function's own record names are ever deleted."""
    root = out_root.resolve()
    now = {path.resolve().relative_to(root).as_posix() for path in written}
    try:
        before = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        before = []
    for relative in before if isinstance(before, list) else []:
        if not isinstance(relative, str) or relative in now or not relative.endswith(".html"):
            continue
        page = (root / relative).resolve()
        if not page.is_relative_to(root) or not page.is_file():
            continue
        page.unlink()
        folder = page.parent
        while folder != root and folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
            folder = folder.parent
    record.parent.mkdir(parents=True, exist_ok=True)
    temporary = record.with_name(record.name + ".part")
    temporary.write_text(json.dumps(sorted(now), ensure_ascii=False, indent=0), encoding="utf-8")
    os.replace(temporary, record)


#: Fewer pages than this are written in the process: starting workers would cost more than it saves.
PARALLEL_FROM = 300


def _draw(site: _Site, relations: "_Relations", spec: PageSpec) -> Path:
    """Write a page, unless it is just as it was written the last time (see `_Site.draw`)."""
    path = site.out_root / spec.path
    site._page = spec.path
    try:
        text = (
            _mail_page(site, spec) if spec.kind == "mail" else _message_page(site, spec, relations)
        )
    except _Unchanged:
        return path
    finally:
        site._page = None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    status = path.stat()
    site.drawn[spec.path] = [site.drawn[spec.path][0], status.st_size, status.st_mtime_ns]
    return path


def _fingerprints(record: Path) -> Path:
    """Where what each page was drawn from is kept: beside the list of pages."""
    return record.with_name(record.stem + ".fingerprints.json")


def _known(record: Path) -> dict[str, list[Any]]:
    try:
        found = json.loads(_fingerprints(record).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        k: v for k, v in found.items() if isinstance(v, list) and len(v) == 3
    } if isinstance(found, dict) else {}  # fmt: skip


def _keep_known(record: Path, drawn: Mapping[str, list[Any]]) -> None:
    target = _fingerprints(record)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".part")
    temporary.write_text(
        json.dumps(dict(sorted(drawn.items())), separators=(",", ":")), encoding="utf-8"
    )
    os.replace(temporary, target)


def _draw_share(
    job: tuple[str, str, list[str], dict[str, Any], list[tuple[int, str]], dict[str, list[Any]]],
) -> dict[str, list[Any]]:
    """A worker's share of the pages: it reads the archive itself and writes the pages it is given
    (by their place in the plan, and their path, to be sure it plans the same pages). Returns
    what each was drawn from."""
    database, out_root, roots, summaries, share, known = job
    with DatabaseManager(database) as db:
        renderer = Renderer(db)
        site = _Site(renderer, Path(out_root), roots)
        site.summaries = {k: tuple(v) for k, v in summaries.items()}  # type: ignore[misc]
        site.known = known
        relations = _Relations(renderer)
        for index, path in share:
            spec = renderer.pages[index] if index < len(renderer.pages) else None
            if spec is None or spec.path != path:
                raise RuntimeError("The archive changed while its pages were being written.")
            _draw(site, relations, spec)
    return site.drawn


def _draw_in_workers(
    renderer: Renderer,
    site: _Site,
    database: PathLike,
    workers: int,
    progress: Optional[Callable[[int, int], None]],
) -> None:
    import concurrent.futures
    import multiprocessing

    plan = [(index, spec.path) for index, spec in enumerate(renderer.pages)]
    count = min(len(plan), workers * 4)  # several shares each, so a slow one does not hold the rest
    shares = [plan[n::count] for n in range(count)]
    roots = [str(r) for r in site.roots[1:]]
    summaries = {k: list(v) for k, v in site.summaries.items()}
    done, total = 0, len(plan)
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        futures = [
            pool.submit(
                _draw_share,
                (str(database), str(site.out_root), roots, summaries, share,
                 {path: site.known[path] for _, path in share if path in site.known}),
            )  # fmt: skip
            for share in shares
        ]
        drawn: dict[str, list[Any]] = {}
        for future in concurrent.futures.as_completed(futures):
            part = future.result()
            drawn.update(part)
            done += len(part)
            if progress:
                progress(done, total)
        site.drawn = drawn


def render_index(
    renderer: Renderer,
    out_root: PathLike,
    attachment_roots: Sequence[PathLike] = (),
    categories: Optional[Mapping[str, str]] = None,
    title: str = "Chattr archive",
    summaries: Optional[Mapping[str, tuple[str, str]]] = None,
    subcategories: Optional[Mapping[str, Any]] = None,
    links: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Path:
    """Write the index alone (who is in which category and subcategory changed, nothing else):
    the same index `render_pages` writes, without touching any other page."""
    site = _Site(renderer, Path(out_root), attachment_roots)
    site.summaries = dict(summaries or {})
    index = site.out_root / "index.html"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(_index(site, categories, title, subcategories, links), encoding="utf-8")
    return index


def render_pages(
    renderer: Renderer,
    out_root: PathLike,
    attachment_roots: Sequence[PathLike] = (),
    pages_list: Optional[PathLike] = None,
    categories: Optional[Mapping[str, str]] = None,
    title: str = "Chattr archive",
    summaries: Optional[Mapping[str, tuple[str, str]]] = None,
    subcategories: Optional[Mapping[str, Any]] = None,
    workers: int = 1,
    database: Optional[PathLike] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    parallel_from: int = PARALLEL_FROM,
    stats: Optional[dict[str, Any]] = None,
    links: Optional[Sequence[Mapping[str, Any]]] = None,
) -> list[Path]:
    """Write every page and the index under `out_root`; returns the files written.

    `categories` ({person's name: category}) sorts people on the index, and `subcategories`
    (`{"tree": [...], "placed": {name: id}}`) into the categories' subcategories; `title` names it.

    With several `workers` and the archive's `database` (committed: each worker reads it itself),
    the pages are shared out among worker processes once there are `parallel_from` of them; if
    one fails, they are all written here instead. `progress(done, total)` follows the pages.

    Pages written by an earlier call and no longer wanted are deleted. The list of what was
    written is kept in `pages_list` (default: `.chattr-pages` in `out_root`). Given a `pages_list`,
    what each page was drawn from is kept beside it, and a page drawn from the same data and
    templates as last time (its file untouched since) is not written again.
    """
    started = time.monotonic()
    site = _Site(renderer, Path(out_root), attachment_roots)
    site.summaries = dict(summaries or {})
    record = Path(pages_list) if pages_list else site.out_root / PAGES_LIST
    # A page drawn from the same as last time is left as it is. (Only with a list kept apart from
    # the pages, as Caixa keeps it: never a file of its own among them.)
    site.known = _known(record) if pages_list else {}
    total = len(renderer.pages)
    shared = False
    if workers > 1 and database is not None and total and total >= parallel_from:
        try:
            _draw_in_workers(renderer, site, database, workers, progress)
            shared = True
        except Exception as error:  # (a worker that could not start, or fell over)
            print(f"Writing the pages with {workers} workers failed ({error}); writing them here.")
            site.drawn = {}
    written = []
    if shared:
        written = [site.out_root / spec.path for spec in renderer.pages]
    else:
        relations = _Relations(renderer)
        for number, spec in enumerate(renderer.pages, 1):
            written.append(_draw(site, relations, spec))
            if progress and (number % 25 == 0 or number == total):
                progress(number, total)
    index = site.out_root / "index.html"
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(_index(site, categories, title, subcategories, links), encoding="utf-8")
    written.append(index)
    _forget_old_pages(site.out_root, record, written)
    if pages_list:
        _keep_known(record, site.drawn)
    if stats is not None:  # (what was done, for whoever reports it)
        rewritten = sum(1 for page, was in site.drawn.items() if site.known.get(page) != was)
        stats.update(pages=total, written=rewritten if site.known else total,
                     unchanged=total - (rewritten if site.known else total),
                     workers=workers if shared else 1, seconds=time.monotonic() - started)  # fmt: skip
    return written
