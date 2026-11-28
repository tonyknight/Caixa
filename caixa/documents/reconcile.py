"""Reconciling what is known about a document, by Caixa's rules (not the model's), and deciding
whether it can be named and filed.

The sources of a fact are the filename, the PDF's properties, the dates written in the text, the
model and the owner (`document_fields`). The rules:

- **The owner's word wins**: a `user_verified` value is never replaced, and needs no evidence.
- **Date**: the model's naming date. The filename's date *agrees* when one is a prefix of the
  other (`2024-11` and `2024-11-30`); the more precise is kept. A different filename date is
  *explained* when it matches another date written in the document: it then describes another
  date (the property tax bill's `2023` is when it was issued, the tax year is 2022). Otherwise
  the filename contradicts the document: a `date` conflict. Filename information is never
  dropped without a contradiction.
- **Type**: the filename's type words conflict only when none of them is (close to) the model's.
- **Author**: the model's author is matched to a known author (the same name or alias, or one
  containing the other as words) and takes that name; the model's wording becomes an alias. A
  filename author that is someone else is an `author` conflict. A properties author never is:
  properties are often wrong.
- **Confident** means all of these: the model's answer was valid; type, title and date are
  present; the date is verified (its quote found on its page, or the date written in the text);
  the author is known or verified (its quote found, or its name in the text); and there is no
  conflict. Only then is a document applied: named, filed, its fields marked `applied`. Anything
  else goes to review with its reasons.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from caixa import session_log
from caixa.documents.evidence import _find
from caixa.documents.records import normalize_author
from caixa.naming import NamingDate, NamingError
from caixa.session_log import Document

#: The reasons reconciliation gives; each reading replaces the earlier ones.
REASONS = (
    "conflict:date", "conflict:type", "conflict:author", "no_date", "no_author", "no_title",
    "no_type", "unverified_date", "unverified_author", "ai_unusable", "rejected_author",
)  # fmt: skip
#: Types close enough that a filename naming one and a model the other do not conflict.
CLOSE = [{"bill", "invoice"}, {"agreement", "property_record"}, {"medical", "personal_record"}]


@dataclass
class Decision:
    confident: bool = False
    title: Optional[str] = None
    author: Optional[str] = None
    alias: Optional[str] = None  # the model's wording of a known author, kept as an alias
    author_kind: str = "organization"
    date: Optional[str] = None
    precision: Optional[str] = None
    date_kind: Optional[str] = None
    date_sources: list[str] = field(default_factory=list)
    type: Optional[str] = None
    category: Optional[str] = None
    reasons: list[str] = field(default_factory=list)
    applied: set[int] = field(default_factory=set)  # ids of the fields the decision rests on
    conflicts: set[int] = field(default_factory=set)
    explained: list[tuple[str, str]] = field(default_factory=list)  # (filename date, its kind)
    trail: list[str] = field(default_factory=list)  # what each rule found, for the session log
    #: An organized document's file name (D30, D31): the owner's, with only what may change.
    organized: Optional[str] = None


def _one(
    fields: Sequence[Mapping[str, Any]], name: str, source: str
) -> Optional[Mapping[str, Any]]:
    for row in fields:
        if row["field"] == name and row["source"] == source and row["value"]:
            return row
    return None


def _all(fields: Sequence[Mapping[str, Any]], name: str, source: str) -> list[Mapping[str, Any]]:
    return [r for r in fields if r["field"] == name and r["source"] == source and r["value"]]


def _compatible(one: str, other: str) -> bool:
    return one.startswith(other) or other.startswith(one)


def _precision(value: str) -> Optional[str]:
    try:
        return NamingDate.parse(value).precision
    except NamingError:
        return None


def _close(one: str, other: str) -> bool:
    return one == other or any({one, other} <= group for group in CLOSE)


def _words(name: str) -> str:
    return " " + re.sub(r"[^\w]+", " ", normalize_author(name)).strip() + " "


def _same_author(one: str, other: str) -> bool:
    a, b = _words(one), _words(other)
    return a == b or a in b or b in a


def _known(name: str, known: Mapping[str, str]) -> Optional[str]:
    """The known author `name` is (an alias, or a name containing one as words)."""
    exact = known.get(normalize_author(name))
    if exact:
        return exact
    for alias, canonical in sorted(known.items(), key=lambda item: -len(item[0])):
        if _same_author(name, alias):
            return canonical
    return None


def _text_dates(fields: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """Every other date the document holds: (value, kind) from the text and the model."""
    found = [
        (str(r["value"]), "other") for r in fields if r["field"] == "date_in_text" and r["value"]
    ]
    for row in fields:
        name = str(row["field"])
        if row["source"] == "ai_inference" and name.startswith("date_") and name != "date_kind":
            found.insert(0, (str(row["value"]), name.removeprefix("date_")))
    return found


def _lesson(
    knowledge: Optional[Any], author: Mapping[str, Any], kind: Optional[str]
) -> Optional[str]:
    """The author the owner's lessons give for the model's (itself when none applies), or None
    for a rejected name."""
    said = str(author["value"])
    if knowledge is None:
        return said
    from caixa.documents.author_knowledge import apply

    return apply(knowledge, said, kind)


def _decide_organized(
    fields: Sequence[Mapping[str, Any]],
    pages: Mapping[int, str],
    known_authors: Mapping[str, str],
    knowledge: Optional[Any],
    value: str,
) -> Decision:
    """An organized document (D30, D31): the owner's name is the truth. The model adds the type
    and the category; the date is replaced only when impossible, or when the model's verified
    date is not compatible with it and the name's date is nowhere on the page; a name with no
    author takes the model's verified author for its folder. The owner's corrections rewrite
    that part of the name, in their pattern."""
    from caixa.documents.organized import compatible, on_page, read_organized, rewrite, with_date

    name = read_organized(value)
    decision = Decision()
    trail = decision.trail
    reasons: list[str] = []
    if name is None:  # (cannot be: it was read at import)
        decision.reasons = ["no_title"]
        return decision
    trail.append(f"organized: the owner's name {value}")
    texts = [pages[number] for number in sorted(pages)]
    text = "\n".join(texts)
    for fact in ("type", "category"):
        chosen = _one(fields, fact, "user_verified") or _one(fields, fact, "ai_inference")
        if chosen is not None:
            setattr(decision, fact, str(chosen["value"]))
            decision.applied.add(int(chosen["id"]))
    owner_title = _one(fields, "title", "user_verified")
    decision.title = str(owner_title["value"]) if owner_title is not None else name.subject
    owner_author = _one(fields, "author", "user_verified")
    model_author = _one(fields, "author", "ai_inference")
    if owner_author is not None:
        decision.author = str(owner_author["value"])
        decision.applied.add(int(owner_author["id"]))
        trail.append(f"author: the owner's {decision.author}")
    elif name.author:
        decision.author = name.author
        trail.append(f"author: the name's {name.author}")
    elif model_author is not None:
        taught = _lesson(knowledge, model_author, decision.type)
        if taught is None:
            reasons.append("rejected_author")
            trail.append(f"author: the model's {model_author['value']} is a rejected name")
        else:
            canonical = _known(taught, known_authors)
            lesson = normalize_author(taught) != normalize_author(str(model_author["value"]))
            verified = (
                lesson or canonical is not None or bool(model_author.get("verified"))
                or _find(text, taught) is not None
            )  # fmt: skip
            if verified:
                decision.author = canonical or taught
                decision.applied.add(int(model_author["id"]))
                trail.append(f"author: none in the name; the model's {decision.author}, verified")
            else:
                reasons.append("no_author")
                trail.append(f"author: none in the name; the model's {taught} is not verified")
    else:
        reasons.append("no_author")
        trail.append("author: none in the name, and none from the model")
    owner_date = _one(fields, "date", "user_verified")
    model_date = _one(fields, "date", "ai_inference")
    page_date: Optional[str] = None
    if model_date is not None and model_date.get("verified"):
        try:
            NamingDate.parse(str(model_date["value"]))
            page_date = str(model_date["value"])
        except NamingError:
            page_date = None
    date: Optional[str] = name.date
    if owner_date is not None:
        date = str(owner_date["value"])
        decision.applied.add(int(owner_date["id"]))
        trail.append(f"date: the owner's {date}")
    elif name.impossible:
        if page_date:
            date = page_date
            trail.append(f"date: the name's {name.date} cannot be; the page's {page_date}")
        else:
            date = None
            reasons.append("no_date")
            trail.append(f"date: the name's {name.date} cannot be, and the page gives none")
    elif page_date and not compatible(page_date, name.date) and not on_page(name.date, texts):
        date = page_date
        trail.append(f"date: the page says {page_date}, and not the name's {name.date}")
    else:
        trail.append(f"date: the name's {name.date}")
    if date == page_date and model_date is not None and owner_date is None:
        decision.applied.add(int(model_date["id"]))
        kind = _one(fields, "date_kind", "ai_inference")
        decision.date_kind = str(kind["value"]) if kind is not None else None
    elif owner_date is None:
        decision.date_kind = "filename"
    decision.date = date
    if date:
        decision.precision = NamingDate.parse(date).precision
    corrected = owner_title is not None or owner_author is not None
    if date and corrected:  # the owner's own words, put where the name has them
        decision.organized = rewrite(
            name,
            date=date,
            subject=str(owner_title["value"]) if owner_title is not None else None,
            author=str(owner_author["value"]) if owner_author is not None else None,
        )
    elif date and date != name.date:
        decision.organized = with_date(value, date)
    else:
        decision.organized = value
    if decision.organized != value:
        trail.append(f"name: {decision.organized}")
    decision.reasons = reasons
    decision.confident = not reasons
    return decision


def decide(
    fields: Sequence[Mapping[str, Any]],
    pages: Mapping[int, str],
    known_authors: Mapping[str, str],
    ai_ok: bool,
    fallback_title: Optional[str] = None,
    knowledge: Optional[Any] = None,
) -> Decision:
    """What the fields say about a document, and whether it can be applied (see the module text).
    `known_authors` maps every author's normalized name and alias to its name. `knowledge` (the
    box's author knowledge, D29) puts the model's author through the owner's lessons: an
    `instead` replaces it, a rejected name leaves none (D31)."""
    named = _one(fields, "organized", "original_filename")
    if named is not None:
        return _decide_organized(fields, pages, known_authors, knowledge, str(named["value"]))
    decision = Decision()
    reasons: list[str] = []
    if not ai_ok:
        reasons.append("ai_unusable")
    text = "\n".join(pages[n] for n in sorted(pages))

    # --- the date
    owner_date = _one(fields, "date", "user_verified")
    model_date = _one(fields, "date", "ai_inference")
    named_date = _one(fields, "date", "original_filename")
    others = _text_dates(fields)
    date_verified = False
    trail = decision.trail
    if owner_date is not None:
        decision.date = str(owner_date["value"])
        decision.date_sources = ["user_verified"]
        decision.applied.add(int(owner_date["id"]))
        date_verified = True
        trail.append(f"date: the owner's {decision.date}")
    elif model_date is not None:
        decision.date = str(model_date["value"])
        decision.date_sources = ["ai_inference"]
        decision.applied.add(int(model_date["id"]))
        date_verified = bool(model_date.get("verified")) or any(
            value == decision.date for value, _ in others
        )
        kind = _one(fields, "date_kind", "ai_inference")
        decision.date_kind = str(kind["value"]) if kind else None
        if kind is not None:
            decision.applied.add(int(kind["id"]))
        trail.append(
            f"date: the model's {decision.date} ({decision.date_kind or 'no kind'}), "
            + ("verified" if date_verified else "not verified")
        )
        if named_date is not None:
            written = str(named_date["value"])
            if _compatible(written, decision.date):
                if len(written) > len(decision.date):
                    decision.date = written  # the filename is more precise, and agrees
                decision.date_sources.append("original_filename")
                decision.applied.add(int(named_date["id"]))
                trail.append(f"date: the filename's {written} agrees")
            else:
                matches = [kind for value, kind in others if _compatible(written, value)]
                if matches:
                    decision.explained.append((written, matches[0]))
                    trail.append(f"date: the filename's {written} is its {matches[0]} date")
                else:
                    reasons.append("conflict:date")
                    decision.conflicts |= {int(named_date["id"]), int(model_date["id"])}
                    trail.append(
                        f"date: the filename's {written} contradicts the model's {decision.date}"
                    )
    if decision.date is None:
        trail.append("date: none")
        reasons.append("no_date")
    elif not date_verified:
        reasons.append("unverified_date")
    decision.precision = _precision(decision.date) if decision.date else None

    # --- the type and category
    owner_type = _one(fields, "type", "user_verified")
    model_type = _one(fields, "type", "ai_inference")
    chosen_type = owner_type or model_type
    decision.type = str(chosen_type["value"]) if chosen_type else None
    if chosen_type is not None:
        decision.applied.add(int(chosen_type["id"]))
        trail.append(f"type: {decision.type} ({'the owner' if owner_type else 'the model'})")
    else:
        reasons.append("no_type")
        trail.append("type: none")
    named_types = _all(fields, "type", "original_filename")
    if decision.type and named_types and owner_type is None:
        if not any(_close(str(r["value"]), decision.type) for r in named_types):
            words = ", ".join(str(r["value"]) for r in named_types)
            trail.append(f"type: the filename's words ({words}) are not a {decision.type}")
            reasons.append("conflict:type")
            decision.conflicts |= {int(r["id"]) for r in named_types}
            if model_type is not None:
                decision.conflicts.add(int(model_type["id"]))
    category = _one(fields, "category", "user_verified") or _one(fields, "category", "ai_inference")
    decision.category = str(category["value"]) if category else None
    if category is not None:
        decision.applied.add(int(category["id"]))

    # --- the title
    title = (
        _one(fields, "title", "user_verified")
        or _one(fields, "title", "ai_inference")
        or _one(fields, "title", "original_filename")
    )
    decision.title = str(title["value"]) if title else None
    if title is not None:
        decision.applied.add(int(title["id"]))
        trail.append(f"title: {decision.title} (from {title['source']})")
    else:
        reasons.append("no_title")
        trail.append("title: none")

    # --- the author
    owner_author = _one(fields, "author", "user_verified")
    model_author = _one(fields, "author", "ai_inference")
    named_author = _one(fields, "author", "original_filename")
    if owner_author is not None:
        decision.author = str(owner_author["value"])
        decision.applied.add(int(owner_author["id"]))
        trail.append(f"author: the owner's {decision.author}")
    elif model_author is not None and _lesson(knowledge, model_author, decision.type) is None:
        reasons.append("rejected_author")  # the model's field is left as it is, not applied
        trail.append(f"author: the model's {model_author['value']} is a rejected name")
    elif model_author is not None:
        said = str(model_author["value"])
        taught = _lesson(knowledge, model_author, decision.type)
        if taught is not None and normalize_author(taught) != normalize_author(said):
            trail.append(f"author: the model's {said}, {taught} instead (author knowledge)")
            said = taught
            model_author = {**model_author, "verified": 1}  # the owner's lesson
        canonical = _known(said, known_authors)
        decision.author = canonical or said
        if canonical and normalize_author(canonical) != normalize_author(said):
            decision.alias = said
        decision.applied.add(int(model_author["id"]))
        verified = (
            canonical is not None
            or bool(model_author.get("verified"))
            or _find(text, said) is not None
        )
        if not verified:
            reasons.append("unverified_author")
        trail.append(
            f"author: the model's {said}"
            + (f", known as {canonical}" if canonical else "")
            + (", verified" if verified else ", not verified")
        )
        if named_author is not None:
            if _same_author(str(named_author["value"]), decision.author):
                decision.applied.add(int(named_author["id"]))
                trail.append(f"author: the filename's {named_author['value']} agrees")
            else:
                reasons.append("conflict:author")
                decision.conflicts |= {int(named_author["id"]), int(model_author["id"])}
                trail.append(f"author: the filename's {named_author['value']} is someone else")
    else:
        reasons.append("no_author")
        trail.append("author: none")
    if decision.author and decision.author in [
        str(r["value"]) for r in _all(fields, "person", "ai_inference")
    ]:
        decision.author_kind = "person"

    if owner_date is not None:
        reasons = [r for r in reasons if r not in ("unverified_date", "conflict:date", "no_date")]
    if owner_author is not None:
        reasons = [
            r for r in reasons if r not in ("unverified_author", "conflict:author", "no_author")
        ]
    if owner_date is not None and owner_author is not None:
        reasons = []  # the owner has said who and when: that is enough to file it
        trail.append("the owner said who and when: enough to file it")
        if decision.title is None and fallback_title:
            decision.title = fallback_title
    decision.reasons = reasons
    decision.confident = not reasons
    decision.applied -= decision.conflicts
    return decision


# --- Applying a decision ---------------------------------------------------------------------------


def known_authors(master: Any) -> dict[str, str]:
    """Every author's name and alias, normalized, to that author's name."""
    rows = master.connection.execute(
        "SELECT a.name, x.alias FROM authors a LEFT JOIN author_aliases x ON x.author_id = a.id"
    ).fetchall()
    found: dict[str, str] = {}
    for name, alias in rows:
        found[normalize_author(str(name))] = str(name)
        if alias:
            found[normalize_author(str(alias))] = str(name)
    return found


def _move(box: Any, old: str, new: str) -> None:
    import os

    source, target = box.root / old, box.root / new
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    folder, stop = source.parent, box.root / "Documents"
    while folder != stop and folder.is_relative_to(stop):
        try:
            folder.rmdir()  # only when empty
        except OSError:
            break
        folder = folder.parent


def apply_decision(
    box: Any, master: Any, item_id: str, decision: Decision
) -> list[tuple[str, str]]:
    """Record a decision: confident, the document is named and filed (its file moved; the move is
    returned for undo); otherwise its reasons join its review. Field states follow."""
    from dataclasses import replace

    from caixa.documents import records
    from caixa.documents.archive import Facts, place

    db = master.connection
    db.execute(
        "UPDATE document_fields SET state = 'proposed' WHERE item_id = ? "
        "AND source != 'user_verified' AND state IN ('applied', 'conflict')",
        (item_id,),
    )
    for ids, state in ((decision.applied, "applied"), (decision.conflicts, "conflict")):
        for one in ids:
            db.execute("UPDATE document_fields SET state = ? WHERE id = ?", (state, one))
    record = records.load_record(master, item_id)
    review = [reason for reason in record.review if reason not in REASONS]
    moves: list[tuple[str, str]] = []
    for value, kind in decision.explained:
        already = db.execute(
            "SELECT 1 FROM document_fields WHERE item_id = ? AND field = ? AND value = ? "
            "AND source = 'original_filename'",
            (item_id, f"date_{kind}", value),
        ).fetchone()
        if already is None:
            records.add_field(master, item_id, f"date_{kind}", value, "original_filename",
                              evidence=value, state="applied")  # fmt: skip
    if decision.confident:
        if decision.alias and decision.author:
            records.add_author_alias(
                master, records.author_id(master, decision.author, decision.author_kind),
                decision.alias,
            )  # fmt: skip
        relative = place(
            box, record.original_filename, record.source_sha256,
            Facts(date=decision.date, title=decision.title, author=decision.author),
            record.format, current=record.file_path, filename=decision.organized,
        )  # fmt: skip
        if relative != record.file_path:
            _move(box, record.file_path, relative)
            moves.append((record.file_path, relative))
        record = replace(
            record,
            title=decision.title, author=decision.author, author_kind=decision.author_kind,
            date=decision.date, date_precision=decision.precision, date_kind=decision.date_kind,
            type=decision.type, category=decision.category, file_path=relative,
        )  # fmt: skip
    else:
        review += [reason for reason in decision.reasons if reason not in review]
    record = replace(
        record, review=review, processing_status="needs_review" if review else "archived"
    )
    records.save_document(master, record, None)
    return moves


def reconcile_document(
    box: Any,
    master: Any,
    item_id: str,
    pages: Mapping[int, str],
    ai_ok: bool,
    doc: Optional[Document] = None,
) -> list[tuple[str, str]]:
    """Decide and apply for one document (see `decide` and `apply_decision`); the session log
    gets the decision's trail and where the document ended up."""
    from pathlib import Path

    from caixa.documents import records
    from caixa.documents.archive import UNRECOGNIZED

    document = records.get_document(master, item_id)
    from caixa.documents import author_knowledge

    decision = decide(
        document["fields"], pages, known_authors(master), ai_ok,
        fallback_title=Path(str(document["original_filename"])).stem,
        knowledge=author_knowledge.load(box),
    )  # fmt: skip
    moves = apply_decision(box, master, item_id, decision)
    record = records.load_record(master, item_id)
    doc = doc or Document(1, 1, str(document["original_filename"]))
    fields: dict[str, Any] = {"confident": decision.confident, "trail": decision.trail}
    if decision.reasons:
        fields["reasons"] = decision.reasons
    if moves:
        fields["moved_from"], fields["moved_to"] = moves[-1]
    else:
        fields["stays"] = record.file_path
    log = session_log.current()
    log.event(
        "reconcile", "decide", doc, "confident" if decision.confident else "To review", **fields
    )
    unrecognized = UNRECOGNIZED in Path(record.file_path).parts
    log.outcome(doc, "Unrecognized" if unrecognized else "filed", record.review, key=item_id)
    return moves


__all__ = [
    "CLOSE", "Decision", "REASONS", "apply_decision", "decide", "known_authors",
    "reconcile_document",
]  # fmt: skip
