"""Caixa's own web server (`caixa.web`): signing in, the window, calls, events and box files."""

from __future__ import annotations

import http.client
import json
import threading
import time
from pathlib import Path
from typing import Any, Iterator, Optional

import pytest
from fixtures import family

from caixa import web
from caixa.service import Service


class Browser:
    """A plain HTTP client that keeps the session cookie, like a browser tab."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.cookie = ""

    def ask(
        self,
        method: str,
        path: str,
        body: Optional[bytes] = None,
        headers: Optional[dict[str, str]] = None,
        cookie: bool = True,
    ) -> tuple[int, dict[str, str], bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        sent = {"Host": f"127.0.0.1:{self.port}", **(headers or {})}
        if cookie and self.cookie:
            sent["Cookie"] = self.cookie
        connection.request(method, path, body=body, headers=sent)
        reply = connection.getresponse()
        data = reply.read()
        found = {k.lower(): v for k, v in reply.getheaders()}
        connection.close()
        return reply.status, found, data

    def sign_in(self, ticket: str) -> None:
        status, headers, _ = self.ask("GET", f"/sign-in?ticket={ticket}", cookie=False)
        assert status == 303 and headers["location"] == "/"
        self.cookie = headers["set-cookie"].split(";")[0]

    def rpc(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        body = json.dumps({"method": method, "params": params or {}}).encode()
        status, _, data = self.ask(
            "POST", "/api/caixa/rpc", body, {"Content-Type": "application/json"}
        )
        assert status == 200, data
        return dict(json.loads(data))


@pytest.fixture
def running(tmp_path: Path) -> Iterator[tuple[web.CaixaServer, Browser, Service]]:
    service = Service(roots=[tmp_path])
    service.box_create(str(tmp_path / "Box"), name="Web box", owner=family.OWNER.name)
    server = web.CaixaServer(service, 0, inbox_poll=0.2)
    server.start()
    browser = Browser(server.port)
    browser.sign_in(server.ticket)
    yield server, browser, service
    server.stop()
    service.close()


def test_it_listens_on_this_computer_only_and_the_link_carries_a_ticket(running) -> None:
    server, _, _ = running
    assert server.server_address[0] == "127.0.0.1"
    assert server.link.startswith(f"http://127.0.0.1:{server.port}/sign-in?ticket=")


def test_nothing_answers_without_signing_in(running) -> None:
    server, browser, _ = running
    for path in ("/", "/app/app.js", "/api/caixa/status", "/box/index.html"):
        status, _, page = browser.ask("GET", path, cookie=False)
        assert status == 401, path
        assert b"caixa serve" in page
    status, _, _ = browser.ask("POST", "/api/caixa/rpc", b"{}", {"Content-Type": "application/json"}, cookie=False)  # fmt: skip
    assert status == 401
    status, _, _ = browser.ask("GET", "/sign-in?ticket=wrong", cookie=False)
    assert status == 403
    status, _, _ = browser.ask("GET", "/", headers={"Cookie": "caixa_session=guess"}, cookie=False)
    assert status == 401


def test_the_session_cookie_is_http_only_and_same_site(running) -> None:
    server, browser, _ = running
    _, headers, _ = browser.ask("GET", f"/sign-in?ticket={server.ticket}", cookie=False)
    cookie = headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/" in cookie


def test_another_host_name_is_refused_even_signed_in(running) -> None:
    _, browser, _ = running
    status, _, _ = browser.ask("GET", "/", headers={"Host": "evil.example:80"})
    assert status == 421


def test_the_window_is_caixas_own_with_no_deepseek_and_a_strict_policy(running) -> None:
    _, browser, _ = running
    status, headers, page = browser.ask("GET", "/")
    assert status == 200 and b"<title>Caixa</title>" in page
    assert b"DeepSeek" not in page and b"dsh" not in page.lower()
    policy = headers["content-security-policy"]
    assert "script-src 'self'" in policy and "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy
    status, headers, script = browser.ask("GET", "/app/app.js")
    assert status == 200 and headers["content-type"].startswith("text/javascript")
    assert b"__ModuleLoader__" not in script and b"@deepseek-ai" not in script
    status, headers, _ = browser.ask("GET", "/app/app.css")
    assert status == 200 and headers["content-type"].startswith("text/css")
    assert browser.ask("GET", "/app/../web.py")[0] == 404


def test_the_mail_windows_are_caixas_page_at_their_own_address(running) -> None:
    _, browser, _ = running
    for address in ("/mail/clean", "/mail/sort"):
        status, headers, page = browser.ask("GET", address)
        assert status == 200 and b'<script src="/app/app.js"></script>' in page, address
        assert "script-src 'self'" in headers["content-security-policy"]
    assert browser.ask("GET", "/mail/other")[0] == 404


def test_calls_answer_as_the_window_expects(running) -> None:
    _, browser, _ = running
    assert browser.rpc("box.status")["result"]["name"] == "Web box"
    refused = browser.rpc("people.rename", {"person": 999, "name": "X"})
    assert refused["ok"] is False and refused["error"]["kind"] == "not_found"
    assert refused["error"]["data"]["kind"] == "not_found"
    unknown = browser.rpc("no.such")
    assert unknown["error"]["kind"] == "unknown_method"
    info = browser.rpc("worker.info")["result"]
    assert "people.delete" in info["methods"]


def test_a_change_must_be_json_from_this_window(running) -> None:
    server, browser, _ = running
    form = browser.ask("POST", "/api/caixa/rpc", b"method=box.reset", {"Content-Type": "application/x-www-form-urlencoded"})  # fmt: skip
    assert form[0] == 400
    elsewhere = browser.ask(
        "POST", "/api/caixa/rpc", b'{"method": "box.status"}',
        {"Content-Type": "application/json", "Origin": "http://evil.example"},
    )  # fmt: skip
    assert elsewhere[0] == 403
    here = browser.ask(
        "POST", "/api/caixa/rpc", b'{"method": "box.status"}',
        {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{server.port}"},
    )  # fmt: skip
    assert here[0] == 200
    assert (
        browser.ask("POST", "/api/caixa/rpc", b"{nope", {"Content-Type": "application/json"})[0]
        == 400
    )


def test_the_status_says_the_window_is_caixas(running) -> None:
    _, browser, _ = running
    status, _, body = browser.ask("GET", "/api/caixa/status")
    assert status == 200 and json.loads(body) == {"worker": "running", "shell": True}


def test_box_files_are_served_at_their_own_address(running, tmp_path: Path) -> None:
    _, browser, _ = running
    box = tmp_path / "Box"
    (box / "People" / "Ana Costa").mkdir(parents=True)
    (box / "People" / "Ana Costa" / "Ana Costa.html").write_text("<p>Olá</p>", encoding="utf-8")
    (box / "People" / "Ana Costa" / "voice.m4a").write_bytes(bytes(range(256)) * 4)
    (box / "notes.bin").write_bytes(b"\0\1")
    status, headers, page = browser.ask("GET", "/box/People/Ana%20Costa/Ana%20Costa.html")
    assert status == 200 and page.decode() == "<p>Olá</p>"
    assert headers["content-type"] == "text/html; charset=utf-8"
    policy = headers["content-security-policy"]
    for script in web.page_script_hashes():
        assert f"'{script}'" in policy
    assert "default-src 'none'" in policy and headers["x-content-type-options"] == "nosniff"
    assert "frame-src 'self'" in policy  # a conversation shown over its person's page
    # seeking in a recording
    status, headers, part = browser.ask("GET", "/box/People/Ana%20Costa/voice.m4a", headers={"Range": "bytes=10-19"})  # fmt: skip
    assert status == 206 and part == bytes(range(10, 20))
    assert headers["content-range"] == "bytes 10-19/1024"
    status, _, _ = browser.ask("GET", "/box/People/Ana%20Costa/voice.m4a", headers={"Range": "bytes=5000-"})  # fmt: skip
    assert status == 416
    status, headers, _ = browser.ask("HEAD", "/box/People/Ana%20Costa/voice.m4a")
    assert status == 200 and headers["content-length"] == "1024"
    # anything else is a download
    _, headers, _ = browser.ask("GET", "/box/notes.bin")
    assert headers["content-disposition"].startswith("attachment;")


def test_the_box_files_never_reach_caixas_own_data_or_outside_the_box(
    running, tmp_path: Path
) -> None:
    _, browser, _ = running
    (tmp_path / "secret.txt").write_text("no", encoding="utf-8")
    for path in ("/box/.caixa/owner.json", "/box/.caixa/caixa.sqlite", "/box/../secret.txt",
                 "/box/%2e%2e/secret.txt", "/box/missing.html"):  # fmt: skip
        status, _, body = browser.ask("GET", path)
        assert status in (403, 404), (path, status)
        assert b"no" != body


def test_page_script_hashes_are_those_of_the_templates_the_pages_carry() -> None:
    """Chattr's tests check that each page carries its template unchanged but for the last newline;
    the policy's hashes are of exactly that text."""
    import base64
    import hashlib

    import chattr

    chattrs = Path(chattr.__file__).resolve().parent / "templates"
    caixas = Path(web.__file__).resolve().parent / "documents" / "templates"
    for (folder, name), listed in zip(
        ((chattrs, "lightbox.js"), (chattrs, "index.js"), (chattrs, "conversation.js"),
         (caixas, "document.js"), (caixas, "documents-index.js")),
        web.page_script_hashes(),
        strict=True,
    ):  # fmt: skip
        text = (folder / name).read_text(encoding="utf-8").removesuffix("\n")
        digest = base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
        assert listed == f"sha256-{digest}"


