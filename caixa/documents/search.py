"""Searching documents by their words and facts, over the full-text index of their pages.

Every page's text, from the PDF or from OCR, is indexed (`documents_fts`, accents ignored).
`search` finds the pages that hold every word asked for, best first. Each hit says which document
it is in (title, author, date, type, the archived file), which page, whether the text came from
OCR, and a snippet with the words marked `[like this]`. Filters narrow it by the document's facts.

What a person types is made safe by `fts_query`: "quoted phrases" stay phrases, every other word
is a quoted term (so `450.00`, `FT 2024/118` and `HZ-55120` match as the index splits them), a
trailing `*` asks for a prefix, and FTS5's own operators are just words.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional, Sequence

from caixa.documents.records import find_author
from caixa.master import Master

_PIECES = re.compile(r'"([^"]*)"|(\S+)')
#: Snippet marks and length (in words).
OPEN, CLOSE, ELLIPSIS, WORDS = "[", "]", "…", 12
#: A listing without words shows this much of a document's first page.
OPENING = 200


#: Words a question is full of that say nothing of what it asks (English and Portuguese).
COMMON = frozenset(
    "a an and any are as at be by can could de did do does for from had has have how i in is it many much "
    "its me my of on or our than that the their there these this to was we were what when where "
    "which who why will with you your um uma o os as do da dos das em no na nos nas para por "
    "com que qual quais quando quanto quanta onde foi era e se ao aos".split()
)


def fts_query(typed: str, match: str = "all") -> str:
    """An FTS5 query for what a person typed (see the module text); "" when nothing was. With
    `match="any"` (a question), a page needs only one of the words, common ones left out."""
    if match == "any":
        words = {w.casefold(): w for w in re.findall(r"\w+", typed or "")}
        return " OR ".join(
            f'"{w}"' for key, w in words.items() if len(key) > 1 and key not in COMMON
        )
    parts = []
    for phrase, word in _PIECES.findall(typed or ""):
        if phrase:
            text = phrase.strip()
            if text:
                parts.append(f'"{text}"')
            continue
        for piece in word.split('"'):
            prefix = piece.endswith("*") and len(piece.strip("*")) > 0
            piece = piece.strip("*")
            if piece:
                parts.append(f'"{piece}"' + ("*" if prefix else ""))
    return " ".join(parts)


def _start(date: str) -> str:
    return date + {4: "-01-01", 7: "-01"}.get(len(date), "")


def _end(date: str) -> str:
    return date + {4: "-12-31", 7: "-31"}.get(len(date), "")


#: A document's naming date as the first and last day it can mean (a month is all its days).
_DOC_START = (
    "CASE length(d.date) WHEN 4 THEN d.date || '-01-01' WHEN 7 THEN d.date || '-01' "
    "ELSE d.date END"
)
_DOC_END = (
    "CASE length(d.date) WHEN 4 THEN d.date || '-12-31' WHEN 7 THEN d.date || '-31' "
    "ELSE d.date END"
)
_FIELDS = (
    "d.item_id, d.title, a.name AS author, d.type, d.category, d.date, d.date_precision, "
    "d.original_filename, d.processing_status, d.ocr_status, i.file_path"
)


def _filters(
    master: Master,
    type: Optional[str],
    category: Optional[str],
    author: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    tag: Optional[str],
    status: Optional[str],
    ocr_status: Optional[str],
) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    args: list[Any] = []
    for column, value in (
        ("d.type", type), ("d.category", category), ("d.processing_status", status),
        ("d.ocr_status", ocr_status),
    ):  # fmt: skip
        if value:
            where.append(f"{column} = ?")
            args.append(value)
    if author:
        found = find_author(master, author)
        where.append("d.author_id = ?")
        args.append(found if found is not None else -1)
    if date_from:
        where.append(f"d.date IS NOT NULL AND {_DOC_END} >= ?")
        args.append(_start(date_from))
    if date_to:
        where.append(f"d.date IS NOT NULL AND {_DOC_START} <= ?")
        args.append(_end(date_to))
    if tag:
        where.append("d.item_id IN (SELECT item_id FROM document_tags WHERE tag = ?)")
        args.append(tag.casefold())
    return where, args


def search(
    master: Master,
    query: str,
    *,
    type: Optional[str] = None,
    category: Optional[str] = None,
    author: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tag: Optional[str] = None,
    status: Optional[str] = None,
    ocr_status: Optional[str] = None,
    limit: int = 50,
    embed: Optional[Callable[[Sequence[str]], list[list[float]]]] = None,
    model: Optional[str] = None,
    match: str = "all",
) -> list[dict[str, Any]]:
    """The pages that match, best first (see the module text). Without words, the documents the
    filters choose, each by its first page; without either, nothing. Given `embed` and `model`
    (the embedding model and its name), passages close in meaning join the pages found by words,
    ranked together by reciprocal rank fusion (`hybrid`). `match="any"` is for questions: a page
    needs only one of the words (`fts_query`)."""
    where, args = _filters(
        master, type, category, author, date_from, date_to, tag, status, ocr_status
    )
    matched = fts_query(query, match)
    db = master.connection
    if not matched:
        if not where:
            return []
        rows = db.execute(
            f"SELECT {_FIELDS}, COALESCE(p.page, 1) AS page, COALESCE(p.source, 'pdf') AS source, "
            f"substr(COALESCE(p.text, ''), 1, {OPENING}) AS snippet, 0.0 AS rank "
            "FROM documents d JOIN items i ON i.id = d.item_id "
            "LEFT JOIN authors a ON a.id = d.author_id "
            "LEFT JOIN document_pages p ON p.item_id = d.item_id AND p.page = 1 "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY d.date IS NULL, d.date, d.title, d.item_id LIMIT ?",
            (*args, int(limit)),
        )
        return [dict(row) for row in rows]
    rows = db.execute(
        f"SELECT {_FIELDS}, p.page, p.source, "
        f"snippet(documents_fts, 0, '{OPEN}', '{CLOSE}', '{ELLIPSIS}', {WORDS}) AS snippet, "
        "bm25(documents_fts) AS rank "
        "FROM documents_fts JOIN document_pages p ON p.id = documents_fts.rowid "
        "JOIN documents d ON d.item_id = p.item_id JOIN items i ON i.id = d.item_id "
        "LEFT JOIN authors a ON a.id = d.author_id "
        "WHERE documents_fts MATCH ?"
        + "".join(f" AND {condition}" for condition in where)
        + " ORDER BY rank, d.item_id, p.page LIMIT ?",
        (matched, *args, int(limit)),
    )
    words = [{**dict(row), "semantic": False} for row in rows]
    if embed is None or not model:
        return words
    try:
        (vector,) = embed([query])
    except Exception:  # the embedding model is not answering: search by words alone
        return words
    close = _close(master, vector, str(model), where, args, int(limit))
    return hybrid(words, close, int(limit)) if close else words


#: Reciprocal rank fusion's constant, and how close in meaning (cosine) a passage must be to count.
FUSION = 60
CLOSEST = 0.25
#: A passage shown as a snippet is cut at this many characters.
PASSAGE = 240


def _close(
    master: Master,
    vector: Sequence[float],
    model: str,
    where: list[str],
    args: list[Any],
    most: int,
) -> list[dict[str, Any]]:
    """The pages whose passages are closest in meaning to `vector`, best first, one hit a page."""
    import numpy as np

    rows = master.connection.execute(
        f"SELECT {_FIELDS}, c.page, c.text AS passage, c.embedding, "
        "COALESCE(p.source, 'pdf') AS source FROM chunks c "
        "JOIN documents d ON d.item_id = c.item_id JOIN items i ON i.id = d.item_id "
        "LEFT JOIN authors a ON a.id = d.author_id "
        "LEFT JOIN document_pages p ON p.item_id = c.item_id AND p.page = c.page "
        "WHERE c.embedding_model = ? AND c.embedding IS NOT NULL"
        + "".join(f" AND {condition}" for condition in where),
        (model, *args),
    ).fetchall()
    query = np.asarray(vector, dtype=np.float32)
    vectors = [np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]
    usable = [i for i, v in enumerate(vectors) if v.shape == query.shape]
    if not usable:
        return []
    scores = np.vstack([vectors[i] for i in usable]) @ (
        query / (float(np.linalg.norm(query)) or 1.0)
    )
    best: dict[tuple[str, int], dict[str, Any]] = {}
    for at in np.argsort(-scores):
        score = float(scores[at])
        if score < CLOSEST or len(best) >= most:
            break
        row = dict(rows[usable[int(at)]])
        key = (str(row["item_id"]), int(row["page"]))
        if key in best:
            continue
        passage = " ".join(str(row.pop("passage") or "").split())
        row.pop("embedding")
        cut = passage[:PASSAGE] + (ELLIPSIS if len(passage) > PASSAGE else "")
        best[key] = {**row, "snippet": cut, "rank": -score, "semantic": True}
    return list(best.values())


def hybrid(
    words: list[dict[str, Any]], close: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    """Pages found by words and pages found by meaning, ranked together by reciprocal rank fusion:
    a page found both ways rises, and keeps the words' snippet; a page found only by meaning has
    its passage as its snippet."""
    scores: dict[tuple[str, int], float] = {}
    hits: dict[tuple[str, int], dict[str, Any]] = {}
    for found in (words, close):
        for place, hit in enumerate(found, start=1):
            key = (str(hit["item_id"]), int(hit["page"]))
            scores[key] = scores.get(key, 0.0) + 1.0 / (FUSION + place)
            hits.setdefault(key, hit)
    ranked = sorted(scores, key=lambda key: -scores[key])[:limit]
    return [{**hits[key], "rank": -scores[key]} for key in ranked]


__all__ = ["fts_query", "hybrid", "search"]
