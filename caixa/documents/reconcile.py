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

from caixa.documents.evidence import _find
from caixa.documents.records import normalize_author
from caixa.naming import NamingDate, NamingError

#: The reasons reconciliation gives; each reading replaces the earlier ones.
REASONS = (
    "conflict:date", "conflict:type", "conflict:author", "no_date", "no_author", "no_title",
    "no_type", "unverified_date", "unverified_author", "ai_unusable",
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


def decide(
    fields: Sequence[Mapping[str, Any]],
    pages: Mapping[int, str],
    known_authors: Mapping[str, str],
    ai_ok: bool,
) -> Decision:
    """What the fields say about a document, and whether it can be applied (see the module text).
    `known_authors` maps every author's normalized name and alias to its name."""
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
    if owner_date is not None:
        decision.date = str(owner_date["value"])
        decision.date_sources = ["user_verified"]
        decision.applied.add(int(owner_date["id"]))
        date_verified = True
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
        if named_date is not None:
            written = str(named_date["value"])
            if _compatible(written, decision.date):
                if len(written) > len(decision.date):
                    decision.date = written  # the filename is more precise, and agrees
                decision.date_sources.append("original_filename")
                decision.applied.add(int(named_date["id"]))
            else:
                matches = [kind for value, kind in others if _compatible(written, value)]
                if matches:
                    decision.explained.append((written, matches[0]))
                else:
                    reasons.append("conflict:date")
                    decision.conflicts |= {int(named_date["id"]), int(model_date["id"])}
    if decision.date is None:
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
    else:
        reasons.append("no_type")
    named_types = _all(fields, "type", "original_filename")
    if decision.type and named_types and owner_type is None:
        if not any(_close(str(r["value"]), decision.type) for r in named_types):
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
    else:
        reasons.append("no_title")

    # --- the author
    owner_author = _one(fields, "author", "user_verified")
    model_author = _one(fields, "author", "ai_inference")
    named_author = _one(fields, "author", "original_filename")
    if owner_author is not None:
        decision.author = str(owner_author["value"])
        decision.applied.add(int(owner_author["id"]))
    elif model_author is not None:
        said = str(model_author["value"])
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
        if named_author is not None:
            if _same_author(str(named_author["value"]), decision.author):
                decision.applied.add(int(named_author["id"]))
            else:
                reasons.append("conflict:author")
                decision.conflicts |= {int(named_author["id"]), int(model_author["id"])}
    else:
        reasons.append("no_author")
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
    decision.reasons = reasons
    decision.confident = not reasons
    decision.applied -= decision.conflicts
    return decision


__all__ = ["CLOSE", "Decision", "REASONS", "decide"]
