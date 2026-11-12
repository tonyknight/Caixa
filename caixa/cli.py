"""Command-line entry point for Caixa.

Every command calls the same `Service` the worker exposes to the browser, so anything the interface
can do can be scripted, and gives the same result. Results go to standard output (`--json` for
programs); progress and errors go to standard error. Exit status: 0 done, 1 could not be done,
2 usage, 130 interrupted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

from caixa import __version__
from caixa.service import Service, ServiceError

ENVIRONMENT = "CAIXA_BOX"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _box_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--box", help=f"the box folder (or set {ENVIRONMENT}, or run inside it)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caixa",
        description="Collect, preserve and pass on a digital life.",
    )
    parser.add_argument("--version", action="version", version=f"caixa {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")

    box = commands.add_parser("box", help="create a box or see what is in one")
    box_commands = box.add_subparsers(dest="action", metavar="action", required=True)
    create = box_commands.add_parser("create", help="make a new box folder")
    create.add_argument("path")
    create.add_argument("--name", default="", help="the box's name (default: the folder's)")
    create.add_argument("--owner", default="", help="whose archive this is (the 'me' in messages)")
    create.add_argument("--json", action="store_true")
    _box_argument(box_commands.add_parser("status", help="counts and recent imports"))

    collectors = commands.add_parser("collectors", help="the sources Caixa can import")
    collectors.add_argument("id", nargs="?", help="show how to export from this source")
    collectors.add_argument("--json", action="store_true")

    run = commands.add_parser("import", help="import an export into a box")
    run.add_argument("collector", help="which source (see 'caixa collectors')")
    run.add_argument("source", help="the export: a file, a folder or a .zip")
    run.add_argument(
        "--option", "-o", action="append", default=[], metavar="NAME=VALUE", help="a source option"
    )
    run.add_argument("--preview", action="store_true", help="count what is in it; import nothing")
    _box_argument(run)

    doctor = commands.add_parser("doctor", help="a report to paste when something does not work")
    doctor.add_argument(
        "--collector", help="check a source: which kind it is (see 'caixa collectors')"
    )
    doctor.add_argument(
        "--source", help="check a source: the file, folder or .zip that will not import"
    )
    doctor.add_argument("--box", help=f"include this box (or set {ENVIRONMENT}, or run inside it)")

    undo = commands.add_parser(
        "undo", help="undo the newest import (the box goes back to how it was before it)"
    )
    undo.add_argument("--yes", action="store_true", help="do it without asking")
    _box_argument(undo)

    again = commands.add_parser("again", help="run an earlier import again (see 'caixa jobs')")
    again.add_argument("job", type=int, help="the number of the import to run again")
    _box_argument(again)

    jobs = commands.add_parser("jobs", help="imports done and running")
    jobs.add_argument("--limit", type=int, default=20)
    _box_argument(jobs)

    people = commands.add_parser("people", help="who is in the box")
    people_commands = people.add_subparsers(dest="action", metavar="action", required=True)
    _box_argument(people_commands.add_parser("list", help="everyone in the box"))
    _box_argument(people_commands.add_parser("unresolved", help="handles no one is named for"))
    link = people_commands.add_parser("link", help="say who a number, address or name is")
    link.add_argument("service")
    link.add_argument("identifier")
    link.add_argument("person", help="a name (made if new) or a person's number from 'list'")
    link.add_argument("--move", action="store_true", help="take it from whoever it names now")
    _box_argument(link)
    rename = people_commands.add_parser("rename", help="change a person's name")
    rename.add_argument("person", type=int)
    rename.add_argument("name")
    _box_argument(rename)
    merge = people_commands.add_parser("merge", help="two names for one person: fold one in")
    merge.add_argument("source", type=int, help="the person who goes away")
    merge.add_argument("target", type=int, help="the person who stays")
    _box_argument(merge)

    serve = commands.add_parser("serve", help="start the browser interface and open it")
    serve.add_argument("--box", help="open this box when it starts")
    serve.add_argument("--read-only", action="store_true", help="refuse every change to the box")
    serve.add_argument(
        "--port", type=int, default=0, help="3082 or higher (default: any free port)"
    )
    serve.add_argument(
        "--no-browser", action="store_true", help="print the link instead of opening it"
    )
    serve.add_argument("--stop", action="store_true", help="stop a running Caixa")
    serve.add_argument("--node", help="the Node.js program to use (it must be 24.9 or newer)")

    commands.add_parser(
        "worker", help="serve JSON-RPC over stdio (for the interface)", add_help=False
    )
    return parser


# --- Helpers ----------------------------------------------------------------------------------


def _open(args: argparse.Namespace, read_only: bool = False) -> Service:
    """A service with the box opened: `--box`, else `CAIXA_BOX`, else the folder you are in."""
    where = args.box or os.environ.get(ENVIRONMENT)
    if not where:
        if (Path.cwd() / ".caixa" / "box.yaml").is_file():
            where = str(Path.cwd())
        else:
            raise ServiceError(
                "no_box",
                f"No box given: use --box PATH, set {ENVIRONMENT}, or run this inside a box.",
            )
    service = Service(read_only=read_only)
    service.box_open(where)
    return service


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _parse_options(service: Service, collector: str, pairs: Sequence[str]) -> dict[str, Any]:
    """`name=value` pairs, with each value read as the type the collector's schema declares."""
    try:
        schema = service.registry.get(collector).info.options_schema.get("properties", {})
    except KeyError:
        raise ServiceError("not_found", f"No collector '{collector}'.") from None
    options: dict[str, Any] = {}
    for pair in pairs:
        name, separator, text = pair.partition("=")
        if not separator or not name:
            raise ServiceError(
                "invalid_params", f"'{pair}' is not an option; write it as name=value."
            )
        kind = schema.get(name, {}).get("type", "string")
        try:
            if kind == "boolean":
                if text.lower() not in ("true", "false", "yes", "no", "1", "0"):
                    raise ValueError
                options[name] = text.lower() in ("true", "yes", "1")
            elif kind == "integer":
                options[name] = int(text)
            elif kind == "number":
                options[name] = float(text)
            else:
                options[name] = text
        except ValueError:
            raise ServiceError(
                "invalid_params", f"The option '{name}' must be a {kind}; got '{text}'."
            ) from None
    return options


