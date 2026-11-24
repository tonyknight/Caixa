"""The Documents ▸ PDF view: the page that shows every document of the box by year and author.

`Documents/PDF/PDF.html` (named like the other document pages, after its folder) has a heat map
of the documents' dates, a year range, each year's authors as tiles, Unrecognized and To review,
and every document as a short entry that a filter box narrows by its words. The box's index links
to it from its sidebar (`index_links`, given to Chattr's generic slot for links).
"""

from __future__ import annotations

from typing import Any

from caixa.box import Box

#: Where the view is, relative to the box.
VIEW = "Documents/PDF/PDF.html"


def index_links(box: Box) -> list[dict[str, Any]]:
    """The links the box's index shows for documents: **Documents** ▸ **PDF (n)**, or none."""
    if not box.master_path.exists():
        return []
    with box.master(read_only=True) as master:
        try:
            (count,) = master.connection.execute(
                "SELECT COUNT(*) FROM documents WHERE format = 'pdf'"
            ).fetchone()
        except Exception:  # an older database, before documents
            return []
    if not count:
        return []
    return [{"group": "Documents", "links": [{"label": "PDF", "href": VIEW, "count": int(count)}]}]


def _plain(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", text or "")
    return " ".join(
        "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().split()
    )


def _initials(name: str) -> str:
    words = [
        w for w in name.replace(",", " ").split() if w[:1].isalpha() and len(w) > 2
    ] or name.split()
    return "".join(w[0].upper() for w in words[:2]) or "?"


def _hue(name: str) -> str:
    import zlib

    return f"hsl({zlib.crc32(name.encode('utf-8')) % 360}, 38%, 46%)"


def view_context(documents: list[dict[str, Any]], tags: dict[str, list[str]]) -> dict[str, Any]:
    """What the view page shows (paths relative to `Documents/PDF/`)."""
    import calendar
    import os
    from collections import defaultdict
    from pathlib import PurePosixPath
    from urllib.parse import quote

    from caixa.documents.evidence import TYPE_LABELS
    from caixa.documents.pages import REASONS, _when, card

    folder = PurePosixPath(VIEW).parent

    def rel(path: str) -> str:
        return quote(os.path.relpath(path, folder).replace(os.sep, "/"), safe="/()#")

    def card_link(document: dict[str, Any]) -> str:
        path = PurePosixPath(document["file_path"])
        page = path.parent / f"{path.parent.name}.html"
        return rel(str(page)) + "#d-" + str(card(document, [], path.parent)["id"])

    years: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    unrecognized: list[dict[str, Any]] = []
    days: dict[str, list[dict[str, Any]]] = defaultdict(list)
    entries, review = [], []
    for document in documents:
        path = PurePosixPath(document["file_path"])
        if path.parent.name == "Unrecognized":
            unrecognized.append(document)
        elif len(path.parts) >= 5:
            years[path.parts[2]][path.parent.name].append(document)
        if document["date"] and len(document["date"]) == 10:
            days[document["date"]].append(document)
        iso, when = _when(document["date"])
        mine = tags.get(document["item_id"], [])
        title = document["title"] or path.name  # not named yet: the file's own name
        words = _plain(" ".join(filter(None, [
            title, document["author"], document["type"], document["category"], document["date"],
            document["summary"], document["original_filename"], path.name, *mine,
        ])))  # fmt: skip
        year = (document["date"] or "")[:4]
        entries.append({
            "iso": iso, "when": when, "title": title, "card": card_link(document),
            "more": " · ".join(filter(None, [document["author"], (document["type"] or "").replace("_", " ")])),
            "tags": mine, "href": rel(document["file_path"]), "words": words, "year": year,
        })  # fmt: skip
        if document["review"]:
            review.append({
                "title": title, "href": card_link(document), "words": words, "year": year,
                "reasons": "; ".join(REASONS.get(r, r) for r in document["review"]),
            })  # fmt: skip
    entries.sort(key=lambda e: (e["iso"] is None, e["iso"] or ""), reverse=False)
    year_blocks = []
    for year in sorted(years, reverse=True):
        authors: list[dict[str, Any]] = []
        for name, members in sorted(years[year].items(), key=lambda item: item[0].casefold()):
            page = PurePosixPath(members[0]["file_path"]).parent
            words = _plain(" ".join([name, *[m["title"] or "" for m in members],
                                     *[t for m in members for t in tags.get(m["item_id"], [])]]))  # fmt: skip
            authors.append({
                "name": name, "count": len(members), "initials": _initials(name), "hue": _hue(name),
                "href": rel(str(page / f"{page.name}.html")), "words": words,
            })  # fmt: skip
        year_blocks.append(
            {"year": year, "count": sum(int(a["count"]) for a in authors), "authors": authors}
        )
    calendars = []
    for year in sorted({d[:4] for d in days}, reverse=True):
        busiest = max((len(v) for k, v in days.items() if k.startswith(year)), default=1)
        months = []
        for month in range(1, 13):
            cells = []
            for week in calendar.monthcalendar(int(year), month):
                for day in week:
                    date = f"{year}-{month:02d}-{day:02d}" if day else ""
                    found = days.get(date, [])
                    level = 0 if not found else max(1, min(4, -(-len(found) * 4 // busiest)))
                    cells.append({"day": day, "count": len(found), "level": level,
                                  "href": card_link(found[0]) if found else ""})  # fmt: skip
            months.append({"name": calendar.month_name[month], "cells": cells})
        count = sum(len(v) for k, v in days.items() if k.startswith(year))
        calendars.append({"year": year, "count": count, "months": months})
    dated = [d["date"] for d in documents if d["date"]]
    span = ""
    if dated:
        first, last = _when(min(dated))[1], _when(max(dated))[1]
        span = first if first == last else f"from {first} to {last}"
    return {
        "count": f"{len(documents)} document{'' if len(documents) == 1 else 's'}",
        "span": span,
        "home": rel("index.html"),
        "years": year_blocks,
        "years_list": sorted({d[:4] for d in dated}),
        "calendars": calendars,
        "unrecognized": (
            {"href": "Unrecognized/Unrecognized.html", "count": len(unrecognized)}
            if unrecognized
            else None
        ),
        "review": review,
        "entries": entries,
        "types": [
            {"value": kind, "label": TYPE_LABELS.get(kind, kind.replace("_", " ").capitalize())}
            for kind in sorted({d["type"] for d in documents if d["type"]})
        ],
    }


__all__ = ["VIEW", "index_links", "view_context"]