def test_notifications_reach_an_open_event_stream(running) -> None:
    server, browser, service = running
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=20)
    connection.request("GET", "/api/caixa/events", headers={"Host": f"127.0.0.1:{server.port}", "Cookie": browser.cookie})  # fmt: skip
    reply = connection.getresponse()
    assert reply.status == 200 and reply.getheader("Content-Type").startswith("text/event-stream")
    assert reply.fp.readline().startswith(b"event: worker.state")
    reply.fp.readline()
    reply.fp.readline()
    seen: list[bytes] = []

    def read() -> None:
        for _ in range(4):
            seen.append(reply.fp.readline())

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    time.sleep(0.2)
    server.broadcast("job.finished", {"job": 1, "status": "done"})
    reader.join(5)
    assert b"event: job.finished\n" in seen
    assert any(line.startswith(b"data: ") and b'"status":"done"' in line for line in seen)
    connection.close()


def test_the_built_window_is_up_to_date_with_its_sources() -> None:
    """`web/scripts/build-app.mjs` records the digest of the sources it built from; change the
    interface without rebuilding it and this fails (run `pnpm run build` in web/)."""
    import hashlib

    sources = Path(__file__).resolve().parents[1] / "web"
    if not sources.is_dir():
        pytest.skip("not a checkout")
    digest = hashlib.sha256()

    def walk(folder: Path) -> None:
        for path in sorted(folder.iterdir(), key=lambda p: p.name):
            if path.is_dir():
                walk(path)
            else:
                digest.update(path.relative_to(sources).as_posix().encode())
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")

    walk(sources / "src" / "app")
    walk(sources / "src" / "client")
    built = json.loads((web.APP / "build.json").read_text(encoding="utf-8"))
    assert (
        built["sources"] == digest.hexdigest()
    ), "rebuild Caixa's window: cd web && pnpm run build"


