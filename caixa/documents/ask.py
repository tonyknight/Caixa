"""Ask the documents: a question answered by the local model from passages Caixa found, citing
each passage it uses as `[n]`.

1. **Retrieval.** The question is searched with any of its words (`search(match="any")`), by
   meaning too when an embedding model is set. The best pages give one passage each, the one on
   the page sharing most of the question's words, or the closest in meaning: four for Apple
   Intelligence, which reads little, eight for a model at an endpoint.
2. **The answer.** The model reads the numbered passages, within its budget, and answers with
   a JSON object `{found, answer}`, citing passages as `[n]`.
3. **The check.** A found answer must cite at least one passage, and every number it cites must
   be a passage it was given; otherwise it is refused and not shown. The answer comes back with
   the passages it cites (document, page, the file) and the model that wrote it, so whoever shows
   it says it is a model's, and every citation opens its PDF at its page.

As for reading, only a model on this computer is asked; nothing asked or answered is logged.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

from chattr.translation import TranslationError

from caixa import settings
from caixa.box import Box
from caixa.documents import embeddings, enrich
from caixa.documents.passages import split
from caixa.documents.search import COMMON, search
from caixa.master import Master

#: How many passages each provider reads.
COUNT = {"apple": 4, "endpoint": 8}
#: How long the question's words wait for the embedding model.
EMBED_WAIT = 10

INSTRUCTION = (
    "You answer a question about a family's documents using only the numbered passages given. "
    "After each thing you say, cite the passage that says it by its number in square brackets, "
    "like [2]. Never cite a number that was not given. If the passages do not hold the answer, "
    "set found to false and say so in one sentence. Answer in the language of the question, in "
    "at most 120 words, as one JSON object: "
    '{"found": true or false, "answer": "the answer, with its citations"}.'
)
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"found": {"type": "boolean"}, "answer": {"type": "string"}},
    "required": ["found", "answer"],
    "additionalProperties": False,
}
_CITED = re.compile(r"\[(\d+)\]")


@dataclass
class Passage:
    """A numbered passage of one page of one document."""

    n: int
    item_id: str
    title: Optional[str]
    author: Optional[str]
    date: Optional[str]
    page: int
    source: str
    file_path: str
    original_filename: str
    passage: str

    def label(self) -> str:
        return ", ".join(
            filter(None, [self.title or self.original_filename, self.author, self.date])
        ) + (f", page {self.page}")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.casefold()) if len(w) > 1 and w not in COMMON}


def _best_passage(
    master: Master,
    hit: Mapping[str, Any],
    question: str,
    vector: Optional[Callable[[], Optional[Sequence[float]]]],
    model: Optional[str],
) -> str:
    """The passage of the hit's page that answers best: by meaning when found by meaning and its
    vectors exist, else the one sharing most of the question's words."""
    db = master.connection
    if hit.get("semantic") and vector is not None and model:
        import numpy as np

        rows = db.execute(
            "SELECT text, embedding FROM chunks WHERE item_id = ? AND page = ? "
            "AND embedding_model = ? AND embedding IS NOT NULL",
            (hit["item_id"], hit["page"], model),
        ).fetchall()
        query = vector()
        if rows and query is not None:
            wanted = np.asarray(query, dtype=np.float32)
            scored = [
                (float(np.frombuffer(blob, dtype=np.float32) @ wanted), str(text))
                for text, blob in rows
                if len(blob) == wanted.nbytes
            ]
            if scored:
                return max(scored, key=lambda pair: pair[0])[1]
    row = db.execute(
        "SELECT text FROM document_pages WHERE item_id = ? AND page = ?",
        (hit["item_id"], hit["page"]),
    ).fetchone()
    pieces = [piece for _, _, piece in split(str(row[0] if row else ""))]
    if not pieces:
        return ""
    asked = _words(question)
    return max(pieces, key=lambda piece: len(asked & _words(piece)))  # the first, on a tie


