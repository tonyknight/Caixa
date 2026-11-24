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
from caixa import owner as owner_file
from caixa.box import Box
from caixa.mail import write as mail_write
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

    reset = commands.add_parser(
        "reset",
        help="take out everything imported, keeping the box's settings and the names you gave",
    )
    reset.add_argument("--forget-names", action="store_true", help="forget those names too")
    reset.add_argument("--yes", action="store_true", help="do it without asking")
    _box_argument(reset)

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

    documents = commands.add_parser("documents", help="the documents (PDFs) filed in the box")
    document_commands = documents.add_subparsers(dest="action", metavar="action", required=True)
    listing = document_commands.add_parser("list", help="every document, by date")
    listing.add_argument("--type", help="only documents of this type (statement, bill, …)")
    listing.add_argument("--author", help="only documents by this author")
    listing.add_argument("--year", type=int, help="only documents of this year")
    listing.add_argument("--status", help="only documents with this status (needs_review, …)")
    listing.add_argument("--tag", help="only documents with this tag")
    _box_argument(listing)
    fix = document_commands.add_parser(
        "update", help="correct a document: --author, --date, --title, --type (yours from then on)"
    )
    fix.add_argument("item_id", help="the document's id")
    fix.add_argument("--author", help="who issued, sent or wrote it")
    fix.add_argument("--date", help="its date: YYYY, YYYY-MM or YYYY-MM-DD")
    fix.add_argument("--title", help="what it is, in a few words")
    fix.add_argument("--type", help="statement, bill, invoice, insurance, tax, …")
    _box_argument(fix)
    waiting = document_commands.add_parser("review", help="the documents waiting for you, and why")
    _box_argument(waiting)
    tags = document_commands.add_parser(
        "tags", help="a document's tags (--add, --remove), or with --starter the starter set"
    )
    tags.add_argument("item_id", nargs="?", help="the document's id")
    tags.add_argument("--add", nargs="+", default=[], help="tags to add")
    tags.add_argument("--remove", nargs="+", default=[], help="tags to take off")
    tags.add_argument("--starter", action="store_true", help="change the starter set instead")
    _box_argument(tags)
    who = document_commands.add_parser(
        "authors", help="the authors documents are filed under: list, rename ID NAME, merge FROM TO"
    )
    who.add_argument("verb", nargs="?", default="list", choices=["list", "rename", "merge"])
    who.add_argument("values", nargs="*", help="rename: ID NAME; merge: FROM_ID TO_ID")
    _box_argument(who)
    read = document_commands.add_parser(
        "enrich", help="read documents with the model: those waiting, those named, or --all"
    )
    read.add_argument("item_ids", nargs="*", help="documents' ids, as `caixa documents list` shows")
    read.add_argument("--all", action="store_true", help="every document, read again")
    _box_argument(read)
    again = document_commands.add_parser(
        "reprocess",
        help="OCR documents again: those named, or --failed for every one that needs it",
    )
    again.add_argument(
        "item_ids", nargs="*", help="documents' ids, as `caixa documents list` shows"
    )
    again.add_argument("--failed", action="store_true", help="every document OCR could improve")
    again.add_argument("--languages", help="Tesseract languages for this run, such as eng+por")
    _box_argument(again)
    find = document_commands.add_parser(
        "search", help='find documents by their words ("a phrase", prefix*), and their facts'
    )
    find.add_argument("query", nargs="?", default="", help="the words to find")
    for name, help_text in (
        ("type", "only documents of this type"), ("category", "only this category"),
        ("author", "only this author"), ("date-from", "from this date (YYYY, YYYY-MM or YYYY-MM-DD)"),
        ("date-to", "up to this date"), ("tag", "only documents with this tag"),
        ("status", "only documents with this status"),
    ):  # fmt: skip
        find.add_argument(f"--{name}", help=help_text)
    find.add_argument("--limit", type=int, default=50, help="at most this many pages (50)")
    _box_argument(find)
    show = document_commands.add_parser("show", help="everything known about one document")
    show.add_argument("item_id", help="the document's id, as `caixa documents list` shows it")
    _box_argument(show)

    mail = commands.add_parser("mail", help="read, clean and sort mail before importing it")
    mail_commands = mail.add_subparsers(dest="action", metavar="action", required=True)
    read = mail_commands.add_parser(
        "read", help="read an mbox (or a zip or folder of them) into the box's mail index"
    )
    read.add_argument("source", help="an .mbox file, a .zip holding mboxes, or a folder")
    read.add_argument("--account", help="the account the mail comes from, such as Gmail or Work")
    read.add_argument("--workers", type=int, help="processes at once (default: the setting)")
    _box_argument(read)
    clean = mail_commands.add_parser(
        "clean", help="show the junk in an mbox, by group and sender; --write leaves it out"
    )
    clean.add_argument("source", help="an .mbox file, a .zip holding mboxes, or a folder")
    clean.add_argument("--account", help="the account the mail comes from (once per mbox)")
    clean.add_argument(
        "--write", action="store_true", help="write the Cleaned mbox beside the source"
    )
    _box_argument(clean)
    senders = mail_commands.add_parser(
        "senders", help="an mbox's senders: known, to sort, to import, ignored, imported"
    )
    senders.add_argument("source", help="an .mbox file, a .zip holding mboxes, or a folder")
    senders.add_argument("--account", help="the account the mail comes from (once per mbox)")
    _box_argument(senders)
    for name, what in (("choose", "choose senders to import"), ("ignore", "ignore senders")):
        decide = mail_commands.add_parser(name, help=what)
        decide.add_argument("addresses", nargs="+", help="the senders' addresses")
        decide.add_argument("--forget", action="store_true", help="forget the decision")
        _box_argument(decide)
    imported = mail_commands.add_parser(
        "import", help="import the conversations of the chosen senders (see 'caixa mail senders')"
    )
    imported.add_argument("source", help="an .mbox file, a .zip holding mboxes, or a folder")
    imported.add_argument("--account", help="the account the mail comes from (once per mbox)")
    _box_argument(imported)
    reduced = mail_commands.add_parser(
        "reduce", help="write the Reduced mbox: everything not yet in the box, beside the source"
    )
    reduced.add_argument("source", help="an .mbox file, a .zip holding mboxes, or a folder")
    reduced.add_argument("--account", help="the account the mail comes from (once per mbox)")
    _box_argument(reduced)
    sampled = mail_commands.add_parser(
        "sample", help="draw a few conversations three ways, to choose how mail looks"
    )
    sampled.add_argument("source", help="an .mbox file, a .zip holding mboxes, or a folder")
    sampled.add_argument("--out", required=True, help="the folder to write the samples into")
    sampled.add_argument("--account", help="the account the mail comes from (once per mbox)")
    sampled.add_argument("--conversations", type=int, default=6, help="how many (default 6)")
    _box_argument(sampled)
    keep = mail_commands.add_parser("keep", help="never leave a sender's mail out when cleaning")
    keep.add_argument("addresses", nargs="+", help="the senders' addresses")
    keep.add_argument("--forget", action="store_true", help="stop keeping them")
    _box_argument(keep)

    bench = commands.add_parser(
        "benchmark",
        help="time summaries, translations and documents: Apple Intelligence against your model",
        description="Times summaries and translations of 100 made-up emails, and readings of 12 "
        "made-up documents (tools/ai-benchmark), "
        "through Apple Intelligence and through an OpenAI-compatible endpoint, at several worker "
        "counts, and writes a report. Nothing from a box is sent.",
    )
    bench.add_argument("--endpoint", help="your model's address, such as http://localhost:8000/v1")
    bench.add_argument("--model", help="the model's name as the endpoint knows it")
    bench.add_argument("--api-key", help="the endpoint's key (or set CAIXA_BENCHMARK_API_KEY)")
    bench.add_argument("--ask-key", action="store_true", help="ask for the key without showing it")
    bench.add_argument(
        "--apple-workers", default="1,2,4,8", help="helpers at once (default 1,2,4,8)"
    )
    bench.add_argument(
        "--endpoint-workers", default="1,2,4", help="requests at once (default 1,2,4)"
    )
    bench.add_argument("--only", choices=["apple", "endpoint"], help="time only one side")
    bench.add_argument(
        "--tasks",
        default="summaries,translations,documents",
        help="any of summaries, translations, documents (default: all three)",
    )
    bench.add_argument("--emails", help="another emails file in the same form")
    bench.add_argument(
        "--out", help="the folder for the report (default: ai-benchmark-<date> here)"
    )

    serve = commands.add_parser("serve", help="start the browser interface and open it")
    serve.add_argument("--box", help="open this box when it starts")
    serve.add_argument("--read-only", action="store_true", help="refuse every change to the box")
    serve.add_argument("--port", type=int, default=0, help="1024 to 65535 (default: any free port)")
    serve.add_argument(
        "--no-browser", action="store_true", help="print the link instead of opening it"
    )
    serve.add_argument("--stop", action="store_true", help="stop a running Caixa")

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


