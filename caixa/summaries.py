"""Summaries of mail conversations, written by a model the person chose, after an import.

Each conversation imported through the mail workflow gets a summary of 30–50 words, in its own
language, shown on the person pages and marked as written by a model. This module is to summaries
what `caixa.translation` is to translation, and shares its client (Chattr's OpenAI-compatible
client), its key (kept outside the box, sent only to the host it was saved for) and its rule: a
service on the internet is used only when the person has also ticked "allow", because it means
mail text leaves the computer.

- the box's settings say whether summaries are on, and name the endpoint and the model (empty:
  translation's);
- `prepare` turns a conversation into what is sent: its mails in date order without quoted earlier
  mail or signatures, within `BUDGET` characters;
- `summarize` asks for the summary and holds the answer to 30–50 words;
- `check` sends a fixed synthetic conversation (never anything from the box).
"""

from __future__ import annotations

import re
import time
from typing import Any, Mapping, NamedTuple, Optional, Sequence
from urllib.parse import urlparse

from chattr.translation import (
    OpenAICompatibleTranslator,
    TranslationError,
    TranslationUnavailable,
    is_local_endpoint,
)

from caixa.translation import LOCAL_WORKERS, REMOTE_WORKERS, Keys

__all__ = ["Keys", "Mail", "BUDGET", "SAMPLE"]

#: The most characters of a conversation sent; a longer one sends its first mails and its last.
BUDGET = 12_000
MIN_WORDS, MAX_WORDS = 30, 50

INSTRUCTION = (
    "You summarize an email conversation for a family archive. Write one summary of 30 to 50 "
    "words, in the language the conversation is written in (if it uses several, the language "
    "most of it uses). Say who wrote to whom and what it is about, using only what the mails "
    "say: do not guess, add or advise. Answer with the summary alone, as plain sentences, with "
    "no heading, list or quotation marks."
)
RETRY = "That was {count} words. Write it again in between 30 and 50 words."


class Mail(NamedTuple):
    sender: str
    date: str  # as the summary should see it, such as 2025-01-15
    text: str


#: What `check` sends: a short made-up conversation (the synthetic family), nothing from a box.
SAMPLE = (
    Mail(
        "Ana Costa",
        "2025-01-15",
        "Olá Maria! O casamento é a 14 de junho, em Sintra. Podes trazer a sobremesa? "
        "A Inês fica com as flores.",
    ),
    Mail(
        "Maria Costa",
        "2025-01-16",
        "Claro! Levo o bolo de laranja da avó. Precisas de ajuda com as mesas no sábado?",
    ),
    Mail("Ana Costa", "2025-01-16", "Sim, por favor. Às nove na quinta. Obrigada!"),
)

_QUOTE_START = re.compile(
    r"^(>|On .{0,200} wrote:$|Em .{0,200} escreveu:$|El .{0,200} escribió:$|"
    r"-{2,} ?Original Message ?-{2,}|-{2,} ?Forwarded message ?-{2,}|From: .+)",
    re.I,
)
_SENTENCE_END = re.compile(r"[.!?…](?:[\"'”’)\]]*)(?=\s|$)")


# --- Settings -------------------------------------------------------------------------------------


def endpoint(values: Mapping[str, Any]) -> str:
    return str(values.get("summaries.endpoint") or values.get("translation.endpoint") or "").strip()


def model(values: Mapping[str, Any]) -> str:
    return str(values.get("summaries.model") or values.get("translation.model") or "").strip()


def _allowed(values: Mapping[str, Any]) -> bool:
    """A service on the internet: the summaries' own yes (or translation's, for the endpoint it
    lends them)."""
    if is_local_endpoint(endpoint(values)):
        return True
    if values.get("summaries.allow_remote"):
        return True
    own = str(values.get("summaries.endpoint") or "").strip()
    return not own and bool(values.get("translation.allow_remote"))


def ready(values: Mapping[str, Any]) -> bool:
    """Whether summaries are on and can be asked for."""
    return bool(values.get("summaries.enabled")) and not problems(values) and bool(model(values))


def problems(values: Mapping[str, Any]) -> list[str]:
    """What is wrong with the summary settings, in words; empty when they can be saved."""
    if not values.get("summaries.enabled"):
        return []
    address = endpoint(values)
    if not address:
        return ["Summaries are on but have no endpoint. Give one (or translation's), or turn "
                "summaries off."]  # fmt: skip
    parsed = urlparse(address)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return [f"Summaries endpoint: '{address}' is not a web address. It should look like "
                "http://localhost:11434/v1 or https://openrouter.ai/api/v1."]  # fmt: skip
    found = []
    if not _allowed(values):
        found.append(
            f"Summaries endpoint: {parsed.hostname} is on the internet, so mail text would leave "
            "this computer. Tick 'Allow a service on the internet' for summaries to agree to "
            "that, or use an address on this computer."
        )
    if not model(values):
        found.append("Summaries are on but have no model. Give one, or turn summaries off.")
    return found