def retrieve(
    master: Master,
    question: str,
    count: int,
    embed: Optional[Callable[[Sequence[str]], list[list[float]]]] = None,
    model: Optional[str] = None,
) -> list[Passage]:
    """The passages for a question, numbered from 1, one for each of the best `count` pages."""
    asked: dict[str, Optional[Sequence[float]]] = {}

    def once(texts: Sequence[str]) -> list[list[float]]:  # the question is embedded only once
        if embed is None:
            raise embeddings.EmbeddingError("no model")
        if "v" not in asked:
            try:
                asked["v"] = embed(texts)[0]
            except Exception:
                asked["v"] = None
        if asked["v"] is None:
            raise embeddings.EmbeddingError("no answer")
        return [list(asked["v"])]

    hits = search(
        master, question, match="any", limit=count,
        embed=once if embed is not None else None, model=model,
    )  # fmt: skip
    found: list[Passage] = []
    for hit in hits:
        text = _best_passage(master, hit, question, lambda: asked.get("v"), model)
        if not text.strip():
            continue
        found.append(Passage(
            n=len(found) + 1, item_id=hit["item_id"], title=hit["title"], author=hit["author"],
            date=hit["date"], page=int(hit["page"]), source=str(hit["source"] or "pdf"),
            file_path=hit["file_path"], original_filename=hit["original_filename"],
            passage=" ".join(text.split()),
        ))  # fmt: skip
    return found


def prompt(question: str, passages: Sequence[Passage], budget: int) -> str:
    """What the model reads: the question, then each passage under its number and label, every
    passage cut to its share of the budget."""
    head = f"Question: {question.strip()}\n\nPassages:\n"
    labels = [f"\n[{p.n}] {p.label()}\n" for p in passages]
    room = budget - len(head) - sum(len(label) + 1 for label in labels)
    share = max(0, room // max(1, len(passages)))
    body = "".join(
        label + (p.passage if len(p.passage) <= share else p.passage[: max(0, share - 1)] + "…")
        + "\n"
        for label, p in zip(labels, passages)
    )  # fmt: skip
    return (head + body)[:budget]


def check(answer: Any, count: int) -> list[str]:
    """What is wrong with an answer to `count` passages (nothing, when it can be shown)."""
    if not isinstance(answer, dict):
        return ["it is not a JSON object"]
    if not isinstance(answer.get("found"), bool) or not isinstance(answer.get("answer"), str):
        return ['it needs "found" (true or false) and "answer" (text)']
    cited = [int(n) for n in _CITED.findall(answer["answer"])]
    wrong = sorted({n for n in cited if not 1 <= n <= count})
    if wrong:
        named = ", ".join(f"[{n}]" for n in wrong)
        return [f"it cites {named}, a passage it was not given; cite only [1] to [{count}]"]
    if answer["found"] and not cited:
        return ["it cites no passage; cite each passage it uses as [n]"]
    return []


def _said(question: str, **more: Any) -> dict[str, Any]:
    return {"question": question, "found": False, "answer": "", "citations": [], **more}


def ask_documents(
    box: Box, question: str, values: Optional[Mapping[str, Any]] = None
) -> dict[str, Any]:
    """Answer a question from the box's documents (see the module text). When no model can be
    asked, `reason` and `message` say why; a refused answer has `refused` and its reason."""
    question = " ".join((question or "").split())
    if not question:
        return _said(question, message="Nothing was asked.")
    values = values if values is not None else settings.load(box)
    try:
        client, info = enrich.provider(values, reading=False)
    except enrich.EnrichUnavailable as unavailable:
        return _said(question, reason=unavailable.reason, message=unavailable.message)
    try:
        try:
            embed, model = embeddings.embedder(values, timeout=EMBED_WAIT)
        except embeddings.EmbeddingsUnavailable:
            embed, model = None, None
        count = COUNT[info["provider"]]
        with box.master(read_only=True) as master:
            passages = retrieve(master, question, count, embed, model)
        if not passages:
            return _said(question, message="No page holds any of the question's words.")
        written_by = {"provider": info["provider"], "model": info["model"]}
        try:
            result = enrich.ask(
                client, INSTRUCTION, prompt(question, passages, int(info["budget"])), SCHEMA,
                lambda answer: check(answer, len(passages)), name="caixa_ask",
            )  # fmt: skip
        except TranslationError as error:
            return _said(question, reason="failed", message=f"The model could not answer: {error}")
    finally:
        enrich.close(client)
    if not result.ok:
        return _said(
            question, refused=True, written_by=written_by, passages=len(passages),
            message=f"The model's answer was not shown: {result.error}.",
        )  # fmt: skip
    answer = result.answer
    numbers = list(dict.fromkeys(int(n) for n in _CITED.findall(answer["answer"])))
    by_number = {p.n: p for p in passages}
    return {
        "question": question,
        "found": bool(answer["found"]),
        "answer": answer["answer"].strip(),
        "citations": [asdict(by_number[n]) for n in numbers],
        "written_by": written_by,
        "passages": len(passages),
    }


__all__ = ["COUNT", "Passage", "ask_documents", "check", "prompt", "retrieve"]
