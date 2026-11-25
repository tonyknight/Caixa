"""Embeddings: each passage of each document as a vector, so search can find it by meaning.

The model is the summaries' endpoint (an OpenAI-compatible server on this computer, such as LM
Studio), asked at `/v1/embeddings` with the box's `documents.embedding_model`; left empty, there is
no semantic search, and search is by words alone. As for reading, documents are never sent to a
service on the internet. (Apple's own embeddings need Caixa's Swift helper, and are for a later
step on the Mac.)

`embed_documents` cuts every document's pages into passages (`caixa.documents.passages`), asks for
their vectors in batches, and stores them normalized, as float32, with the model's name, in
`chunks`. A document whose passages already have vectors from this model is passed by, so a run
that stopped carries on, and changing the model embeds everything again.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Optional, Sequence

from chattr.translation import is_local_endpoint

from caixa import session_log, settings, summaries
from caixa.box import Box
from caixa.collectors.base import Progress
from caixa.documents.passages import split
from caixa.session_log import Document

#: Passages sent in one request.
BATCH = 16
#: After this many documents in a row the model failed on, the run stops: the rest wait.
FAILURES_IN_A_ROW = 2


class EmbeddingError(Exception):
    """The embedding model did not answer, or answered something unusable."""


class EmbeddingsUnavailable(Exception):
    """No embedding model can be asked: `reason` is `no_model`, `no_endpoint` or `remote`."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _ask(
    address: str,
    model: str,
    texts: Sequence[str],
    key: Optional[str] = None,
    timeout: float = 120,
) -> list[list[float]]:
    body = json.dumps({"model": model, "input": list(texts)}).encode("utf-8")
    request = urllib.request.Request(
        address.rstrip("/") + "/embeddings", data=body, method="POST",
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})},
    )  # fmt: skip
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            data = json.loads(answer.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise EmbeddingError(f"The embedding model could not be asked: {error}") from None
    try:
        rows = sorted(data["data"], key=lambda row: int(row.get("index", 0)))
        vectors = [[float(x) for x in row["embedding"]] for row in rows]
    except (KeyError, TypeError, ValueError) as error:
        raise EmbeddingError(f"The embedding model's answer had no vectors ({error}).") from None
    if len(vectors) != len(texts):
        raise EmbeddingError("The embedding model answered for some passages only.")
    return vectors


class _Embedder:
    """Embeds texts with one model at one address, waiting at most `timeout` seconds."""

    def __init__(self, address: str, model: str, key: Optional[str], timeout: float) -> None:
        self.address, self.model, self.key, self.timeout = address, model, key, timeout

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        return _ask(self.address, self.model, texts, self.key, self.timeout)


def embedder(
    values: Mapping[str, Any], timeout: float = 120
) -> tuple[Callable[[Sequence[str]], list[list[float]]], str]:
    """A function that embeds texts, and the model's name; `EmbeddingsUnavailable` says why not.
    A search asks with a short `timeout`, so a model that does not answer only slows it a little."""
    model = str(values.get("documents.embedding_model") or "").strip()
    if not model:
        raise EmbeddingsUnavailable("no_model", "No embedding model is set (Settings, Documents).")
    address = summaries.endpoint(values)
    if not address:
        raise EmbeddingsUnavailable(
            "no_endpoint", "Embeddings need the summaries' endpoint, on this computer."
        )
    if not is_local_endpoint(address):
        raise EmbeddingsUnavailable(
            "remote",
            "The endpoint is on the internet; documents are only embedded on this computer.",
        )
    from caixa.translation import Keys

    key = Keys().get(address)
    return _Embedder(address, model, key, timeout), model


def model_name(values: Mapping[str, Any]) -> str:
    return str(values.get("documents.embedding_model") or "").strip()


def _waiting(master: Any, model: str, item_ids: Optional[Sequence[str]]) -> list[str]:
    rows = master.connection.execute(
        "SELECT d.item_id FROM documents d WHERE EXISTS (SELECT 1 FROM document_pages p "
        "WHERE p.item_id = d.item_id AND trim(p.text) != '') AND NOT EXISTS (SELECT 1 FROM chunks c "
        "WHERE c.item_id = d.item_id AND c.embedding_model = ? AND c.embedding IS NOT NULL) "
        "ORDER BY d.created_at, d.item_id",
        (model,),
    ).fetchall()
    wanted = set(item_ids or [])
    return [str(r[0]) for r in rows if not wanted or r[0] in wanted]


def embed_documents(
    box: Box,
    item_ids: Optional[Sequence[str]] = None,
    progress: Callable[[Progress], None] = lambda step: None,
) -> dict[str, Any]:
    """Embed the documents whose passages have no vectors from the current model (see the module
    text); returns what was done, or why nothing could be."""
    import numpy as np

    result: dict[str, Any] = {"embedded": 0, "failed": 0, "documents": []}
    log = session_log.current()
    try:
        embed, model = embedder(settings.load(box))
    except EmbeddingsUnavailable as unavailable:
        log.event(
            "embed", "embedder", message=f"Nothing is embedded: {unavailable.message}",
            reason=unavailable.reason,
        )  # fmt: skip
        return {**result, "reason": unavailable.reason, "message": unavailable.message}
    result["model"] = model
    with box.master() as master:
        chosen = _waiting(master, model, item_ids)
    log.event("embed", "embedder", model=model, waiting=len(chosen))
    in_a_row = 0
    for number, item_id in enumerate(chosen, start=1):
        if in_a_row >= FAILURES_IN_A_ROW:
            result["stopped"] = f"The model failed {in_a_row} times in a row; the rest wait."
            log.event(
                "embed", "stopped", message=result["stopped"], waiting=len(chosen) - number + 1
            )
            break
        progress(Progress("embedding", number, len(chosen), item_id))
        with box.master() as master:
            pages = master.connection.execute(
                "SELECT page, text FROM document_pages WHERE item_id = ? ORDER BY page", (item_id,)
            ).fetchall()
            (name,) = master.connection.execute(
                "SELECT original_filename FROM documents WHERE item_id = ?", (item_id,)
            ).fetchone()
        doc = Document(number, len(chosen), str(name))
        passages = [
            (int(page), start, end, text)
            for page, whole in pages
            for start, end, text in split(str(whole or ""))
        ]
        began = time.monotonic()
        try:
            vectors: list[list[float]] = []
            for at in range(0, len(passages), BATCH):
                vectors += embed([p[3] for p in passages[at : at + BATCH]])
        except EmbeddingError as error:
            result["failed"] += 1
            result.setdefault("errors", []).append(str(error))
            log.event("embed", "embed", doc, passage_count=len(passages), error=str(error))
            in_a_row += 1
            continue
        log.event(
            "embed", "embed", doc, passage_count=len(passages),
            seconds=round(time.monotonic() - began, 1),
        )  # fmt: skip
        in_a_row = 0
        with box.master() as master:
            master.connection.execute("DELETE FROM chunks WHERE item_id = ?", (item_id,))
            for (page, start, end, text), vector in zip(passages, vectors):
                array = np.asarray(vector, dtype=np.float32)
                norm = float(np.linalg.norm(array)) or 1.0
                master.connection.execute(
                    "INSERT INTO chunks (item_id, page, start, end, text, embedding, embedding_model) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (item_id, page, start, end, text, (array / norm).tobytes(), model),
                )
        result["embedded"] += 1
        result["documents"].append(item_id)
    return result


__all__ = [
    "EmbeddingError", "EmbeddingsUnavailable", "embed_documents", "embedder", "model_name",
]  # fmt: skip