def workers(values: Mapping[str, Any]) -> int:
    return LOCAL_WORKERS if is_local_endpoint(endpoint(values)) else REMOTE_WORKERS


def client(
    values: Mapping[str, Any],
    keys: Optional[Keys] = None,
    key: Optional[str] = None,
    timeout: float = 120,
) -> OpenAICompatibleTranslator:
    """The client these settings describe (raises `TranslationUnavailable` saying why not)."""
    address, name = endpoint(values), model(values)
    parsed = urlparse(address)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise TranslationUnavailable("Give the endpoint's address first, such as http://…/v1.")
    if not name:
        raise TranslationUnavailable("Give the model's name first.")
    chosen = (key or "").strip() or (keys or Keys()).get(address)
    made = OpenAICompatibleTranslator(address, name, api_key=chosen or None, timeout=timeout)
    made.server_name = "summary server"
    return made


# --- What is sent ---------------------------------------------------------------------------------


def own_words(text: str) -> str:
    """A mail's own text: without the earlier mail it quotes or forwards, and without its
    signature (from a `-- ` line)."""
    kept: list[str] = []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if line.rstrip() == "--" or line == "-- " or _QUOTE_START.match(stripped):
            break
        kept.append(line)
    return re.sub(r"\s+", " ", " ".join(kept)).strip()


def prepare(mails: Sequence[Mail]) -> str:
    """The conversation as it is sent: a line per mail, in date order, within `BUDGET`."""
    lines = [f"{m.sender}, {m.date}: {own_words(m.text)}" for m in mails]
    lines = [line for line in lines if not line.endswith(": ")] or lines[:1]
    if sum(len(line) + 1 for line in lines) <= BUDGET:
        return "\n".join(lines)
    half = BUDGET // 2 - 60
    first: list[str] = []
    used = 0
    for line in lines:
        if used + len(line) + 1 > half:
            break
        first.append(line)
        used += len(line) + 1
    last: list[str] = []
    used = 0
    for line in reversed(lines[len(first) :]):
        if used + len(line) + 1 > half:
            break
        last.insert(0, line)
        used += len(line) + 1
    if not first:  # one very long mail: its beginning
        first = [lines[0][:half]]
    if not last and len(lines) > 1:
        last = [lines[-1][:half]]
    left = len(lines) - len(first) - len(last)
    gap = [f"[{left} mails left out]"] if left > 0 else []
    return "\n".join(first + gap + last)[:BUDGET]


# --- The answer -----------------------------------------------------------------------------------


def _count(text: str) -> int:
    return len(text.split())


def _cut(text: str) -> str:
    """At most `MAX_WORDS` words: up to the last sentence end within them, else the first 50."""
    words = text.split()
    if len(words) <= MAX_WORDS:
        return text
    within = " ".join(words[:MAX_WORDS])
    ends = [m.end() for m in _SENTENCE_END.finditer(within)]
    if ends and _count(within[: ends[-1]]) >= MIN_WORDS // 2:
        return within[: ends[-1]].strip()
    return within


def _clean(reply: str) -> str:
    text = re.sub(r"\s+", " ", reply).strip()
    text = re.sub(r"^(summary|resumo|resumen)\s*:\s*", "", text, flags=re.I)
    return text.strip("\"“”'").strip()


def summarize(chosen: OpenAICompatibleTranslator, conversation: str) -> str:
    """The summary of a conversation already `prepare`d: asked once, asked again once when it is
    not 30–50 words, then cut at a sentence when still too long (too short is kept)."""
    messages = [
        {"role": "system", "content": INSTRUCTION},
        {"role": "user", "content": "The conversation:\n\n" + conversation},
    ]
    reply, _ = chosen.chat(messages, temperature=0.2)
    text = _clean(reply)
    if MIN_WORDS <= _count(text) <= MAX_WORDS:
        return text
    messages += [
        {"role": "assistant", "content": reply},
        {"role": "user", "content": RETRY.format(count=_count(text))},
    ]
    again, _ = chosen.chat(messages, temperature=0.2)
    second = _clean(again)
    if MIN_WORDS <= _count(second) <= MAX_WORDS:
        return second
    return _cut(second) if second else _cut(text)


def check(
    values: Mapping[str, Any], keys: Optional[Keys] = None, key: Optional[str] = None
) -> dict[str, Any]:
    """Summarize the made-up `SAMPLE` and say what came back: `{ok, summary, words, seconds,
    local, used_key}` or `{ok: False, message}`. Nothing from the box is sent."""
    try:
        chosen = client(values, keys, key, timeout=90)
        chosen.retries = 0  # a person is waiting for the answer
        started = time.monotonic()
        summary = summarize(chosen, prepare(SAMPLE))
    except TranslationError as error:
        return {"ok": False, "message": str(error)}
    return {
        "ok": True,
        "summary": summary,
        "words": _count(summary),
        "seconds": round(time.monotonic() - started, 1),
        "local": is_local_endpoint(endpoint(values)),
        "used_key": bool(chosen.api_key),
    }
