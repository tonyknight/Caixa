"""The PDF import's dry run (D31; D28 and D30 as amended): see where a folder of PDFs would go,
for Apple Intelligence and for the local model, before importing anything.

There is one code path: the import itself. For each model, `prepare` makes a throwaway box in a
temporary folder, outside the real box, seeded from the real box (a copy of its master database,
its settings with that model, and its author knowledge), and runs the PDF collector's own `run` on
the folder there, with `organized` when asked. It then reads where each file went, and why, and
deletes the throwaway box. So the dry run follows the import rule for rule: inspection and OCR,
what the model reads and is told, the second look, author knowledge, organized names and filing.
A file the box already has comes out "already in the box", at its place.

It writes `(YYYY-MM-DD) PDF Import Preview.json` at the box's root (a second run that day replaces
it): both models' trees (`apple`, `local`; folders as objects, each file as `{from, name, why}`)
and a `report`: the two trees compared, the time each model took, each file's preprocessing, the
organized names, and what was learned. `report_text` is the readable report the command prints.
Nothing else is written into the box, except, with `organized`, what the owner's names teach
(`.caixa/author-knowledge.json`, D30). The preview holds names, places and decisions, never page
text.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Optional

from caixa.box import Box

#: The preview's name at the box's root.
PREVIEW = "({day}) PDF Import Preview.json"
LABELS = ("apple", "local")
#: What can become of an organized name, in the order the report counts them.
OUTCOMES = ("kept", "date replaced", "no author", "waiting", "not organized")


@dataclass
class Prepared:
    """A dry run: where its preview was written, the preview itself, and its readable report."""

    path: Path
    preview: dict[str, Any]
    text: str


def preview_path(box: Box, day: Optional[date] = None) -> Path:
    return box.root / PREVIEW.format(day=(day or date.today()).isoformat())


def models_for(box: Box) -> dict[str, Optional[dict[str, Any]]]:
    """The settings each run reads with: Apple Intelligence when it is available here, and the
    endpoint and model in Settings when they are on this computer; `None` for one that cannot
    run."""
    from chattr.translation import is_local_endpoint

    from caixa import apple_intelligence, settings, summaries

    values = settings.load(box)
    apple = {"summaries.provider": "apple"} if apple_intelligence.available() else None
    address = summaries.endpoint(values)
    name = str(values.get("summaries.model") or values.get("translation.model") or "").strip()
    local: Optional[dict[str, Any]] = None
    if address and name and is_local_endpoint(address):
        local = {"summaries.provider": "endpoint", "summaries.endpoint": address,
                 "summaries.model": name}  # fmt: skip
    return {"apple": apple, "local": local}


def _pdfs(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf" and not path.name.startswith(".")
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _known_sources(box: Box) -> set[str]:
    """The sources the real box has already, by their bytes' hash."""
    if not box.master_path.exists():
        return set()
    with box.master(read_only=True) as master:
        try:
            rows = master.connection.execute("SELECT source_sha256 FROM documents").fetchall()
        except sqlite3.Error:  # an older database, before documents
            return set()
    return {str(row[0]) for row in rows}


def _seed(real: Box, folder: Path, values: Mapping[str, Any]) -> Box:
    """A throwaway box in `folder`: the real box's master (copied with SQLite's backup), its
    settings with this run's model (and no embedding), and its author knowledge."""
    from caixa import settings
    from caixa.documents import author_knowledge

    made = Box.create(folder / "Box", name=real.name)
    for side in ("", "-wal", "-shm"):
        Path(str(made.master_path) + side).unlink(missing_ok=True)
    if real.master_path.exists():
        with real.master(read_only=True) as master:
            copy = sqlite3.connect(made.master_path)
            try:
                master.connection.backup(copy)
            finally:
                copy.close()
    saved = settings.load(real)
    settings.save(made, {**saved, **values, "documents.enrich": True,
                         "documents.embedding_model": ""})  # fmt: skip
    taught = author_knowledge.path_of(real)
    if taught.is_file():
        shutil.copyfile(taught, author_knowledge.path_of(made))
    return made


def _looks(events_path: Optional[Path]) -> dict[str, str]:
    """Which look found a fact, by the document's file name, from the session log."""
    found: dict[str, str] = {}
    if events_path is None or not events_path.is_file():
        return found
    for line in events_path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("event") != "propose" or "document" not in event:
            continue
        looks = {event.get("author_look"), event.get("date_look")}
        found[str(event["document"]["name"])] = "bottom" if "bottom" in looks else "first"
    return found


