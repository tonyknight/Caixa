"""A stand-in embedding model, for tests: deterministic vectors in which a few words share a
meaning (`power` ≈ `electricity` ≈ `energia`, `invoice` ≈ `bill` ≈ `fatura`…), so a paraphrase
lands near the text it means while sharing none of its words.

`respond` answers OpenAI-compatible `/v1/embeddings` requests (`{"model", "input": [...]}`) for
Chattr's `StubServer`; `embed` is the same thing called directly.
"""

from __future__ import annotations

import math
import re
import unicodedata
import zlib
from typing import Any

DIMENSIONS = 64
CONCEPTS = {
    "energy": ["electricity", "electric", "power", "energia", "energy", "kwh"],
    "bill": ["bill", "invoice", "fatura", "factura", "receipt", "recibo", "amount", "due"],
    "statement": ["statement", "extrato", "balance", "saldo", "account", "conta"],
    "bank": ["bank", "banco", "atlantico", "cheque", "check"],
    "insurance": ["insurance", "seguro", "policy", "apolice", "premium", "coverage"],
    "water": ["water", "agua", "aguas", "contador", "meter"],
    "home": ["home", "house", "casa", "rent", "rental", "landlord", "tenant", "property"],
    "health": ["clinic", "clinica", "hemoglobina", "analises", "medical", "exame", "lab"],
}
_WORD = {word: index for index, words in enumerate(CONCEPTS.values()) for word in words}


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def embed(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for word in re.findall(r"[a-z0-9]+", _plain(text)):
        if word in _WORD:
            vector[_WORD[word]] += 3.0
        else:
            vector[len(CONCEPTS) + zlib.crc32(word.encode()) % (DIMENSIONS - len(CONCEPTS))] += 0.3
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def respond(request: dict[str, Any]) -> dict[str, Any]:
    texts = request["input"] if isinstance(request["input"], list) else [request["input"]]
    return {
        "object": "list",
        "model": request.get("model"),
        "data": [
            {"object": "embedding", "index": i, "embedding": embed(t)} for i, t in enumerate(texts)
        ],
    }


__all__ = ["CONCEPTS", "DIMENSIONS", "embed", "respond"]
