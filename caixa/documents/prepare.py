"""Read a folder of PDFs with both models, beside any box, and compare where they file.

One run preprocesses every PDF once, asks Apple Intelligence and the local model the same
question, and files each answer under the output path (Apple) and `<output> local` (the local
model). Nothing is written into a box, and the originals are only read. See D28.

With `organized` (`--organized`, D30), a file named `(YYYY-MM-DD) Subject (Author) [Tag].pdf`
(`caixa.documents.organized`) keeps the owner's name: only a date that cannot be, or that the
page clearly contradicts, is replaced, and the author both models agree on chooses the folder of a
name that has none. The decision is shared by both trees. Every file's record in the report says
which pages were read by OCR, whether a cover sheet was skipped, and which look found a fact.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from chattr.translation import OpenAICompatibleTranslator, is_local_endpoint

from caixa.documents import author_knowledge
from caixa.documents.archive import DOCUMENTS, FORMAT_FOLDERS, UNRECOGNIZED, Facts, _target
from caixa.documents.organized import OrganizedName, compatible, on_page, read_organized, with_date
from caixa.naming import NamingDate, NamingError, folder_name, free_path

_MISSING = object()
INSTRUCTION = (
    "You read one document and answer with one JSON object: "
    '{"kind", "author", "title", "date"}. '
    "The author is who issued or sent it, named on the page. Never use a software name, "
    "such as Brite:Bill, as the author. "
    "The date is the one that names the document: a bill's issue date, the end of a "
    "statement's period, a tax year, or the day a letter was written. "
    "Write it as YYYY, YYYY-MM or YYYY-MM-DD, and never invent a day. "
    "Use null for what the page does not say."
)

#: A first page this short, or saying so, is a cover in front of the document.
_COVER = re.compile(r"fax cover|transmission report|scan cover", re.IGNORECASE)


@dataclass
class Read:
    """One PDF after preprocessing, shared by both models."""

    name: str
    pages: list[str]  # reading order; a cover sheet is not among them
    ocr_pages: list[int] = field(default_factory=list)  # page numbers that were pictures of text
    cover: bool = False


def _not_words(text: str) -> bool:
    """A text layer of punctuation and digits: it looks like text and says nothing."""
    visible = [character for character in text if not character.isspace()]
    letters = sum(character.isalpha() for character in visible)
    return len(visible) >= 15 and letters < 20


def _ordered(page: object) -> str:
    return str(page.get_text(sort=True))  # type: ignore[attr-defined]


def _ocr(page: object) -> str:
    textpage = page.get_textpage_ocr(language="eng", dpi=150, full=True)  # type: ignore[attr-defined]
    return str(page.get_text(textpage=textpage, sort=True))  # type: ignore[attr-defined]


def _is_cover(text: str) -> bool:
    letters = sum(character.isalpha() for character in text)
    return bool(_COVER.search(text)) or letters < 40


def read_document(path: Path) -> Read:
    """The pages a model is shown: in reading order, with unreadable text read by OCR, and a
    cover sheet left out."""
    import pymupdf

    pages: list[str] = []
    ocr_pages: list[int] = []
    with pymupdf.open(path) as doc:
        for number, page in enumerate(doc, start=1):
            text = _ordered(page)
            if _not_words(text):
                try:
                    text = _ocr(page) or text
                except Exception:
                    pass  # the punctuation stays; the record still says OCR was needed
                ocr_pages.append(number)
            pages.append(" ".join(text.split()))
    cover = len(pages) > 1 and _is_cover(pages[0])
    if cover:
        pages = pages[1:]
    return Read(path.name, pages, ocr_pages, cover)


def prompt(document: Read, budget: int = 6000) -> str:
    """What a model is sent. The top of the first page and the bottom of the last are kept whole
    even when the rest is cut to `budget`."""
    top = document.pages[0][:500]
    bottom = document.pages[-1][-500:]
    kept = f"[top of the first page]\n{top}\n[bottom of the last page]\n{bottom}\n"
    body = "\n".join(document.pages)
    room = budget - len(kept)
    if room < 0:
        return kept[:budget]
    if len(body) > room:
        body = body[:room]
    return kept + body


def local_root(out: Path) -> Path:
    """The local model's folder, beside the one asked for: `prepared` and `prepared local`."""
    return out.with_name(out.name + " local")


