"""Caixa's own web server: the collection and authoring window, on this computer only.

`caixa serve` runs this. It is plain Python (the standard library's HTTP server, one thread per
request) and calls the service layer in-process, so running Caixa needs neither Node.js nor DeepSeek
Harness. It serves:

- `GET  /sign-in?ticket=…`   the link `caixa serve` prints and opens: sets the session cookie, then
                              goes to `/`. Nothing else answers without that cookie;
- `GET  /`, `/app/…`         Caixa's window (built from `web/src` into `caixa/data/web`);
- `GET  /mail/clean|sort`    the same page, showing the Clean mail or Sort mail window;
- `POST /api/caixa/rpc`      `{"method": "box.status", "params": {}}` → `{"ok": true, "result": …}`
                              or `{"ok": false, "error": {"code", "message", "kind", "data"}}`;
- `GET  /api/caixa/events`   the service's notifications as server-sent events;
- `GET  /api/caixa/status`   `{"worker": "running", "shell": true}`;
- `GET|HEAD /box/<path>`     a file of the open box at its own address, so the box's pages and their
                              relative links work unchanged (`.caixa/` and anything outside the box
                              are refused).

Protection: it listens on 127.0.0.1 only; a request must name this computer and port in its Host
header (against DNS rebinding); everything but the sign-in link needs the session cookie (HttpOnly,
SameSite=Strict); a change (POST) must be JSON, and come from this window when it says where from.
Box files are sent under a Content-Security-Policy that admits no scripts but the pages' own (by
their hashes) and `nosniff`; audio and video answer `Range` requests so they can seek.

A later presentation mode (read-only, on a port of its own) is meant to reuse this with the
service opened read-only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import mimetypes
import queue
import re
import secrets
import threading
import traceback
import sys
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, quote, unquote, urlsplit

from caixa.service import Service, ServiceError
from caixa.worker import INTERNAL, INVALID_PARAMS, REFUSED, UNKNOWN_METHOD, Worker

#: Caixa's window, as built by `web/scripts/build-app.mjs`.
APP = Path(__file__).resolve().parent / "data" / "web"
APP_FILES = {"app.js": "text/javascript", "app.css": "text/css"}
COOKIE = "caixa_session"
#: The mail windows (Clean mail, Sort mail): Caixa's page at their own addresses, opened in a window
#: of their own; the page picks what to show by its address.
MAIL_WINDOWS = ("/mail/clean", "/mail/sort")
METHOD_NAME = re.compile(r"^[a-z][a-z.]*[a-zA-Z]$")
MAX_REQUEST = 10_000_000
HEARTBEAT = 15.0
CHUNK = 1 << 20
#: Files shown in the browser; anything else is offered as a download.
INLINE = re.compile(
    r"^(text/html|text/plain|application/pdf|image/(png|jpeg|gif|webp|bmp|avif)|audio/[\w.+-]+|"
    r"video/[\w.+-]+)$"
)
#: A PDF is not one of the box's pages: it is drawn by the browser's own viewer, which a page's
#: policy (no plugins, no scripts but the pages') would stop. It may be shown only by the box's own
#: pages (in the document overlay) and on its own.
PDF_CSP = "frame-ancestors 'self'"

APP_CSP = "; ".join(
    [
        "default-src 'none'", "script-src 'self'", "style-src 'self'", "img-src 'self' data:",
        "connect-src 'self'", "frame-src 'self'", "font-src 'self'", "base-uri 'none'",
        "form-action 'none'", "frame-ancestors 'none'",
    ]
)  # fmt: skip


#: The scripts the box's pages carry inline (Chattr's templates), and how each begins: its first
#: words have not changed between versions, so a page drawn with an older one is recognised.
PAGE_SCRIPTS = (
    ("lightbox.js", b"/* Pictures, full size", "chattr"),
    ("index.js", b"/* The box's index:", "chattr"),
    ("conversation.js", b"/* Conversations, over the page", "chattr"),
    ("document.js", b"/* Documents, over the page", "caixa"),
    ("documents-index.js", b"/* The documents' index", "caixa"),
    ("document-edit.js", b"/* Documents, corrected by their owner", "caixa"),
)
#: The scripts sit at the end of a page; only this much of its end is looked at.
SCRIPT_TAIL = 512 * 1024


def page_scripts() -> list[tuple[bytes, bytes]]:
    """(how it begins, its current text) for each page script, as the pages hold it: as Jinja
    includes it, without its last newline."""
    import chattr

    folders = {
        "chattr": Path(chattr.__file__).resolve().parent / "templates",
        "caixa": Path(__file__).resolve().parent / "documents" / "templates",
    }
    found = []
    for name, start, where in PAGE_SCRIPTS:
        text = (folders[where] / name).read_bytes()
        found.append((start, text[:-1] if text.endswith(b"\n") else text))
    return found


def page_script_hashes() -> list[str]:
    """The SHA-256 of each script the box's pages carry (Chattr's lightbox, index and conversation
    scripts, Caixa's document overlay), in the form a Content-Security-Policy takes."""
    return [
        "sha256-" + base64.b64encode(hashlib.sha256(text).digest()).decode()
        for _, text in page_scripts()
    ]