def _mail_read_text(result: dict[str, Any]) -> str:
    lines = []
    for source in result["sources"]:
        name = source["member"] or Path(source["path"]).name
        how = "already read" if source["reused"] else f"read in {source['seconds']:.1f} s"
        lines.append(f"{name} ({source['account']}): {_plural(source['mails'], 'mail')}, {how}.")
    return "\n".join(lines)


def _clean_text(reply: dict[str, Any]) -> str:
    source = reply["source"]
    name = source["member"] or Path(source["path"]).name
    lines = [f"{name} ({source['account']}): {_plural(source['mails'], 'mail')}"]
    for group in reply["groups"]:
        lines.append(
            f"{group['label']}: {_plural(group['senders'], 'sender')}, "
            f"{_plural(group['mails'], 'mail')}, {mail_write.human_size(group['size'])}"
        )
        lines += [
            f"  {row['mails']:>6}  {mail_write.human_size(row['size']):>9}  "
            f"{row['name']} <{row['address']}>"
            for row in group["rows"][:10]
        ]
        if len(group["rows"]) > 10:
            lines.append(f"  … and {len(group['rows']) - 10} more")
    left = reply["left_out"]
    lines.append(
        f"Writing the cleaned mbox would leave out {_plural(left['mails'], 'mail')} "
        f"({mail_write.human_size(left['size'])}) from {_plural(left['senders'], 'sender')}."
    )
    return "\n".join(lines)


