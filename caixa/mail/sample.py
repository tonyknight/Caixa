"""`caixa mail sample`: a few conversations of an mbox drawn each way a body can be drawn
(`caixa.mail.render`), as pages of cards, for the owner to choose how mail looks in the box.

The folder it writes holds `plain/`, `tidied/` and `original/` (one page per conversation in each),
`files/` (the files the mails carry, pictures sent inside them included) and `index.html`, which lists
the conversations with a link to each way. Nothing is fetched from the internet.
"""

from __future__ import annotations

import base64
import email
import email.policy
import html
import re
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Optional

from chattr.parsers.mbox_parser import html_to_text

from caixa.mail import render
from caixa.mail.index import MailIndex

STYLES = ("plain", "tidied", "original")
LABELS = {
    "plain": "Plain text",
    "tidied": "Tidied HTML",
    "original": "The mail's own HTML, made safe",
}

PAGE_STYLE = """
:root { --bg:#eceff4; --card:#ffffff; --fg:#2e3440; --muted:#4c566a; --line:#d8dee9; --accent:#5e81ac; }
@media (prefers-color-scheme: dark) { :root { --bg:#2e3440; --card:#3b4252; --fg:#eceff4; --muted:#a7b1c2;
  --line:#434c5e; --accent:#88c0d0; } }
* { box-sizing: border-box; }
body { margin:0; padding:2rem 1rem 3rem; background:var(--bg); color:var(--fg);
  font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:52rem; margin:0 auto; }
.kind { color:var(--muted); font-size:.85rem; margin:0 0 1.6rem; }
.card { position:relative; background:var(--card); border:1px solid var(--line); border-top:3px solid var(--accent);
  border-radius:.7rem; padding:1.4rem 1.2rem 1rem; margin:2rem 0 1.4rem; box-shadow:0 1px 3px rgba(46,52,64,.12); }
.subject { position:absolute; top:-.85rem; left:1rem; margin:0; max-width:calc(100% - 2rem); padding:.05rem .7rem;
  font-size:.95rem; background:var(--accent); color:var(--bg); border-radius:999px; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis; }
.who { display:grid; grid-template-columns:auto 1fr; gap:.05rem .8rem; margin:0 0 .9rem; font-size:.86rem; }
.who dt { color:var(--muted); } .who dd { margin:0; overflow-wrap:anywhere; }
.body { border-top:1px solid var(--line); padding-top:.8rem; overflow-wrap:anywhere; }
.text { white-space:pre-wrap; }
.body img { max-width:100%; height:auto; }
.mailframe { width:100%; border:0; resize:vertical; overflow:auto; background:#fff; }
details.quoted { margin-top:.8rem; color:var(--muted); } details.quoted summary { cursor:pointer; font-size:.85rem; }
.files { margin:.8rem 0 0; padding-left:1.2rem; font-size:.88rem; }
details.headers { margin-top:.8rem; font-size:.8rem; color:var(--muted); }
details.headers summary { cursor:pointer; }
details.headers pre { white-space:pre-wrap; overflow-wrap:anywhere; }
table.list { width:100%; border-collapse:collapse; background:var(--card); border:1px solid var(--line); }
table.list td, table.list th { padding:.45rem .7rem; border-bottom:1px solid var(--line); text-align:left; }
"""


@dataclass(frozen=True)
class SampleResult:
    folder: Path
    conversations: int