def _explain(error: ServiceError) -> str:
    listed = error.data.get("errors")
    return "\n".join(f"caixa: {line}" for line in listed) if listed else f"caixa: {error}"


# --- Commands ---------------------------------------------------------------------------------


def _box_status_text(status: dict[str, Any]) -> str:
    lines = [
        f"{status['name']}  ({status['root']})",
        f"{_plural(status['items'], 'item')}, {_plural(status['people'], 'person')}"
        + (f"; owner {status['owner']}" if status.get("owner") else ""),
    ]
    lines += [f"  {kind}: {count}" for kind, count in sorted(status["by_type"].items())]
    for record in status["imports"]:
        lines.append(
            f"  import {record['id']}: {record['collector']} {record['status']} "
            f"({record['inserted']} new)"
        )
    return "\n".join(lines)


def _cmd_box(args: argparse.Namespace) -> int:
    if args.action == "create":
        service = Service()
        status = service.box_create(args.path, name=args.name, owner=args.owner)
    else:
        service = _open(args, read_only=True)
        status = service.box_status()
    print(json.dumps(status, indent=2) if args.json else _box_status_text(status))
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from caixa import diagnostics

    if bool(args.collector) != bool(args.source):
        raise ServiceError(
            "invalid_params", "Checking a source needs both --collector and --source."
        )
    where = args.box or os.environ.get(ENVIRONMENT)
    if not where and (Path.cwd() / ".caixa" / "box.yaml").is_file():
        where = str(Path.cwd())
    service = Service(read_only=True)  # looking, never changing
    if where:
        try:
            service.box_open(where)
        except ServiceError as error:
            print(f"(Could not open the box: {error})", file=sys.stderr)
    print(diagnostics.report(service, args.collector, args.source))
    return 0