def _senders_text(reply: dict[str, Any]) -> str:
    source = reply["source"]
    name = source["member"] or Path(source["path"]).name
    lines = [f"{name} ({source['account']}): {_plural(source['mails'], 'mail')}"]
    for category in reply["categories"]:
        lines.append(
            f"{category['label']}: {_plural(category['senders'], 'sender')}, "
            f"{_plural(category['mails'], 'mail')}"
        )
        for row in category["rows"][:10]:
            how = {"address": "known", "name": f"by name: {row['person']}?"}.get(
                row["known_by"] or "", ""
            )
            wrote = f"you wrote {row['owner_wrote']}" if row["owner_wrote"] else ""
            notes = ", ".join(n for n in (how, wrote) if n)
            lines.append(
                f"  {row['mails']:>6}  {row['name']} <{row['address']}>"
                + (f"  ({notes})" if notes else "")
            )
        if len(category["rows"]) > 10:
            lines.append(f"  … and {len(category['rows']) - 10} more")
    picked = reply["selection"]
    lines.append(
        f"Importing would bring {_plural(picked['mails'], 'mail')} in "
        f"{_plural(picked['threads'], 'conversation')} ({mail_write.human_size(picked['size'])})."
    )
    return "\n".join(lines)


def _cmd_mail(args: argparse.Namespace) -> int:
    if args.action in ("choose", "ignore"):
        service = _open(args)
        box = Box.open(service.box_status()["root"])
        kind = "chosen" if args.action == "choose" else "ignored"
        owner_file.set_mail_decision(box, args.addresses, kind, on=not args.forget)
        decided = owner_file.load(box)["mail"][kind]
        print(json.dumps({kind: decided}, indent=2) if args.json else
              f"{kind.capitalize()}: " + (", ".join(decided) or "nobody"))  # fmt: skip
        return 0
    if args.action == "keep":
        service = _open(args)
        box = Box.open(service.box_status()["root"])
        kept = owner_file.set_mail_kept(box, args.addresses, keep=not args.forget)
        print(json.dumps({"kept": kept}, indent=2) if args.json else
              "Kept when cleaning: " + (", ".join(kept) or "nobody"))  # fmt: skip
        return 0
    service = _open(args)
    screen = sys.stderr  # a running job redirects sys.stderr to its log; keep the real one

    def show(name: str, payload: dict[str, Any]) -> None:
        if name == "job.progress" and payload.get("message"):
            print(f"{payload['stage']}: {payload['message']}", file=screen)

    service.subscribe(show)
    try:
        workers = getattr(args, "workers", None)
        job = service.mail_read(args.source, account=args.account, workers=workers)
        done = service.wait(job["id"])
    except KeyboardInterrupt:
        print("caixa: cancelled.", file=sys.stderr)
        return 130
    finally:
        service.close()
    if done["status"] != "done":
        print(f"caixa: {done['error'] or done['status']}", file=sys.stderr)
        return 1
    if args.action == "read":
        print(
            json.dumps(done["result"], indent=2) if args.json else _mail_read_text(done["result"])
        )
        return 0
    service = _open(args)
    service.subscribe(show)
    try:
        for source in done["result"]["sources"]:
            if args.action == "reduce":
                job = service.mail_reduce(source["source_id"])
                ended = service.wait(job["id"])
                if ended["status"] != "done":
                    print(f"caixa: {ended['error'] or ended['status']}", file=sys.stderr)
                    return 1
                got = ended["result"]
                print(json.dumps(got, indent=2) if args.json else
                      f"Wrote {got['path']}: {_plural(got['mails'], 'mail')} kept, "
                      f"{_plural(got['left_out'], 'mail')} left out "
                      f"({mail_write.human_size(got['left_out_size'])}).")  # fmt: skip
                continue
            if args.action == "import":
                job = service.mail_import(source["source_id"])
                ended = service.wait(job["id"])
                if ended["status"] != "done":
                    print(f"caixa: {ended['error'] or ended['status']}", file=sys.stderr)
                    return 1
                got = ended["result"]
                print(json.dumps(got, indent=2) if args.json else
                      f"{_result_text(got)}\n{_plural(got['mails'], 'mail')} in "
                      f"{_plural(got['conversations'], 'conversation')} from "
                      f"{_plural(got['senders'], 'sender')}, account {got['account']}.")  # fmt: skip
                continue
            if args.action == "sample":
                from caixa.mail import sample as mail_sample
                from caixa.mail.index import MailIndex

                out = Path(args.out).expanduser()
                if len(done["result"]["sources"]) > 1:
                    out = out / Path(source["member"] or source["path"]).stem
                box = Box.open(service.box_status()["root"])
                with MailIndex.for_box(box, read_only=True) as index:
                    made = mail_sample.sample(index, source["source_id"], out, args.conversations)
                print(f"{_plural(made.conversations, 'conversation')} drawn three ways: "
                      f"open {out / 'index.html'}")  # fmt: skip
                continue
            if args.action == "senders":
                listed = service.mail_senders(source["source_id"])
                print(json.dumps(listed, indent=2) if args.json else _senders_text(listed))
                continue
            reply = service.mail_clean(source["source_id"])
            if not args.write:
                print(json.dumps(reply, indent=2) if args.json else _clean_text(reply))
                continue
            job = service.mail_clean_write(source["source_id"])
            written = service.wait(job["id"])
            if written["status"] != "done":
                print(f"caixa: {written['error'] or written['status']}", file=sys.stderr)
                return 1
            result = written["result"]
            print(json.dumps(result, indent=2) if args.json else
                  f"Wrote {result['path']}: {_plural(result['mails'], 'mail')} kept, "
                  f"{_plural(result['left_out'], 'mail')} left out "
                  f"({mail_write.human_size(result['left_out_size'])}).")  # fmt: skip
    finally:
        service.close()
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