def test_a_page_drawn_with_an_older_script_gets_the_current_one(running, tmp_path: Path) -> None:
    """Pages are drawn at import; Caixa's scripts change with Caixa. An index page drawn with an
    earlier index script (whose hash the policy no longer lists, so the browser would not run it)
    is served with the current one, so its categories, sorting and naming keep working."""
    import base64
    import hashlib
    import re

    import chattr

    _, browser, _ = running
    current = (Path(chattr.__file__).resolve().parent / "templates" / "index.js").read_text(
        encoding="utf-8"
    )
    older = '/* The box\'s index: a category at a time, and sorting people into categories. */\n(function () { var CAIXA = location.pathname === "/api/caixa/box"; })();'
    words = "x" * 600_000  # a long page: the script is near its end
    (tmp_path / "Box" / "index.html").write_text(
        f"<!DOCTYPE html><html><body><p>{words}</p><p>&lt;script&gt;not a script&lt;/script&gt;</p>"
        f"<script>{older}</script></body></html>",
        encoding="utf-8",
    )
    status, headers, page = browser.ask("GET", "/box/index.html")
    assert status == 200
    text = page.decode("utf-8")
    (script,) = re.findall(r"<script>(.*?)</script>", text, re.S)
    assert script == current.removesuffix("\n")
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    assert f"'sha256-{digest}'" in headers["content-security-policy"]
    assert int(headers["content-length"]) == len(page)
    assert words in text and "&lt;script&gt;not a script&lt;/script&gt;" in text
    # a page with no script, or a script that is not one of Caixa's, is sent as it is
    (tmp_path / "Box" / "plain.html").write_text(
        "<p>hi</p><script>alert(1)</script>", encoding="utf-8"
    )
    assert browser.ask("GET", "/box/plain.html")[2] == b"<p>hi</p><script>alert(1)</script>"


