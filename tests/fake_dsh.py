#!/usr/bin/env python3
"""A stand-in for `dsh` for the launcher's tests.

`fake_dsh plugin --profile web add DIR` records the plugin in the profile, as the real one does.
`fake_dsh --profile web --no-open --host H --port P [--patch F]` prints the link line, serves HTTP
(200 only with the right token), keeps a grandchild process running (its pid goes to $FAKE_PIDFILE),
writes a line containing the link to stderr (so redaction can be checked), and exits on SIGTERM.

$FAKE_MODE: "silent" never prints the link; "early" exits at once; "noready" prints the link but
does not listen.
"""

import http.server
import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

TOKEN = "SECRET-TOKEN-0123456789"
args = sys.argv[1:]

if args[:1] == ["plugin"]:
    home = Path(os.environ["DSH_HOME"]) / "profiles" / "web"
    home.mkdir(parents=True, exist_ok=True)
    (home / "package.json").write_text(
        json.dumps({"dsh": {"profile": {"bundles": ["base", "caixa-dsh-plugin"]}}})
    )
    sys.exit(0)

if "--patch" in args and args.index("--patch") > args.index("--profile"):  # as the real dsh
    print("error: unknown option '--patch'", file=sys.stderr)
    sys.exit(1)

mode = os.environ.get("FAKE_MODE", "")
if mode == "early":
    print(
        "dsh: cannot start: something is wrong " + f"http://127.0.0.1:1/?token={TOKEN}",
        file=sys.stderr,
    )
    sys.exit(7)

port = int(args[args.index("--port") + 1]) if "--port" in args else 0
patch = args[args.index("--patch") + 1] if "--patch" in args else ""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        ok = f"token={TOKEN}" in self.path
        self.send_response(200 if ok else 401)
        self.end_headers()
        self.wfile.write(b"ok" if ok else b"no")

    def log_message(self, *a: object) -> None:
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0 if mode == "noready" else port), Handler)
chosen = server.server_address[1] if mode != "noready" else (port or 54321)
child = subprocess.Popen(["sleep", "300"])
if os.environ.get("FAKE_PIDFILE"):
    Path(os.environ["FAKE_PIDFILE"]).write_text(
        f"{os.getpid()} {child.pid}\n{patch}\n{os.environ.get('DSH_HOME', '')}\n"
    )
link = f"http://127.0.0.1:{chosen}/?token={TOKEN}"
print(f"dsh: harness is up at {link}", file=sys.stderr, flush=True)
print("[caixa] job 1: transcribing 1/2 - 1.amr: 2.0 s", file=sys.stderr, flush=True)
if mode != "silent":
    print(f"dsh web: {link}", flush=True)
signal.signal(signal.SIGTERM, lambda *a: (child.kill(), os._exit(0)))
threading.Thread(target=server.serve_forever, daemon=True).start()
signal.pause() if hasattr(signal, "pause") else None