def _cmd_reset(args: argparse.Namespace) -> int:
    service = _open(args)
    try:
        box = service._require_box()
        names = (
            "and the names you gave people" if args.forget_names else "but not the names you gave"
        )
        if not args.yes:
            print(
                f"This takes everything imported out of '{box.name}' ({box.root}): its pages, the "
                f"files it filed, its people {names}. Its settings, its owner, README.md and "
                "Inbox stay. The exports you imported from are not touched."
            )
            if input("Reset the box? [y/N] ").strip().lower() not in ("y", "yes"):
                print("Nothing was changed.")
                return 0
        done = service.box_reset(forget_names=args.forget_names)
    finally:
        service.close()
    print(f"Reset: {_plural(done['removed'], 'file')} removed.")
    if done["names_kept"]:
        print(f"{_plural(done['names_kept'], 'name')} you gave people will apply again.")
    for left in done["left"]:
        print(f"Left in place (not written by Caixa): {left}")
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


def _cmd_documents(args: argparse.Namespace) -> int:
    if args.action == "update":
        service = _open(args)
        changed = service.documents_update(
            args.item_id, author=args.author, date=args.date, title=args.title, type=args.type
        )
        print(json.dumps(changed, indent=2) if args.json else
              f"Filed as {changed['document']['file_path']}.")  # fmt: skip
        return 0
    if args.action == "review":
        listing = _open(args, read_only=True).documents_review()
        if args.json:
            _print_json(listing)
        elif not listing["documents"]:
            print("Nothing waits for review.")
        for document in [] if args.json else listing["documents"]:
            print(
                f"{document['title'] or document['original_filename']}: {'; '.join(document['reasons'])}"
            )
            print(f"            {document['item_id']}")
        return 0
    if args.action == "tags":
        service = _open(args)
        if args.starter:
            starter = service.documents_tags_starter(args.add, args.remove)
            print(json.dumps(starter, indent=2) if args.json else ", ".join(starter["starter"]))
            return 0
        if not args.item_id:
            raise ServiceError("invalid_params", "Give a document's id, or --starter.")
        changed = service.documents_tags(args.item_id, args.add, args.remove)
        print(json.dumps(changed, indent=2) if args.json else
              ", ".join(t["tag"] for t in changed["tags"]) or "No tags.")  # fmt: skip
        return 0
    if args.action == "authors":
        service = _open(args, read_only=args.verb == "list")
        if args.verb == "list":
            listing = service.documents_authors()
            if args.json:
                _print_json(listing)
            for author in [] if args.json else listing["authors"]:
                also = f"  (also {', '.join(author['aliases'])})" if author["aliases"] else ""
                print(
                    f"{author['id']:<4} {author['name']}  {_plural(author['documents'], 'document')}{also}"
                )
            return 0
        if len(args.values) != 2:
            raise ServiceError("invalid_params", f"'authors {args.verb}' takes two values.")
        if args.verb == "rename":
            change = service.documents_authors_rename(int(args.values[0]), args.values[1])
            print(json.dumps(change, indent=2) if args.json else
                  f"Renamed: {change['author']['name']} ({_plural(change['moved'], 'file')} moved).")  # fmt: skip
        else:
            change = service.documents_authors_merge(int(args.values[0]), int(args.values[1]))
            print(json.dumps(change, indent=2) if args.json else
                  f"Merged into {change['author']['name']} ({_plural(change['moved'], 'file')} moved).")  # fmt: skip
        return 0
    if args.action == "enrich":
        service = _open(args)
        job = service.documents_enrich(item_ids=args.item_ids, all=args.all)
        try:
            done = service.wait(job["id"])
        finally:
            service.close()
        if done["status"] != "done":
            print(f"caixa: {done['error'] or done['status']}", file=sys.stderr)
            return 1
        result = done["result"]
        if args.json:
            _print_json(result)
        elif result.get("reason"):
            print(f"Nothing was read: {result['message']}")
        else:
            print(
                f"{result['enriched']} read, {result['needs_review']} need review, "
                f"{result['failed']} failed."
            )
        return 0
    if args.action == "reprocess":
        service = _open(args)
        job = service.documents_reprocess(
            item_ids=args.item_ids, failed=args.failed, languages=args.languages
        )
        try:
            done = service.wait(job["id"])
        finally:
            service.close()
        if done["status"] != "done":
            print(f"caixa: {done['error'] or done['status']}", file=sys.stderr)
            return 1
        result = done["result"]
        if args.json:
            _print_json(result)
        else:
            print(
                f"{result['reprocessed']} reprocessed: {result['improved']} improved, "
                f"{result['failed']} still failing (languages {result['languages']})."
            )
        return 0
    service = _open(args, read_only=True)
    if args.action == "search":
        found = service.documents_search(
            args.query, type=args.type, category=args.category, author=args.author,
            date_from=args.date_from, date_to=args.date_to, tag=args.tag, status=args.status,
            limit=args.limit,
        )  # fmt: skip
        if args.json:
            _print_json(found)
            return 0
        if not found["hits"]:
            print("Nothing found.")
        for hit in found["hits"]:
            title = hit["title"] or hit["original_filename"]
            author = f" - {hit['author']}" if hit["author"] else ""
            read = " (OCR)" if hit["source"] == "ocr" else ""
            snippet = " ".join(str(hit["snippet"] or "").split())
            print(f"{hit['date'] or 'undated':<10}  {title}{author}, page {hit['page']}{read}")
            print(f"            {snippet}\n            {hit['file_path']}")
        return 0
    if args.action == "list":
        listing = service.documents_list(
            type=args.type, author=args.author, year=args.year, status=args.status, tag=args.tag
        )
        if args.json:
            _print_json(listing)
            return 0
        if not listing["documents"]:
            print("No documents.")
        for document in listing["documents"]:
            when = document["date"] or "undated"
            title = document["title"] or document["original_filename"]
            author = f" - {document['author']}" if document["author"] else ""
            status = (
                f"  [{document['processing_status']}]"
                if document["processing_status"] != "archived"
                else ""
            )
            print(f"{when:<10}  {title}{author}{status}\n            {document['item_id']}")
        return 0
    found = service.documents_get(args.item_id)
    if args.json:
        _print_json(found)
        return 0
    for key in ("title", "author", "type", "category", "date", "date_precision", "file_path",
                "original_filename", "processing_status", "ocr_status", "validation_status",
                "ai_status"):  # fmt: skip
        print(f"{key.replace('_', ' '):<18} {found[key] if found[key] is not None else ''}")
    if found["tags"]:
        print(f"{'tags':<18} {', '.join(t['tag'] for t in found['tags'])}")
    for source in found["sources"]:
        print(f"{'found at':<18} {source['path']}")
    if found["summary"]:
        print(f"\n{found['summary']}")
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
                no_browser=args.no_browser, stop=args.stop,
            )  # fmt: skip
        )
    except serve.ServeError as error:
        raise ServiceError("serve", str(error)) from None