def current_scripts(tail: bytes, scripts: list[tuple[bytes, bytes]]) -> bytes:
    """The end of a page with each of Caixa's scripts in it replaced by its current text.

    Pages are drawn at import, and Caixa's scripts change with Caixa: a page drawn with an older
    script would be refused by the policy (it lists only the current scripts' hashes), and its
    categories, sorting and pictures would stop working until the pages were drawn again. Only a
    `<script>` whose text begins as one of Caixa's does is replaced; a message's own text cannot
    hold one, since everything a message says is escaped."""

    def swap(match: "re.Match[bytes]") -> bytes:
        body = match.group(1)
        for start, text in scripts:
            if body.startswith(start):
                return b"<script>" + text + b"</script>"
        return match.group(0)

    return re.sub(rb"<script>(.*?)</script>", swap, tail, flags=re.S)


def box_csp() -> str:
    scripts = " ".join(f"'{h}'" for h in page_script_hashes())
    return "; ".join(
        [
            "default-src 'none'", f"script-src {scripts}", "connect-src 'self'",
            "img-src 'self' data:", "media-src 'self'", "frame-src 'self'",
            "style-src 'unsafe-inline'",
            "font-src 'self'", "frame-ancestors 'self'", "base-uri 'none'", "form-action 'none'",
        ]
    )  # fmt: skip


def parse_range(header: str, size: int) -> Any:
    """`Range: bytes=…` for a file of `size` bytes: (start, end) inclusive, "unsatisfiable", or
    None when the header cannot be used (the whole file is sent)."""
    found = re.match(r"^bytes=(\d*)-(\d*)$", header.strip())
    if not found or (found[1] == "" and found[2] == ""):
        return None
    if found[1] == "":
        start, end = max(0, size - int(found[2])), size - 1
    else:
        start = int(found[1])
        end = size - 1 if found[2] == "" else min(int(found[2]), size - 1)
    if size == 0 or start >= size or start > end:
        return "unsatisfiable"
    return start, end