def _organized_name(source: str, place: str, review: list[str]) -> dict[str, Any]:
    from caixa.documents.organized import read_organized

    name = read_organized(source)
    if name is None:
        return {"name": "not organized"}
    filed = Path(place).name
    if "/Unrecognized/" in f"/{place}":
        return {"name": "waiting" if "no_date" in review else "no author"}
    if filed == Path(source).name:
        return {"name": "kept"}
    now = read_organized(filed)
    return {"name": "date replaced", "from_date": name.date, "to_date": now.date if now else None}


def _run(
    real: Box,
    folder: Path,
    values: Mapping[str, Any],
    organized: bool,
    already: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], float]:
    """The import, run in a throwaway box with one model: each file's place and why, the
    preprocessing it found, and the seconds it took."""
    from caixa import session_log, settings
    from caixa.collectors.pdfImport import PdfCollector
    from caixa.documents import records
    from caixa.documents.enrich import is_cover
    from caixa.documents.pages import REASONS

    places: dict[str, dict[str, Any]] = {}
    seen: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="caixa-prepare-") as scratch:
        box = _seed(real, Path(scratch), values)
        workers = int(settings.load(box).get("workers") or 1)
        options: dict[str, Any] = {"workers": workers, **({"organized": True} if organized else {})}
        began = time.monotonic()
        with session_log.opened(box, 0, "PDF import dry run") as log:
            PdfCollector().run(box, folder, options, lambda step: None)
        seconds = time.monotonic() - began
        looks = _looks(getattr(log, "events_path", None))
        with box.master(read_only=True) as master:
            for path in _pdfs(folder):
                source = path.relative_to(folder).as_posix()
                sha = _sha256(path)
                item_id = records.find_by_source(master, sha)
                if item_id is None:
                    continue
                document = records.get_document(master, item_id)
                place = str(document["file_path"])
                if sha in already:
                    places[source] = {"place": place, "why": "already in the box", "look": None}
                    continue
                review = list(document["review"] or [])
                record: dict[str, Any] = {
                    "place": place,
                    "why": "; ".join(REASONS.get(r, r) for r in review) or None,
                    "look": looks.get(path.name),
                }
                if organized:
                    record.update(_organized_name(path.name, place, review))
                places[source] = record
                pages = master.connection.execute(
                    "SELECT page, text, source FROM document_pages WHERE item_id = ? ORDER BY page",
                    (item_id,),
                ).fetchall()
                first = str(pages[0][1] or "") if pages else ""
                seen[source] = {
                    "ocr_pages": [int(page) for page, _, kind in pages if kind == "ocr"],
                    "cover": len(pages) > 1 and is_cover(first),
                }
    return places, seen, seconds