def _cmd_benchmark(args: argparse.Namespace) -> int:
    """Apple Intelligence against an endpoint, on made-up emails (see `caixa.benchmark`)."""
    import getpass
    from datetime import datetime

    from caixa import benchmark

    def counts(text: str) -> list[int]:
        try:
            found = [int(n) for n in text.replace(" ", "").split(",") if n]
        except ValueError:
            found = []
        if not found or any(n < 1 or n > 32 for n in found):
            raise ServiceError(
                "invalid_params",
                f"Worker counts are whole numbers from 1 to 32, such as 1,2,4: not '{text}'.",
            )
        return found

    key = args.api_key or os.environ.get("CAIXA_BENCHMARK_API_KEY") or None
    if not key and args.ask_key:
        key = getpass.getpass("API key for the endpoint (not shown): ").strip() or None
    if args.only != "apple" and not (args.endpoint and args.model):
        print("Give your model's --endpoint and --model (or --only apple).", file=sys.stderr)
        return 2
    out = (
        Path(args.out).expanduser()
        if args.out
        else Path.cwd() / f"ai-benchmark-{datetime.now():%Y-%m-%d-%H%M}"
    )
    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    if not tasks or any(t not in benchmark.TASKS for t in tasks):
        print("--tasks is summaries, translations, or both (comma between).", file=sys.stderr)
        return 2
    print(f"Timing {', '.join(tasks)} on made-up emails; the report goes to {out}")
    benchmark.run(
        endpoint=args.endpoint, model=args.model, api_key=key,
        apple_workers=counts(args.apple_workers), endpoint_workers=counts(args.endpoint_workers),
        only=args.only, tasks=tasks, emails=Path(args.emails).expanduser() if args.emails else None,
        out=out, say=print,
    )  # fmt: skip
    print(f"Report: {out / 'report.md'}")
    return 0


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
        "reset": _cmd_reset,
        "import": _cmd_import,
        "jobs": _cmd_jobs,
        "mail": _cmd_mail,
        "documents": _cmd_documents,
        "benchmark": _cmd_benchmark,
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