class _Notifications(Worker):
    """The worker's notifications (job progress, jobs finished, the inbox changing), sent to every
    open event stream instead of to standard output."""

    def __init__(self, service: Service, server: "CaixaServer", inbox_poll: float) -> None:
        self.server = server
        super().__init__(service, io.StringIO(), inbox_poll=inbox_poll)

    def _send(self, message: dict[str, Any]) -> None:
        if "method" in message and "id" not in message:
            self.server.broadcast(str(message["method"]), message.get("params"))

    def answer(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        """One call, in the form the window reads."""
        try:
            return {"ok": True, "result": self._dispatch(name, params)}
        except ServiceError as error:
            code = {"unknown_method": UNKNOWN_METHOD, "invalid_params": INVALID_PARAMS}.get(
                error.kind, REFUSED
            )
            data = {"kind": error.kind, **error.data}
            return {
                "ok": False,
                "error": {"code": code, "message": str(error), "kind": error.kind, "data": data},
            }
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            return {
                "ok": False,
                "error": {"code": INTERNAL, "message": f"Internal error: {error}",
                          "kind": "internal", "data": {"kind": "internal"}},
            }  # fmt: skip


class CaixaServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        """A browser closing a connection (an idle one, a page left mid-load) is not an error:
        nothing is printed for it. Anything else is reported as `socketserver` does."""
        if isinstance(
            sys.exc_info()[1],
            (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError),
        ):
            return
        super().handle_error(request, client_address)

    def __init__(self, service: Service, port: int = 0, inbox_poll: float = 2.0) -> None:
        super().__init__(("127.0.0.1", port), _Handler)
        self.service = service
        self.port = int(self.server_address[1])
        self.secret = secrets.token_urlsafe(32)  # the session cookie's value
        self.ticket = secrets.token_urlsafe(24)  # the sign-in link's
        self.box_policy = box_csp()
        self._streams: list["queue.Queue[Optional[str]]"] = []
        self._streams_lock = threading.Lock()
        self.notifications = _Notifications(service, self, inbox_poll)
        self._watcher = threading.Thread(
            target=self.notifications._watch_inbox, name="caixa-inbox", daemon=True
        )

    @property
    def link(self) -> str:
        """The sign-in link: it carries the ticket, so it is shown to the owner and nobody else."""
        return f"http://127.0.0.1:{self.port}/sign-in?ticket={self.ticket}"

    def start(self) -> threading.Thread:
        self._watcher.start()
        thread = threading.Thread(target=self.serve_forever, name="caixa-web", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self.notifications._stop.set()
        with self._streams_lock:
            for stream in self._streams:
                stream.put(None)
        self.shutdown()
        self.server_close()

    # --- Event streams ----------------------------------------------------------------------

    def broadcast(self, name: str, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
        text = f"event: {name}\ndata: {data}\n\n"
        with self._streams_lock:
            for stream in self._streams:
                stream.put(text)

    def listen(self) -> "queue.Queue[Optional[str]]":
        stream: "queue.Queue[Optional[str]]" = queue.Queue()
        with self._streams_lock:
            self._streams.append(stream)
        return stream

    def forget(self, stream: "queue.Queue[Optional[str]]") -> None:
        with self._streams_lock:
            if stream in self._streams:
                self._streams.remove(stream)


class _Handler(BaseHTTPRequestHandler):
    server: CaixaServer
    protocol_version = "HTTP/1.1"
    server_version = "Caixa"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (the base class's name)
        return  # requests are not logged: their addresses name people's pages

    # --- Answers ----------------------------------------------------------------------------

    def _headers(
        self, status: int, kind: str, length: Optional[int], extra: dict[str, str]
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in extra.items():
            self.send_header(name, value)
        self.end_headers()

    def _send(
        self, status: int, body: bytes, kind: str, extra: Optional[dict[str, str]] = None
    ) -> None:
        self._headers(status, kind, len(body), extra or {})
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, body: Any, status: int = 200) -> None:
        data = json.dumps(body, ensure_ascii=False, default=str, separators=(",", ":")).encode(
            "utf-8"
        )
        self._send(status, data, "application/json; charset=utf-8")

    def _text(self, status: int, text: str) -> None:
        self._send(status, text.encode("utf-8"), "text/plain; charset=utf-8",
                   {"Content-Security-Policy": "default-src 'none'"})  # fmt: skip

    def _page(self, status: int, title: str, text: str) -> None:
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Caixa</title>"
            "<style>body{font:16px/1.5 system-ui,sans-serif;background:#eceff4;color:#2e3440;"
            "max-width:36rem;margin:4rem auto;padding:0 1rem}h1{font-size:1.4rem}</style></head>"
            f"<body><h1>{title}</h1><p>{text}</p></body></html>"
        )
        self._send(status, html.encode("utf-8"), "text/html; charset=utf-8",
                   {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})  # fmt: skip

    # --- Who is asking ----------------------------------------------------------------------

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").lower()
        return host in {f"127.0.0.1:{self.server.port}", f"localhost:{self.server.port}"}

    def _signed_in(self) -> bool:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie") or "")
        except Exception:
            return False
        given = cookie.get(COOKIE)
        return given is not None and hmac.compare_digest(given.value, self.server.secret)

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True  # not a browser's cross-site request (those always say where from)
        return origin.lower() in {
            f"http://127.0.0.1:{self.server.port}",
            f"http://localhost:{self.server.port}",
        }

    def _admitted(self) -> bool:
        if not self._host_ok():
            self._text(HTTPStatus.MISDIRECTED_REQUEST, "This address is not Caixa's.")
            return False
        if not self._signed_in():
            self._page(
                HTTPStatus.UNAUTHORIZED,
                "Open Caixa from its link",
                "This window is not signed in. Use the link <code>caixa serve</code> printed in "
                "the terminal (run <code>caixa serve</code> again to open it).",
            )
            return False
        return True

    # --- GET, HEAD, POST --------------------------------------------------------------------

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/sign-in":
            return self._sign_in(url.query)
        if not self._admitted():
            return
        if url.path in ("/", "/index.html") or url.path in MAIL_WINDOWS:
            body = (APP / "index.html").read_bytes()
            return self._send(200, body, "text/html; charset=utf-8",
                              {"Content-Security-Policy": APP_CSP})  # fmt: skip
        if url.path.startswith("/app/") and url.path[5:] in APP_FILES:
            name = url.path[5:]
            kind = APP_FILES[name] + "; charset=utf-8"
            return self._send(200, (APP / name).read_bytes(), kind,
                              {"Content-Security-Policy": APP_CSP})  # fmt: skip
        if url.path == "/api/caixa/status":
            return self._json({"worker": "running", "shell": True})
        if url.path == "/api/caixa/events":
            return self._events()
        if url.path == "/box" or url.path.startswith("/box/"):
            return self._box_file(unquote(url.path[5:]) or "index.html")
        self._text(404, "Not found.")

    def do_POST(self) -> None:
        url = urlsplit(self.path)
        # The body is read first, whatever the answer: a refusal that left it unread would spoil
        # the next request on the same connection. One too large closes the connection instead.
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = -1
        if length < 0 or length > MAX_REQUEST:
            self.close_connection = True
            return self._fail(400, -32600, "invalid_request", "The request is too large.")
        raw = self.rfile.read(length) if length else b""
        if not self._admitted():
            return
        if url.path != "/api/caixa/rpc":
            return self._text(404, "Not found.")
        if not self._origin_ok():
            return self._text(403, "A change must come from Caixa's own window.")
        if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            return self._fail(400, -32600, "invalid_request", "A request must be JSON.")
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            return self._fail(400, -32700, "invalid_request", "The request was not valid JSON.")
        method = body.get("method") if isinstance(body, dict) else None
        params = body.get("params", {}) if isinstance(body, dict) else None
        if not isinstance(method, str) or not METHOD_NAME.match(method):
            return self._fail(400, -32600, "invalid_request",
                              'A request needs a method name such as "box.status".')  # fmt: skip
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return self._fail(400, -32602, "invalid_params", "Parameters must be an object.")
        self._json(self.server.notifications.answer(method, params))

    def _fail(self, status: int, code: int, kind: str, message: str) -> None:
        self._json(
            {"ok": False, "error": {"code": code, "message": message, "kind": kind,
                                    "data": {"kind": kind}}},
            status,
        )  # fmt: skip

    # --- Signing in -------------------------------------------------------------------------

    def _sign_in(self, query: str) -> None:
        if not self._host_ok():
            return self._text(HTTPStatus.MISDIRECTED_REQUEST, "This address is not Caixa's.")
        given = parse_qs(query).get("ticket", [""])[0]
        if not given or not hmac.compare_digest(given, self.server.ticket):
            return self._page(
                403,
                "This link does not open Caixa",
                "It may be from an earlier run. Run <code>caixa serve</code> again to get a new one.",
            )
        cookie = f"{COOKIE}={self.server.secret}; Path=/; HttpOnly; SameSite=Strict"
        self._send(303, b"", "text/plain", {"Location": "/", "Set-Cookie": cookie})

    # --- Event stream -----------------------------------------------------------------------

    def _events(self) -> None:
        stream = self.server.listen()
        try:
            self._headers(200, "text/event-stream; charset=utf-8", None,
                          {"Connection": "keep-alive", "X-Accel-Buffering": "no"})  # fmt: skip
            self.wfile.write(b'event: worker.state\ndata: {"state":"running"}\n\n')
            self.wfile.flush()
            while True:
                try:
                    text = stream.get(timeout=HEARTBEAT)
                except queue.Empty:
                    text = ": keep-alive\n\n"
                if text is None:
                    break
                self.wfile.write(text.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.server.forget(stream)
            self.close_connection = True

    # --- The box's files --------------------------------------------------------------------

    def _box_file(self, path: str) -> None:
        if "\0" in path:
            return self._text(400, "That is not a file of the box.")
        try:
            info = self.server.service.call("browse.file", {"path": path})
        except ServiceError as error:
            status = {"not_found": 404, "outside_roots": 403, "no_box": 404}.get(error.kind, 400)
            return self._text(status, str(error))
        file = Path(info["absolute"])
        mime = str(
            info.get("mime") or mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        )
        size = int(info["size"])
        policy = PDF_CSP if mime == "application/pdf" else self.server.box_policy
        extra = {"Content-Security-Policy": policy, "Accept-Ranges": "bytes"}
        if not INLINE.match(mime):
            extra["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(
                str(info["name"])
            )
        kind = f"{mime}; charset=utf-8" if mime.startswith("text/") else mime
        if mime == "text/html":
            return self._box_page(file, size, kind, extra)
        wanted = self.headers.get("Range")
        chosen = parse_range(wanted, size) if wanted else None
        if chosen == "unsatisfiable":
            return self._send(416, b"", kind, {**extra, "Content-Range": f"bytes */{size}"})
        start, end = chosen if chosen else (0, max(0, size - 1))
        length = 0 if size == 0 else end - start + 1
        if chosen:
            extra["Content-Range"] = f"bytes {start}-{end}/{size}"
        self._headers(206 if chosen else 200, kind, length, extra)
        if self.command == "HEAD" or length == 0:
            return
        try:
            with open(file, "rb") as handle:
                handle.seek(start)
                left = length
                while left > 0:
                    piece = handle.read(min(CHUNK, left))
                    if not piece:
                        break
                    self.wfile.write(piece)
                    left -= len(piece)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _box_page(self, file: Path, size: int, kind: str, extra: dict[str, str]) -> None:
        """A page of the box, whole (no ranges), with its scripts brought up to date (see
        `current_scripts`). Only its end is read into memory: the rest is sent as it is."""
        extra = {**extra, "Accept-Ranges": "none"}
        cut = max(0, size - SCRIPT_TAIL)
        with open(file, "rb") as handle:
            handle.seek(cut)
            tail = handle.read()
            start = tail.find(b"<")  # never begin in the middle of a tag
            if cut and start > 0:
                cut, tail = cut + start, tail[start:]
            tail = current_scripts(tail, page_scripts())
            self._headers(200, kind, cut + len(tail), extra)
            if self.command == "HEAD":
                return
            try:
                handle.seek(0)
                left = cut
                while left > 0:
                    piece = handle.read(min(CHUNK, left))
                    if not piece:
                        break
                    self.wfile.write(piece)
                    left -= len(piece)
                self.wfile.write(tail)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
