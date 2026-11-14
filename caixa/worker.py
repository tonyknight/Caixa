"""`caixa worker`: the service layer over standard input and output.

The protocol is JSON-RPC 2.0, one JSON object per line (UTF-8):

- a request `{"jsonrpc": "2.0", "id": 1, "method": "box.status", "params": {...}}` gets exactly one
  response, `{"id": 1, "result": ...}` or `{"id": 1, "error": {"code", "message", "data"}}`;
- the worker also sends notifications (no `id`): `job.progress`, `job.finished` and
  `inbox.changed`.

Requests are handled concurrently, so a long preview never blocks cancelling an import. Standard
output carries the protocol and nothing else: anything a collector prints goes to a job log, and
anything else to standard error. Error codes are the JSON-RPC ones (-32700 parse error, -32600
invalid request, -32601 unknown method, -32602 invalid params, -32603 internal) plus -32000 for
"the request was understood but could not be done"; `error.data.kind` says why in a word
(`read_only`, `not_found`, `input`, `conflict`, `no_box`, `outside_roots`, …).

The worker is never exposed to a browser directly; the harness plugin reaches it through its own
authenticated routes.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, TextIO

from caixa import __version__, revision
from caixa.service import Service, ServiceError
from caixa.state import State

#: When this process loaded its code.
STARTED = time.time()

PROTOCOL = 1
PARSE_ERROR, INVALID_REQUEST, UNKNOWN_METHOD, INVALID_PARAMS, INTERNAL = (
    -32700,
    -32600,
    -32601,
    -32602,
    -32603,
)
REFUSED = -32000


class Worker:
    def __init__(self, service: Service, output: TextIO, inbox_poll: float = 2.0) -> None:
        self.service = service
        self.output = output
        self.inbox_poll = inbox_poll
        self._write_lock = threading.Lock()
        self._stop = threading.Event()
        service.subscribe(self._notify)

    # --- Output -----------------------------------------------------------------------------

    def _send(self, message: dict[str, Any]) -> None:
        line = json.dumps({"jsonrpc": "2.0", **message}, ensure_ascii=False, default=str)
        with self._write_lock:
            self.output.write(line + "\n")
            self.output.flush()

    def _notify(self, name: str, payload: dict[str, Any]) -> None:
        self._send({"method": name, "params": payload})

    def _error(self, request_id: Any, code: int, message: str, data: Any = None) -> None:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        self._send({"id": request_id, "error": error})

    # --- Requests ---------------------------------------------------------------------------

    def handle(self, line: str) -> None:
        """Answer one request line (also used by tests, without threads)."""
        try:
            request = json.loads(line)
        except ValueError:
            return self._error(None, PARSE_ERROR, "That was not valid JSON.")
        if not isinstance(request, dict) or not isinstance(request.get("method"), str):
            return self._error(
                request.get("id") if isinstance(request, dict) else None,
                INVALID_REQUEST,
                "A request is a JSON object with a 'method'.",
            )
        request_id, name = request.get("id"), request["method"]
        params = request.get("params", {})
        if not isinstance(params, dict):
            return self._error(request_id, INVALID_PARAMS, "Parameters must be an object.")
        try:
            result = self._dispatch(name, params)
        except ServiceError as error:
            code = {"unknown_method": UNKNOWN_METHOD, "invalid_params": INVALID_PARAMS}.get(
                error.kind, REFUSED
            )
            return self._error(request_id, code, str(error), {"kind": error.kind, **error.data})
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            return self._error(request_id, INTERNAL, f"Internal error: {error}")
        if "id" in request:  # a request without an id is a notification: no answer
            self._send({"id": request_id, "result": result})

    def _dispatch(self, name: str, params: dict[str, Any]) -> Any:
        if name == "worker.info":
            return {
                "version": __version__,
                "protocol": PROTOCOL,
                "read_only": self.service.read_only,
                "methods": sorted([*self.service.METHODS, "worker.info"]),
                # which code this is, and whether the files have changed since it started (a
                # `git pull` without a restart): the interface says so
                "commit": revision.commit(),
                "started": datetime.fromtimestamp(STARTED, timezone.utc).isoformat(),
                "restart_needed": revision.changed_since(STARTED),
            }
        return self.service.call(name, params)

    # --- Watching the inbox -----------------------------------------------------------------

    def _watch_inbox(self) -> None:
        last: Optional[list[tuple[Any, ...]]] = None
        while not self._stop.wait(self.inbox_poll):
            if self.service.box is None:
                last = None
                continue
            try:
                listing = self.service.inbox_list()
            except Exception:
                continue
            seen = [(e["name"], e["size"], e["modified"]) for e in listing["entries"]]
            if last is not None and seen != last:
                self._notify("inbox.changed", listing)
            last = seen

    # --- The loop ---------------------------------------------------------------------------

    def serve(self, lines: TextIO) -> None:
        watcher = threading.Thread(target=self._watch_inbox, name="caixa-inbox", daemon=True)
        watcher.start()
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="caixa-request") as pool:
            for line in lines:
                if line.strip():
                    pool.submit(self.handle, line)
        self._stop.set()
        self.service.close(cancel=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="caixa worker", description="Serve Caixa's service layer as JSON-RPC over stdio."
    )
    parser.add_argument(
        "--box",
        help="open this box at start (default: the one open last time, if it is still there)",
    )
    parser.add_argument(
        "--read-only", action="store_true", help="refuse every method that would change the box"
    )
    parser.add_argument(
        "--root",
        action="append",
        help="a folder the file picker may show (repeatable; default: your home folder)",
    )
    parser.add_argument(
        "--inbox-poll", type=float, default=2.0, help="seconds between looks at the inbox"
    )
    args = parser.parse_args(argv)
    protocol, sys.stdout = sys.stdout, sys.stderr  # stdout belongs to the protocol alone
    service = Service(read_only=args.read_only, roots=args.root, state=State.default())
    worker = Worker(service, protocol, inbox_poll=args.inbox_poll)
    if args.box:
        try:
            service.box_open(args.box)
        except ServiceError as error:
            print(f"caixa worker: {error}", file=sys.stderr)
            return 1
    else:  # nothing asked for: pick up the box that was open last time, if it is still there
        last = service.state.last_box() if service.state else None
        if last:
            try:
                service.box_open(last)
            except ServiceError as error:
                print(f"caixa worker: could not reopen {last}: {error}", file=sys.stderr)
    worker.serve(sys.stdin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