def _cmd_collectors(args: argparse.Namespace) -> int:
    described = Service().collectors_list()
    if args.id:
        found = [c for c in described if c["id"] == args.id]
        if not found:
            raise ServiceError("not_found", f"No collector '{args.id}'.")
        described = found
    if args.json:
        _print_json(described if not args.id else described[0])
    elif args.id:
        entry = described[0]
        print(f"{entry['name']} ({entry['id']}); takes: {', '.join(entry['inputs'])}\n")
        print(entry["how_to_export"], "\n\nOptions (--option name=value):")
        for name, spec in entry["options_schema"]["properties"].items():
            print(f"  {name} ({spec.get('type')}, default {spec.get('default')!r}): "
                  f"{spec.get('description', '')}")  # fmt: skip
    else:
        for entry in described:
            print(f"{entry['id']:<12} {entry['name']}  [{', '.join(entry['inputs'])}]")
    return 0


def _preview_text(preview: dict[str, Any]) -> str:
    lines = [
        f"{_plural(preview['items'], 'item')} in {_plural(preview['conversations'], 'conversation')}"
        + (f", {preview['first']} to {preview['last']}" if preview["first"] else "")
    ]
    if preview["participants"]:
        lines.append("People: " + ", ".join(preview["participants"]))
    if preview["unresolved"]:
        lines.append("Not yet named: " + ", ".join(preview["unresolved"][:10]))
    lines += [f"Note: {w}" for w in preview["warnings"]]
    return "\n".join(lines)


def _result_text(result: dict[str, Any]) -> str:
    lines = [
        f"{result['inserted']} new, {result['updated']} changed, {result['unchanged']} unchanged; "
        f"{_plural(result['pages'], 'page')} written."
    ]
    unresolved = result["unresolved"]
    if unresolved:
        shown = ", ".join(unresolved[:10]) + (" …" if len(unresolved) > 10 else "")
        lines.append(f"{_plural(len(unresolved), 'handle')} still unnamed: {shown}")
        lines.append("Name them with 'caixa people link'.")
    lines += [f"Note: {w}" for w in result["warnings"]]
    return "\n".join(lines)


def _cmd_import(args: argparse.Namespace) -> int:
    service = _open(args)
    options = _parse_options(service, args.collector, args.option)
    if args.preview:
        preview = service.import_preview(args.collector, args.source, options)
        print(json.dumps(preview, indent=2) if args.json else _preview_text(preview))
        return 0
    screen = sys.stderr  # a running job redirects sys.stderr to its log; keep the real one

    def show(name: str, payload: dict[str, Any]) -> None:
        if name == "job.progress":
            print(f"{payload['stage']}: {payload['message']}".rstrip(": "), file=screen)

    service.subscribe(show)
    job = service.import_start(args.collector, args.source, options)
    try:
        done = service.wait(job["id"])
    except KeyboardInterrupt:
        service.import_cancel(job["id"])
        service.wait(job["id"])
        print("caixa: cancelled.", file=sys.stderr)
        return 130
    finally:
        service.close()
    if done["status"] != "done":
        print(f"caixa: {done['error'] or done['status']}", file=sys.stderr)
        return 1
    print(json.dumps(done["result"], indent=2) if args.json else _result_text(done["result"]))
    return 0


def _follow(service: Service, job: dict[str, Any], as_json: bool) -> int:
    """Wait for a job, showing its stages; print its result. The exit code says how it ended."""
    try:
        done = service.wait(job["id"])
    finally:
        service.close()
    if done["status"] != "done":
        print(f"caixa: {done['error'] or done['status']}", file=sys.stderr)
        return 1
    print(json.dumps(done["result"], indent=2) if as_json else _result_text(done["result"]))
    return 0


