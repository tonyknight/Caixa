"""The owner's corrections: an author, a date, a title or a type given by hand, and the review.

The owner's word wins (`caixa.documents.reconcile`): each value given is recorded as
`user_verified` (replacing an earlier correction of that field) and never replaced by a model
reading the document again. With an author and a date from the owner, a document waiting in
`Unrecognized/` is filed at once: renamed and moved to `<YYYY>/<Author>/`, under the best title
known or its own file name. `candidates` lists what is known about each fact, and where each value
came from, for the owner to choose from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from caixa.box import Box
from caixa.documents import author_knowledge, records
from caixa.documents.reconcile import apply_decision, decide, known_authors
from caixa.naming import NamingDate, NamingError, clean

#: The facts the owner can correct.
FIELDS = ("author", "date", "title", "type")
#: Where a value came from, in words.
SOURCES = {
    "original_filename": "the file name",
    "pdf_metadata": "the PDF's properties",
    "pdf_content": "the text",
    "ocr": "the text read by OCR",
    "ai_inference": "the model",
    "user_verified": "you",
}


class CorrectionError(ValueError):
    """A value the owner gave cannot be used (the message says why)."""


def _checked(
    author: Optional[str], date: Optional[str], title: Optional[str], type: Optional[str]
) -> dict[str, str]:
    from caixa.documents.enrich import TYPES

    values: dict[str, str] = {}
    if date is not None:
        try:
            values["date"] = NamingDate.parse(date.strip()).value
        except NamingError:
            raise CorrectionError(
                f"'{date}' is not a date Caixa can use: write YYYY, YYYY-MM or YYYY-MM-DD."
            ) from None
    if author is not None:
        values["author"] = clean(author, capitals=False)
        if not values["author"]:
            raise CorrectionError("An author needs a name.")
    if title is not None:
        values["title"] = clean(title, capitals=False)
        if not values["title"]:
            raise CorrectionError("A title needs a few words.")
    if type is not None:
        if type not in TYPES:
            raise CorrectionError(f"The type must be one of {', '.join(TYPES)}.")
        values["type"] = type
    if not values:
        raise CorrectionError(
            "There is nothing to correct: give an author, a date, a title or a type."
        )
    return values


def pages_of(master: Any, item_id: str) -> dict[int, str]:
    return {
        int(r[0]): str(r[1] or "")
        for r in master.connection.execute(
            "SELECT page, text FROM document_pages WHERE item_id = ?", (item_id,)
        )
    }


def correct(
    box: Box,
    master: Any,
    item_id: str,
    author: Optional[str] = None,
    date: Optional[str] = None,
    title: Optional[str] = None,
    type: Optional[str] = None,
) -> list[tuple[str, str]]:
    """Record the owner's values, then reconcile and apply; returns the files moved. `KeyError`
    when there is no such document, `CorrectionError` for a value that cannot be used."""
    values = _checked(author, date, title, type)
    document = records.get_document(master, item_id)
    said = next(
        (
            str(field["value"])
            for field in reversed(document["fields"])
            if field["field"] == "author" and field["source"] != "user_verified" and field["value"]
        ),
        str(document.get("author") or ""),
    )
    kind = values.get("type") or str(document.get("type") or "") or None
    for name, value in values.items():
        master.connection.execute(
            "DELETE FROM document_fields WHERE item_id = ? AND field = ? AND source = 'user_verified'",
            (item_id, name),
        )
        records.add_field(master, item_id, name, value, "user_verified", state="applied")
    fields = records.get_document(master, item_id)["fields"]
    decision = decide(
        fields,
        pages_of(master, item_id),
        known_authors(master),
        ai_ok=document["ai_status"] == "completed",
        fallback_title=Path(str(document["original_filename"])).stem,
    )
    moves = apply_decision(box, master, item_id, decision)
    if "author" in values:
        owner = next((person.name for person in master.people() if person.is_owner), None)
        known = author_knowledge.load(box)
        author_knowledge.learn_correction(known, said, values["author"], kind, owner)
        author_knowledge.save(box, known)
    return moves


def candidates(master: Any, item_id: str) -> dict[str, list[dict[str, Any]]]:
    """Each fact's candidate values, with where each came from (its source in words as `label`),
    its evidence, page and state; the owner's first, then the model's, then the rest."""
    order = [
        "user_verified",
        "ai_inference",
        "original_filename",
        "pdf_metadata",
        "ocr",
        "pdf_content",
    ]
    found: dict[str, list[dict[str, Any]]] = {name: [] for name in FIELDS}
    for row in records.get_document(master, item_id)["fields"]:
        name = "date" if row["field"] == "date_in_text" else row["field"]
        if name not in found or not row["value"]:
            continue
        if any(c["value"] == row["value"] and c["source"] == row["source"] for c in found[name]):
            continue
        found[name].append({
            "value": row["value"], "source": row["source"],
            "label": SOURCES.get(row["source"], row["source"]), "evidence": row["evidence"],
            "page": row["page"], "state": row["state"],
        })  # fmt: skip
    for name in found:
        found[name].sort(key=lambda c: order.index(c["source"]) if c["source"] in order else 9)
    return found


__all__ = ["CorrectionError", "FIELDS", "SOURCES", "candidates", "correct", "pages_of"]