def _pdfs(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf" and not path.name.startswith(".")
    )


@dataclass
class Filed:
    name: str
    look: str  # "answer" when the first reply was enough, "bottom" when the second look was
    apple_path: str = ""
    local_path: str = ""
    ocr_pages: list[int] = field(default_factory=list)
    cover: bool = False
    organized: Optional[dict[str, Any]] = None  # with --organized, what became of the name


@dataclass
class Run:
    files: list[Filed]
    apple: str  # "ran" or "not run"


def _software(name: str) -> bool:
    plain = " ".join(re.sub(r"[^a-z0-9]+", " ", name.lower()).split())
    return plain in {"brite", "brite bill", "pro api", "pro document"} or plain.startswith("brite ")


def _facts(answer: object) -> tuple[Facts, Optional[str]]:
    if not isinstance(answer, dict):
        return Facts(), None
    author = str(answer.get("author") or "").strip()
    if _software(author):
        author = ""
    kind = str(answer.get("kind") or "").strip() or None
    return (
        Facts(
            date=str(answer.get("date") or "").strip() or None,
            title=str(answer.get("title") or "").strip() or None,
            author=author or None,
        ),
        kind,
    )


def _parse(raw: str) -> tuple[Facts, Optional[str]]:
    from caixa.documents.enrich import parse_answer

    try:
        return _facts(parse_answer(raw))
    except (ValueError, TypeError):
        return Facts(), None


def _instruction(known: author_knowledge.Knowledge) -> str:
    """The shared question, plus the authors this box has accepted and the names it rejects."""
    extra = []
    if known.accepted:
        extra.append("Accepted authors: " + ", ".join(known.accepted) + ".")
    if known.rejected:
        extra.append("Never use these names: " + ", ".join(known.rejected) + ".")
    return INSTRUCTION if not extra else INSTRUCTION + " " + " ".join(extra)