def _cmd_undo(args: argparse.Namespace) -> int:
    service = _open(args)
    info = service.import_undo_info()
    if info["job"] is None:
        print(info["reason"])
        return 0
    what = f"import #{info['job']} ({info['collector']}: {info['source']})"
    changes = info["people_changes"]
    extra = (
        f" This also undoes {_plural(changes, 'change')} made to people since then."
        if changes
        else ""
    )
    if not args.yes:
        print(f"This will undo {what}. The box goes back to how it was before it.{extra}")
        if input("Undo it? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Nothing was changed.")
            return 0
    job = service.import_undo()
    try:
        done = service.wait(job["id"])
    finally:
        service.close()
    if done["status"] != "done":
        print(f"caixa: {done['error'] or done['status']}", file=sys.stderr)
        return 1
    removed = done["result"].get("files_removed", 0)
    print(f"Undid {what}: {_plural(removed, 'file')} removed.{extra}")
    return 0


def _cmd_again(args: argparse.Namespace) -> int:
    service = _open(args)
    return _follow(service, service.import_again(args.job), args.json)


def _cmd_jobs(args: argparse.Namespace) -> int:
    jobs = _open(args, read_only=True).jobs_list(limit=args.limit)
    if args.json:
        _print_json(jobs)
    elif not jobs:
        print("No jobs yet.")
    for job in jobs if not args.json else []:
        inserted = (job["result"] or {}).get("inserted")
        outcome = f"{inserted} new" if inserted is not None else (job["error"] or "")
        print(
            f"#{job['id']:<4} {job['kind']:<8} {job['collector'] or '':<12} {job['status']:<12} {outcome}"
        )
    return 0


def _finish_people_change(service: Service, change: dict[str, Any]) -> None:
    if change.get("job"):
        service.wait(change["job"]["id"])
    service.close()


def _cmd_people(args: argparse.Namespace) -> int:
    read_only = args.action in ("list", "unresolved")
    service = _open(args, read_only=read_only)
    if args.action == "list":
        listing = service.people_list()
        if args.json:
            _print_json(listing)
        for person in [] if args.json else listing["people"]:
            owner = "  (owner)" if person["is_owner"] else ""
            print(f"{person['id']:<4} {person['name']}{owner}  {person['items']} items")
        return 0
    if args.action == "unresolved":
        found = service.people_unresolved()
        if args.json:
            _print_json(found)
        elif not found["handles"]:
            print("Everyone is named.")
        for handle in [] if args.json else found["handles"]:
            shown_as = handle["display_name"] or ""
            print(
                f"{handle['service']:<12} {handle['identifier']}  {shown_as}  "
                f"({handle['messages']} messages)"
            )
        return 0
    if args.action == "link":
        who: Any = int(args.person) if args.person.isdigit() else args.person
        change = service.people_link(args.service, args.identifier, who, move=args.move)
    elif args.action == "rename":
        change = service.people_rename(args.person, args.name)
    else:
        change = service.people_merge(args.source, args.target)
    _finish_people_change(service, change)
    print(
        json.dumps(change["person"], indent=2)
        if args.json
        else f"Done: {change['person']['name']}."
    )
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from caixa import serve
    from caixa.box import Box, BoxError

    chosen = args.box or os.environ.get(ENVIRONMENT)
    if chosen:
        try:
            Box.open(chosen)
        except BoxError as error:
            raise ServiceError("not_found", str(error)) from None
    try:
        return serve.run(
            serve.Options(
                box=chosen, read_only=args.read_only, port=args.port,
                no_browser=args.no_browser, stop=args.stop, node=args.node,
            )  # fmt: skip
        )
    except serve.ServeError as error:
        raise ServiceError("serve", str(error)) from None


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["worker"]:  # the worker has its own options; hand them over as they are
        from caixa import worker

        return worker.main(arguments[1:])
    parser = build_parser()
    args = parser.parse_args(arguments)
    handlers = {
        "box": _cmd_box,
        "collectors": _cmd_collectors,
        "again": _cmd_again,
        "doctor": _cmd_doctor,
        "undo": _cmd_undo,
        "import": _cmd_import,
        "jobs": _cmd_jobs,
        "people": _cmd_people,
        "serve": _cmd_serve,
    }
    if args.command not in handlers:
        parser.print_help()
        return 0
    try:
        return handlers[args.command](args)
    except ServiceError as error:
        print(_explain(error), file=sys.stderr)
        return 1
