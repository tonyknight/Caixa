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


__all__ = ["VIEW", "index_links"]