def _safe_name(text: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", text).strip().rstrip(".")
    return (cleaned or "mail")[:80]


def _people(message: EmailMessage, header: str) -> list[tuple[str, str]]:
    try:
        values = [str(v) for v in message.get_all(header, [])]
    except (LookupError, UnicodeError, ValueError, IndexError, TypeError):
        return []
    return [(n, a) for n, a in getaddresses(values) if a]


def _who(people: list[tuple[str, str]]) -> str:
    return ", ".join(html.escape(f"{n} <{a}>" if n else a) for n, a in people)


def _body(message: EmailMessage, kind: str) -> Optional[str]:
    try:
        part = message.get_body(preferencelist=(kind,))
        return str(part.get_content()) if part is not None else None
    except (LookupError, UnicodeError, ValueError, KeyError, IndexError):
        return None


def _inline(message: EmailMessage) -> dict[str, str]:
    """Content-ID → a `data:` address, for the pictures sent inside a mail (the original's frame
    cannot load files)."""
    found: dict[str, str] = {}
    for part in message.walk():
        content_id = str(part.get("Content-ID", "") or "").strip("<> ")
        kind = part.get_content_type()
        if content_id and kind in ("image/png", "image/jpeg", "image/gif", "image/webp"):
            data = part.get_payload(decode=True)
            if isinstance(data, bytes) and data:
                found[content_id] = f"data:{kind};base64,{base64.b64encode(data).decode()}"
    return found


def _files(message: EmailMessage, folder: Path) -> tuple[dict[str, str], list[str]]:
    """Write the files a mail carries into `folder`; (Content-ID → path from a style folder, names)."""
    images: dict[str, str] = {}
    names: list[str] = []
    for number, part in enumerate(message.walk()):
        if part.is_multipart() or part.get_content_maintype() == "text" and not part.get_filename():
            continue
        name = part.get_filename()
        content_id = str(part.get("Content-ID", "") or "").strip("<> ")
        if not name and not content_id:
            continue
        data = part.get_payload(decode=True)
        if not isinstance(data, bytes) or not data:
            continue
        name = _safe_name(name or f"part-{number}")
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        if target.exists() and target.read_bytes() != data:
            target = folder / f"{target.stem} ({number}){target.suffix}"
        target.write_bytes(data)
        relative = f"../files/{folder.name}/{target.name}"
        if content_id:
            images[content_id] = relative
        names.append(target.name)
    return images, names


def _card(
    message: EmailMessage, raw: bytes, style: str, images: dict[str, str], files: list[str]
) -> str:
    subject = str(message.get("Subject", "") or "") or "(no subject)"
    plain = _body(message, "plain")
    rich = _body(message, "html")
    text = plain if plain is not None else html_to_text(rich or "")
    if style == "plain" or not rich:
        body = render.plain(text)
    elif style == "tidied":
        body = render.tidied(rich, images)
    else:
        body = render.original(rich, _inline(message))
    try:
        when = parsedate_to_datetime(str(message.get("Date"))).strftime("%Y-%m-%d %H:%M %z")
    except (TypeError, ValueError, IndexError):
        when = str(message.get("Date", "") or "")
    rows = [("Date", html.escape(when)), ("From", _who(_people(message, "From")))]
    for header in ("To", "Cc"):
        people = _people(message, header)
        if people:
            rows.append((header, _who(people)))
    head = raw.partition(b"\n\n")[0].decode("utf-8", "replace")
    listed = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    attached = "".join(f"<li>{html.escape(n)}</li>" for n in files)
    return (
        f'<article class="card"><h2 class="subject" title="{html.escape(subject)}">'
        f"{html.escape(subject)}</h2>"
        f'<dl class="who">{listed}</dl><div class="body">{body}</div>'
        + (f'<ul class="files">{attached}</ul>' if attached else "")
        + '<details class="headers"><summary>All headers</summary>'
        f"<pre>{html.escape(head)}</pre></details></article>"
    )


def _page(title: str, style: str, cards: list[str]) -> str:
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{PAGE_STYLE}</style></head><body><main>"
        f'<p class="kind">{html.escape(LABELS[style])} · <a href="../index.html">all samples</a></p>'
        + "".join(cards)
        + "</main></body></html>"
    )


def sample(index: MailIndex, source_id: int, out: Path, conversations: int = 6) -> SampleResult:
    """Draw the conversations with the most mails (those with HTML first) three ways into `out`."""
    db = index.connection
    candidates = [
        str(r[0])
        for r in db.execute(
            "SELECT thread_key FROM mails WHERE source_id = ? GROUP BY thread_key "
            "ORDER BY COUNT(*) DESC, MIN(date_utc) LIMIT ?",
            (source_id, conversations * 4),
        )
    ]
    threads: list[tuple[bool, str, list[tuple[EmailMessage, bytes]]]] = []
    for key in candidates:
        mails = []
        for (position,) in db.execute(
            "SELECT position FROM mails WHERE source_id = ? AND thread_key = ? ORDER BY date_utc",
            (source_id, key),
        ):
            raw = index.mail_bytes(source_id, int(position)).partition(b"\n")[2]
            message = email.message_from_bytes(raw, policy=email.policy.default)
            assert isinstance(message, EmailMessage)
            mails.append((message, raw))
        has_html = any(_body(m, "html") for m, _ in mails)
        threads.append((has_html, key, mails))
    chosen = sorted(threads, key=lambda t: (not t[0], -len(t[2])))[:conversations]
    rows = []
    for number, (_, _, mails) in enumerate(chosen, start=1):
        first = mails[0][0]
        subject = str(first.get("Subject", "") or "") or "(no subject)"
        try:
            day = parsedate_to_datetime(str(first.get("Date"))).date().isoformat()
        except (TypeError, ValueError, IndexError):
            day = "undated"
        name = _safe_name(f"({day}) {subject}") + ".html"
        attached = [_files(m, out / "files" / f"{number:02d}") for m, _ in mails]
        for style in STYLES:
            cards = [
                _card(m, raw, style, images, names)
                for (m, raw), (images, names) in zip(mails, attached)
            ]
            (out / style).mkdir(parents=True, exist_ok=True)
            (out / style / name).write_text(_page(subject, style, cards), encoding="utf-8")
        links = "".join(
            f'<td><a href="{style}/{html.escape(name)}">{LABELS[style]}</a></td>'
            for style in STYLES
        )
        rows.append(f"<tr><td>{html.escape(name[:-5])} ({len(mails)})</td>{links}</tr>")
    front = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>How mail looks</title>'
        f"<style>{PAGE_STYLE}</style></head><body><main><h1>How mail looks</h1>"
        "<p>Each conversation drawn three ways. Open them side by side and choose one for the box.</p>"
        f'<table class="list"><tr><th>Conversation (mails)</th>'
        + "".join(f"<th>{LABELS[s]}</th>" for s in STYLES)
        + "</tr>"
        + "".join(rows)
        + "</table></main></body></html>"
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(front, encoding="utf-8")
    return SampleResult(out, len(chosen))