def _ask(model: object, text: str, instruction: str) -> tuple[Facts, Optional[str]]:
    if model is None:
        return Facts(), None
    chat = getattr(model, "chat", None)
    if callable(chat):
        raw, _ = chat(
            [
                {"role": "system", "content": instruction},
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        return _parse(str(raw))
    answer = model(instruction + "\n" + text)  # type: ignore[operator]
    return _facts(answer)


def _taught(known: author_knowledge.Knowledge, facts: Facts, kind: Optional[str]) -> Facts:
    """A lesson replaces the author. A rejected name with no lesson is not filed."""
    if not facts.author:
        return facts
    author = author_knowledge.apply(known, facts.author, kind)
    if author == facts.author:
        return facts
    return Facts(date=facts.date, title=facts.title, author=author)


def _question(document: Read, second: bool) -> str:
    if not second:
        return f"File name: {document.name}\n" + prompt(document)
    bottom = document.pages[-1][-800:]
    return f"File name: {document.name}\nsecond look\n[bottom of the last page]\n{bottom}\n"


def _decide(
    model: object, document: Read, known: author_knowledge.Knowledge, instruction: str
) -> tuple[Facts, str]:
    found, kind = _ask(model, _question(document, False), instruction)
    found = _taught(known, found, kind)
    if found.complete:
        return found, "answer"
    again, again_kind = _ask(model, _question(document, True), instruction)
    again = _taught(known, again, again_kind)
    if again.author and not found.author:
        found = Facts(
            date=found.date or again.date, title=found.title or again.title, author=again.author
        )
    if again.date and not found.date:
        found = Facts(date=again.date, title=found.title or again.title, author=found.author)
    if again.title and not found.title:
        found = Facts(date=found.date, title=again.title, author=found.author)
    return found, "bottom" if found.complete else "answer"


def _place(root: Path, source: Path, facts: Facts) -> str:
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    relative = _target(source.name, digest, facts if facts.complete else None, "pdf")
    folder = root / DOCUMENTS / FORMAT_FOLDERS["pdf"] / relative.parent
    target = free_path(folder, relative.name, digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(source, target)
    return target.relative_to(root).as_posix()


def _place_as(root: Path, source: Path, folder: Path, filename: str) -> str:
    """Copy `source` as `filename` into `folder` (relative to the PDF folder)."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    target = free_path(root / DOCUMENTS / FORMAT_FOLDERS["pdf"] / folder, filename, digest)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(source, target)
    return target.relative_to(root).as_posix()


def _fold(text: str) -> str:
    return " ".join(text.casefold().split())


def _agreed_date(ran: list[Facts], pages: list[str]) -> Optional[str]:
    """The naming date every model that ran gives, when it is a date and the page states it."""
    dates = [facts.date for facts in ran]
    if not dates or any(not date for date in dates) or len(set(dates)) != 1:
        return None
    date = str(dates[0])
    try:
        NamingDate.parse(date)
    except NamingError:
        return None
    return date if on_page(date, pages) else None


def _agreed_author(ran: list[Facts]) -> Optional[str]:
    authors = [facts.author for facts in ran]
    if not authors or any(not author for author in authors):
        return None
    if len({_fold(str(author)) for author in authors}) != 1:
        return None
    return " ".join(str(authors[0]).split())


def _organized(name: OrganizedName, document: Read, ran: list[Facts]) -> dict[str, Any]:
    """What becomes of an organized name (D30): kept, its date replaced, or waiting. Only the date
    is ever replaced; the owner's author is never put through author knowledge."""
    record: dict[str, Any] = {"organized": "kept", "tags": list(name.tags)}
    date = name.date
    page_date = _agreed_date(ran, document.pages)
    waiting = None
    if name.impossible:
        if page_date:
            date, why = page_date, "impossible date; the page gives another"
        else:
            waiting = "impossible date, no page date to replace it"
    elif (
        page_date
        and not compatible(page_date, name.date)
        and not on_page(name.date, document.pages)
    ):
        date, why = page_date, "the page says another date, and not the name's"
    if date != name.date:
        record.update({"organized": "date replaced", "from": name.date, "to": date, "why": why})
    author = name.author
    if author:
        record["author_from"] = "name"
    else:
        author = _agreed_author(ran)
        if author:
            record["author_from"] = "models"
    filename = with_date(name.name, date) if date != name.date else name.name
    if waiting:
        record.update({"organized": "waiting", "from": name.date, "why": waiting})
        return {**record, "folder": Path(UNRECOGNIZED), "filename": filename}
    if not author:
        record.update(
            {
                "organized": "no author",
                "why": "no author in the name, and the models do not agree on one",
            }
        )
        return {**record, "folder": Path(UNRECOGNIZED), "filename": filename}
    return {**record, "folder": Path(date[:4]) / folder_name(author), "filename": filename}


def _endpoint_client(values: object) -> tuple[object, str]:
    """The endpoint and model named in Settings, even when Apple Intelligence is the one chosen
    for ordinary reading. A service on the internet is refused."""
    from caixa import summaries

    saved = values if isinstance(values, dict) else {}
    address = summaries.endpoint(saved)
    name = str(saved.get("summaries.model") or saved.get("translation.model") or "").strip()
    if not address or not name or not is_local_endpoint(address):
        return None, name
    from caixa.translation import Keys

    # The key saved for this endpoint's host, the same one summaries use. Sent only there.
    return OpenAICompatibleTranslator(address, name, api_key=Keys().get(address), timeout=300), name


def models_for(box: Path) -> tuple[object, object, str, str]:
    """Apple Intelligence, and the local endpoint's model. The box is only read."""
    from caixa import apple_intelligence, settings
    from caixa.box import Box

    local, local_name = _endpoint_client(settings.load(Box.open(box)))
    apple: object = None
    state = "not run"
    if apple_intelligence.available():
        apple = apple_intelligence.AppleIntelligence(1)
        state = "ran"
    return apple, local, state, local_name


def _from_box(box: Optional[Path]) -> tuple[object, object, str, str]:
    if box is None:
        from caixa import apple_intelligence

        if apple_intelligence.available():
            return apple_intelligence.AppleIntelligence(1), None, "ran", ""
        return None, None, "not run", ""
    return models_for(box)


def prepare(
    folder: Path,
    out: Path,
    box: Optional[Path] = None,
    *,
    apple: object = _MISSING,
    local: object = _MISSING,
    apple_available: Optional[bool] = None,
    organized: bool = False,
) -> Run:
    """File every PDF for both models. Pass `apple` and `local` (callables or chat clients) in
    tests; otherwise they are taken from `box`, which is not written. With `organized`, organized
    file names are trusted (see the module text)."""
    close_apple = False
    local_name = ""
    if apple is _MISSING and local is _MISSING:
        apple, local, state, local_name = _from_box(box)
        close_apple = apple is not None
    else:
        state = (
            "ran"
            if apple_available or (apple_available is None and apple is not None)
            else "not run"
        )
        if apple_available is False:
            apple = None
    files: list[Filed] = []
    apple_seconds = 0.0
    local_seconds = 0.0
    known = author_knowledge.Knowledge()
    if box is not None:
        from caixa.box import Box

        known = author_knowledge.load(Box.open(box))
    instruction = _instruction(known)
    read_authors: list[str] = []
    read_tags: list[str] = []
    try:
        for source in _pdfs(folder):
            document = read_document(source)
            name = read_organized(source.name) if organized else None
            look = "answer"
            paths: dict[str, str] = {}
            ran: list[Facts] = []
            for label, model, root in (
                ("apple", apple, out),
                ("local", local, local_root(out)),
            ):
                began = time.monotonic()
                if model is None:
                    facts, which = Facts(), "answer"
                else:
                    facts, which = _decide(model, document, known, instruction)
                    ran.append(facts)
                spent = time.monotonic() - began
                if label == "apple":
                    apple_seconds += spent
                else:
                    local_seconds += spent
                if model is not None and which == "bottom":
                    look = "bottom"
                if name is None:
                    paths[label] = _place(root, source, facts)
            record: Optional[dict[str, Any]] = None
            if name is not None:
                read_authors += [name.author] if name.author else []
                read_tags += name.tags
                decided = _organized(name, document, ran)
                for label, root in (("apple", out), ("local", local_root(out))):
                    paths[label] = _place_as(root, source, decided["folder"], decided["filename"])
                record = {k: v for k, v in decided.items() if k not in ("folder", "filename")}
            elif organized:
                record = {"organized": "not organized"}
            files.append(Filed(source.name, look, paths["apple"], paths["local"],
                               list(document.ocr_pages), document.cover, record))  # fmt: skip
        learned = _learn(box, read_authors, read_tags) if organized else None
        _report(out, files, state, local is not None, local_name, apple_seconds, local_seconds,
                learned)  # fmt: skip
        return Run(files, state)
    finally:
        if close_apple:
            closer = getattr(apple, "close", None)
            if callable(closer):
                closer()


def _outcome(one: Filed) -> str:
    apple_waiting = "/Unrecognized/" in f"/{one.apple_path}"
    local_waiting = "/Unrecognized/" in f"/{one.local_path}"
    if apple_waiting != local_waiting:
        return "one"
    if one.apple_path == one.local_path:
        return "same"
    return "different"


#: What can become of an organized name, in the order the report counts them.
OUTCOMES = ("kept", "date replaced", "no author", "waiting", "not organized")


def _learn(box: Optional[Path], authors: list[str], tags: list[str]) -> dict[str, Any]:
    """Add what the owner's names say to the box's author knowledge (D30): the one thing
    `prepare --organized` writes into a box."""

    def distinct(names: list[str]) -> int:
        return len({" ".join(name.casefold().split()) for name in names if name.strip()})

    if box is None:
        return {"saved": False, "authors": [], "tags": [], "read_authors": distinct(authors),
                "read_tags": distinct(tags)}  # fmt: skip
    from caixa.box import Box

    opened = Box.open(box)
    known = author_knowledge.load(opened)
    new_authors, new_tags = author_knowledge.learn_organized(known, authors, tags)
    author_knowledge.save(opened, known)
    return {"saved": True, "authors": new_authors, "tags": new_tags,
            "read_authors": distinct(authors), "read_tags": distinct(tags)}  # fmt: skip


def _organized_lines(files: list[Filed], learned: Optional[dict[str, Any]] = None) -> list[str]:
    """The report's *organized names* section: counts, then each name that was changed or waits."""
    told = [one for one in files if one.organized]
    counts = {outcome: 0 for outcome in OUTCOMES}
    for one in told:
        counts[str(one.organized["organized"])] += 1  # type: ignore[index]
    lines = ["organized names", "  " + ", ".join(f"{k}: {v}" for k, v in counts.items())]
    for one in told:
        record = one.organized or {}
        if record["organized"] == "date replaced":
            lines.append(f"  {one.name}: {record['from']} → {record['to']} ({record['why']})")
        elif record["organized"] in ("waiting", "no author"):
            replaced = f" after {record['from']} → {record['to']}" if "to" in record else ""
            lines.append(f"  {one.name}: waits in Unrecognized{replaced} ({record['why']})")
    if learned is not None:
        lines.append("")
        lines.append("learned from the names")
        if not learned["saved"]:
            lines.append("  not saved: no box was given (--box)")
        authors, tags = learned["authors"], learned["tags"]
        lines.append(f"  authors learned ({len(authors)}): {', '.join(authors) or 'none'}")
        lines.append(f"  tags learned ({len(tags)}): {', '.join(tags) or 'none'}")
        lines.append(
            f"  already known: {learned['read_authors'] - len(authors)} authors, "
            f"{learned['read_tags'] - len(tags)} tags"
        )
    return lines


def _report(
    out: Path,
    files: list[Filed],
    apple_state: str,
    local_ran: bool,
    local_name: str,
    apple_seconds: float,
    local_seconds: float,
    learned: Optional[dict[str, Any]] = None,
) -> None:
    groups: dict[str, list[Filed]] = {"same": [], "different": [], "one": []}
    for one in files:
        groups[_outcome(one)].append(one)
    lines = [
        f"Apple Intelligence: {apple_state}, {apple_seconds:.1f} s",
        f"local{f' ({local_name})' if local_name else ''}: "
        f"{'ran' if local_ran else 'not run'}, {local_seconds:.1f} s",
        f"same place: {len(groups['same'])}",
        f"different places: {len(groups['different'])}",
        f"filed by one: {len(groups['one'])}",
        "",
        "same place",
    ]
    lines += [f"  {one.apple_path}" for one in groups["same"]] or ["  none"]
    lines += ["", "different places"]
    if groups["different"]:
        for one in groups["different"]:
            lines += [f"  Apple: {one.apple_path}", f"  local: {one.local_path}"]
    else:
        lines.append("  none")
    lines += ["", "filed by one"]
    if groups["one"]:
        for one in groups["one"]:
            which = "Apple" if "/Unrecognized/" not in f"/{one.apple_path}" else "local"
            path = one.apple_path if which == "Apple" else one.local_path
            lines.append(f"  {which} only: {path}")
    else:
        lines.append("  none")
    lines += ["", "preprocessing"]
    told = [
        f"  {one.name}: "
        + "; ".join(
            filter(None, [
                f"OCR on page {', '.join(map(str, one.ocr_pages))}" if one.ocr_pages else "",
                "cover sheet skipped" if one.cover else "",
                "found on the second look" if one.look == "bottom" else "",
            ])
        )
        for one in files
        if one.ocr_pages or one.cover or one.look == "bottom"
    ]  # fmt: skip
    lines += told or ["  nothing beyond reading order"]
    if learned is not None:
        lines += ["", *_organized_lines(files, learned)]
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    records: list[dict[str, Any]] = [
        {
            "event": "diff",
            "name": one.name,
            "outcome": _outcome(one),
            "apple": one.apple_path,
            "local": one.local_path,
            "ocr_pages": list(one.ocr_pages),
            "cover": one.cover,
            "look": one.look,
            **(one.organized or {}),
        }
        for one in files
    ]
    records.append(
        {
            "event": "summary",
            "apple": apple_state,
            "local": "ran" if local_ran else "not run",
            "local_model": local_name,
            "same": len(groups["same"]),
            "different": len(groups["different"]),
            "one": len(groups["one"]),
            "apple_seconds": round(apple_seconds, 1),
            "local_seconds": round(local_seconds, 1),
        }
    )
    (out / "report.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