def test_a_connection_the_browser_closes_is_not_printed(running, capsys) -> None:
    """A browser closing an idle connection is not an error worth a traceback in the terminal."""
    server, _, _ = running
    for closed in (
        ConnectionResetError(54, "Connection reset by peer"),
        BrokenPipeError(32, "Broken pipe"),
    ):
        try:
            raise closed
        except OSError:
            server.handle_error(None, ("127.0.0.1", 50094))
    assert capsys.readouterr().err == ""
    try:
        raise ValueError("something else went wrong")
    except ValueError:
        server.handle_error(None, ("127.0.0.1", 50094))
    assert "something else went wrong" in capsys.readouterr().err


# --- PDFs (ticket 20261124-15) ---------------------------------------------------------------------


def test_a_pdf_is_shown_by_the_browser(running, tmp_path: Path) -> None:
    _, browser, _ = running
    folder = tmp_path / "Box" / "Documents" / "PDF" / "2024" / "Banco Atlântico"
    folder.mkdir(parents=True)
    pdf = b"%PDF-1.4\n" + bytes(range(256)) * 8
    (folder / "(2024-11-30) Checking Statement - Banco Atlântico.pdf").write_bytes(pdf)
    path = "/box/Documents/PDF/2024/Banco%20Atl%C3%A2ntico/(2024-11-30)%20Checking%20Statement%20-%20Banco%20Atl%C3%A2ntico.pdf"
    status, headers, body = browser.ask("GET", path)
    assert status == 200 and body == pdf
    assert headers["content-type"] == "application/pdf"
    assert "content-disposition" not in headers  # shown, not downloaded
    assert headers["content-security-policy"] == web.PDF_CSP
    assert "frame-ancestors 'self'" in web.PDF_CSP and "script-src" not in web.PDF_CSP
    assert headers["x-content-type-options"] == "nosniff" and headers["accept-ranges"] == "bytes"
    status, headers, part = browser.ask("GET", path, headers={"Range": "bytes=0-7"})
    assert status == 206 and part == b"%PDF-1.4"


def test_the_document_script_begins_as_listed() -> None:
    names = [name for name, *_ in web.PAGE_SCRIPTS]
    assert names[-2:] == ["document.js", "documents-index.js"]
    for name, start, text in zip(
        names, (s for _, s, *_ in web.PAGE_SCRIPTS), (t for _, t in web.page_scripts())
    ):
        assert text.startswith(start), name


def test_a_page_with_an_older_document_script_gets_the_current_one(running, tmp_path: Path) -> None:
    _, browser, _ = running
    box = tmp_path / "Box" / "Documents" / "PDF" / "2024"
    box.mkdir(parents=True, exist_ok=True)
    old = "/* Documents, over the page: an older version */ var x = 1;"
    (box / "Banco.html").write_text(f"<p>cards</p><script>{old}</script>", encoding="utf-8")
    status, headers, page = browser.ask("GET", "/box/Documents/PDF/2024/Banco.html")
    assert status == 200 and old.encode() not in page
    current = dict(web.page_scripts())[b"/* Documents, over the page"]
    assert current in page