def _tree(places: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Folders as objects, down to each file's record: where it came from, and what and why."""
    tree: dict[str, Any] = {}
    for source, record in places.items():
        parts = str(record["place"]).split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        leaf = {"from": source}
        leaf.update({k: record[k] for k in ("name", "why") if record.get(k)})
        node[parts[-1]] = leaf
    return tree


def _outcome(
    apple: Optional[Mapping[str, Any]], local: Optional[Mapping[str, Any]]
) -> Optional[str]:
    if apple is None or local is None:
        return None
    waiting = ["/Unrecognized/" in f"/{one['place']}" for one in (apple, local)]
    if waiting[0] != waiting[1]:
        return "one"
    return "same" if apple["place"] == local["place"] else "different"


def _learn(box: Box, folder: Path) -> dict[str, Any]:
    """What the owner's organized names teach the real box (D30): their authors and tags."""
    from caixa.documents import author_knowledge
    from caixa.documents.organized import read_organized

    authors: list[str] = []
    tags: list[str] = []
    for path in _pdfs(folder):
        name = read_organized(path.name)
        if name is not None:
            authors += [name.author] if name.author else []
            tags += name.tags
    known = author_knowledge.load(box)
    new_authors, new_tags = author_knowledge.learn_organized(known, authors, tags)
    author_knowledge.save(box, known)

    def distinct(names: list[str]) -> int:
        return len({" ".join(name.casefold().split()) for name in names})

    return {"authors": new_authors, "tags": new_tags,
            "already_authors": distinct(authors) - len(new_authors),
            "already_tags": distinct(tags) - len(new_tags)}  # fmt: skip


def prepare(
    folder: Path,
    box: Path,
    *,
    organized: bool = False,
    models: Optional[Mapping[str, Optional[Mapping[str, Any]]]] = None,
) -> Prepared:
    """The dry run (see the module text). `models` gives each run's settings (`None`: not run);
    by default `models_for(box)`."""
    real = Box.open(box)
    chosen = dict(models) if models is not None else models_for(real)
    already = _known_sources(real)
    runs: dict[str, Optional[dict[str, dict[str, Any]]]] = {}
    states: dict[str, dict[str, Any]] = {}
    seen: dict[str, dict[str, Any]] = {}
    for label in LABELS:
        values = chosen.get(label)
        if values is None:
            runs[label] = None
            states[label] = {"state": "not run"}
            continue
        places, found, seconds = _run(real, folder, values, organized, already)
        runs[label] = places
        seen = seen or found
        states[label] = {"state": "ran", "seconds": round(seconds, 1),
                         "model": values.get("summaries.model") or values.get("summaries.provider")}  # fmt: skip
    files = []
    counts = {"same": 0, "different": 0, "one": 0}
    for path in _pdfs(folder):
        source = path.relative_to(folder).as_posix()
        apple = (runs["apple"] or {}).get(source)
        local = (runs["local"] or {}).get(source)
        outcome = _outcome(apple, local)
        if outcome:
            counts[outcome] += 1
        files.append({"from": source, "outcome": outcome, "apple": apple, "local": local,
                      **seen.get(source, {"ocr_pages": [], "cover": False})})  # fmt: skip
    report: dict[str, Any] = {**states, **counts, "files": files}
    if organized:
        tally = {outcome: 0 for outcome in OUTCOMES}
        for one in files:
            record = one["apple"] or one["local"] or {}
            if record.get("name") in tally:
                tally[str(record["name"])] += 1
        report["organized"] = {"counts": tally, "learned": _learn(real, folder)}
    preview = {
        "apple": _tree(runs["apple"]) if runs["apple"] is not None else None,
        "local": _tree(runs["local"]) if runs["local"] is not None else None,
        "report": report,
    }
    target = preview_path(real)
    target.write_text(json.dumps(preview, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return Prepared(target, preview, report_text(preview))


def report_text(preview: Mapping[str, Any]) -> str:
    """The readable report: the runs, the trees compared, the preprocessing, the organized names."""
    report = preview["report"]
    lines = []
    for label, title in (("apple", "Apple Intelligence"), ("local", "local")):
        state = report[label]
        lines.append(f"{title}: {state['state']}" + (
            f" ({state.get('model')}), {state['seconds']:.1f} s" if state["state"] == "ran" else ""
        ))  # fmt: skip
    lines += [f"same place: {report['same']}", f"different places: {report['different']}",
              f"filed by one: {report['one']}", ""]  # fmt: skip
    for one in report["files"]:
        apple, local = one["apple"], one["local"]
        if one["outcome"] == "different":
            lines += [f"{one['from']}:", f"  Apple: {apple['place']}", f"  local: {local['place']}"]
        else:
            shown = (apple or local or {}).get("place", "not filed")
            why = (apple or local or {}).get("why")
            lines.append(f"{one['from']}: {shown}" + (f" ({why})" if why else ""))
    told = [
        f"  {one['from']}: " + "; ".join(filter(None, [
            f"OCR on page {', '.join(map(str, one['ocr_pages']))}" if one["ocr_pages"] else "",
            "cover sheet left out for the model" if one["cover"] else "",
            "found on the second look"
            if any((one[label] or {}).get("look") == "bottom" for label in LABELS) else "",
        ]))
        for one in report["files"]
        if one["ocr_pages"] or one["cover"]
        or any((one[label] or {}).get("look") == "bottom" for label in LABELS)
    ]  # fmt: skip
    lines += ["", "preprocessing", *(told or ["  nothing beyond reading order"])]
    if "organized" in report:
        counts, learned = report["organized"]["counts"], report["organized"]["learned"]
        lines += ["", "organized names", "  " + ", ".join(f"{k}: {v}" for k, v in counts.items())]
        for one in report["files"]:
            record = one["apple"] or one["local"] or {}
            if record.get("name") == "date replaced":
                lines.append(f"  {one['from']}: {record['from_date']} → {record['to_date']}")
            elif record.get("name") in ("waiting", "no author"):
                lines.append(f"  {one['from']}: waits in Unrecognized ({record.get('why')})")
        lines += ["", "learned from the names",
                  f"  authors learned ({len(learned['authors'])}): "
                  f"{', '.join(learned['authors']) or 'none'}",
                  f"  tags learned ({len(learned['tags'])}): {', '.join(learned['tags']) or 'none'}",
                  f"  already known: {learned['already_authors']} authors, "
                  f"{learned['already_tags']} tags"]  # fmt: skip
    return "\n".join(lines) + "\n"


__all__ = [
    "OUTCOMES",
    "PREVIEW",
    "Prepared",
    "models_for",
    "prepare",
    "preview_path",
    "report_text",
]
