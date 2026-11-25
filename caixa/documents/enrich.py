"""Reading documents with a model on this computer: what each one is, who issued it, and when.

The model is the summaries' (Automatic: Apple Intelligence first, else the OpenAI-compatible
endpoint), with one rule of its own: documents never go to a service on the internet, whatever the
summaries allow (`provider`). It is given (`prepare`):

- the file name and what it says, since a filename is evidence;
- the PDF's properties without their noise, and the number of pages;
- the box's authors whose names appear in the text;
- the first two pages and the last, within what the model reads at once (Apple Intelligence
  about 6,000 characters, an endpoint 12,000).

It answers in a fixed JSON form (`SCHEMA`, version `SCHEMA_VERSION`): type and category from fixed
lists, a title, the author and the naming date with the words that show them (`evidence`) and their
page, other dates, people and organizations named, up to four tags, a 30–50-word summary, and what
the filename gets wrong. An endpoint is asked for that form directly (`response_format`); Apple
Intelligence finds it in its instructions. Caixa checks every answer (`problems`), asks once more
naming what was wrong, and checks every quote against the page it cites (`verify_quote`).

Nothing is decided here. Each answer is recorded as proposals (`document_fields`, source
`ai_inference`, with evidence, page and whether it was verified) and an `enrich` run naming the
model, the prompt and the schema. Reconciliation weighs the proposals against the filename and the
properties, and applies them.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

from chattr.translation import (
    OpenAICompatibleTranslator,
    TranslationError,
    TranslationUnavailable,
    is_local_endpoint,
)

from caixa import settings, summaries
from caixa.box import Box
from caixa.collectors.base import Progress
from caixa.documents import evidence, records
from caixa.documents import types as document_types
from caixa.documents.tags import normalize_tags, starter_tags
from caixa.naming import NamingDate, NamingError

PROMPT_VERSION = "1"
SCHEMA_VERSION = "1"
BUDGET = summaries.BUDGET
APPLE_BUDGET = summaries.APPLE_BUDGET

TYPES = [
    "statement", "cheque", "bill", "invoice", "insurance", "tax", "agreement", "property_record",
    "medical", "personal_record", "correspondence", "business", "other",
]  # fmt: skip
CATEGORIES = ["financial", "legal", "personal", "correspondence", "business", "other"]
DATE_KINDS = [
    "statement_end", "issue", "written", "tax_year", "coverage_start", "execution", "letter",
    "effective", "due", "period_start", "other",
]  # fmt: skip
MOST_TAGS = 4

_QUOTE = {"type": ["string", "null"]}
_PAGE = {"type": ["integer", "null"]}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "category", "type", "title", "author", "date", "other_dates", "people", "organizations",
        "tags", "summary", "filename_conflicts",
    ],  # fmt: skip
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "type": {"type": "string", "enum": TYPES},
        "title": {"type": "string"},
        "author": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["name", "evidence", "page"],
            "properties": {"name": {"type": "string"}, "evidence": _QUOTE, "page": _PAGE},
        },
        "date": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["value", "precision", "kind", "evidence", "page"],
            "properties": {
                "value": {"type": "string", "pattern": r"^\d{4}(-\d{2}(-\d{2})?)?$"},
                "precision": {"type": "string", "enum": ["day", "month", "year"]},
                "kind": {"type": "string", "enum": DATE_KINDS},
                "evidence": _QUOTE,
                "page": _PAGE,
            },
        },
        "other_dates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["value", "kind", "evidence", "page"],
                "properties": {
                    "value": {"type": "string"},
                    "kind": {"type": "string", "enum": DATE_KINDS},
                    "evidence": _QUOTE,
                    "page": _PAGE,
                },
            },
        },
        "people": {"type": "array", "items": {"type": "string"}},
        "organizations": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": MOST_TAGS},
        "summary": {"type": "string"},
        "filename_conflicts": {"type": "array", "items": {"type": "string"}},
    },
}
RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {"name": "caixa_document", "strict": True, "schema": SCHEMA},
}

INSTRUCTION = (
    "You read one document from a family archive and describe it as one JSON object. Use only "
    "what the document, its file name and its properties say: do not guess, add or advise. "
    "The file name is evidence too: keep what it says unless the pages contradict it, and list "
    'each contradiction in filename_conflicts (such as "year", "type" or "author"). '
    "The author is who issued, sent or wrote the document, not who it is about or addressed to. "
    "The date is the one that names the document: the end of a statement's period, the day a "
    "bill, invoice or receipt was issued, the day a cheque was written, the tax year of a tax "
    "document (year only), the start of an insurance's cover, the day an agreement was signed, "
    "the date of a letter. Give it at the precision the document gives (YYYY, YYYY-MM or "
    "YYYY-MM-DD); never invent a day or a month. For the author and each date give evidence: "
    "words copied exactly from one page, and that page's number. Write null for what the "
    "document does not say. Give at most four short tags in lower case, and a summary of 30 to "
    "50 words in the document's own language. "
    f"Types: {', '.join(TYPES)}. Categories: {', '.join(CATEGORIES)}. "
    f"Date kinds: {', '.join(DATE_KINDS)}. Answer with the JSON object alone."
)
RETRY = (
    "That answer could not be used: {reason}. Answer again with only the JSON object, in the "
    "form asked for."
)


class EnrichUnavailable(Exception):
    """No model can read documents: `reason` is `off`, `no_model`, `remote` or `unavailable`."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def provider(values: Mapping[str, Any], reading: bool = True) -> tuple[Any, dict[str, Any]]:
    """The client documents are read with, and `{provider, model, budget}`; `EnrichUnavailable`
    says why there is none. The owner's questions (`reading=False`) are answered even when reading
    at import is turned off; a model on the internet is refused either way."""
    if reading and not values.get("documents.enrich", True):
        raise EnrichUnavailable("off", "Reading documents with a model is turned off in Settings.")
    apple = summaries.apple(values)
    if not apple:
        address, name = summaries.endpoint(values), summaries.model(values)
        if not address or not name:
            raise EnrichUnavailable(
                "no_model",
                "No model is set: choose Apple Intelligence, or an endpoint and a model on this "
                "computer, in Settings, Summaries.",
            )
        if not is_local_endpoint(address):
            raise EnrichUnavailable(
                "remote",
                "The summaries' endpoint is on the internet; documents are only read by a model "
                "on this computer.",
            )
    try:
        client = summaries.client(values, timeout=300)
    except TranslationUnavailable as error:
        raise EnrichUnavailable("unavailable", str(error)) from None
    info = {
        "provider": "apple" if apple else "endpoint",
        "model": summaries.model(values),
        "budget": APPLE_BUDGET if apple else BUDGET,
    }
    return client, info


def close(client: Any) -> None:
    closing = getattr(client, "close", None)
    if callable(closing):
        closing()


# --- What is sent --------------------------------------------------------------------------------


@dataclass
class DocumentInput:
    filename: str
    properties: dict[str, str]  # as the PDF gives them (PyMuPDF's names)
    pages: list[tuple[int, str]]  # (number from 1, text)
    page_count: int
    authors: list[str] = field(default_factory=list)  # the box's authors and their aliases
    tags: list[str] = field(default_factory=list)  # the starter tags, to use when they fit


def _said_by_name(named: evidence.FilenameEvidence) -> str:
    parts = []
    if named.date is not None:
        parts.append(f"date {named.date.value} ({named.date.precision})")
    if named.author:
        parts.append(f"author {named.author}")
    if named.types:
        parts.append(f"type words: {', '.join(named.types)}")
    if named.title:
        parts.append(f'title "{named.title}"')
    if named.amounts:
        parts.append(f"amounts {', '.join(named.amounts)}")
    if named.cheque_number:
        parts.append(f"cheque {named.cheque_number}")
    if not named.informative:
        return "nothing (a name a scanner or a download gave it)"
    return "; ".join(parts) or "no date, author or type"


def _said_by_properties(stated: evidence.PropertyEvidence) -> str:
    parts = [
        f"{label}: {value}"
        for label, value in (
            ("title", stated.title), ("author", stated.author), ("subject", stated.subject),
            ("keywords", ", ".join(stated.keywords)), ("created", stated.created),
        )  # fmt: skip
        if value
    ]
    return "; ".join(parts) or "none worth reading"


def prepare(document: DocumentInput, budget: int) -> str:
    """What the model is sent about one document, within `budget` characters."""
    named = evidence.read_filename(document.filename, document.authors)
    stated = evidence.read_properties(document.properties)
    text = "\n".join(t for _, t in document.pages)
    known = [a for a in sorted(set(document.authors)) if a.strip() and evidence._find(text, a)]
    count = document.page_count
    numbers = sorted({n for n, _ in document.pages if n <= 2 or n == count})
    shown = "all of them" if len(numbers) == count else "the first two and the last are given"
    head = [
        f"File name: {document.filename}",
        f"What the file name says: {_said_by_name(named)}",
        f"PDF properties: {_said_by_properties(stated)}",
        f"Pages: {count} pages ({shown})",
    ]
    if known:
        head.append(f"Authors already in the box named in the text: {', '.join(known)}")
    if document.tags:
        head.append(f"Tags to use when they fit: {', '.join(document.tags)}")
    header = "\n".join(head) + "\n"
    texts = dict(document.pages)
    labels = {
        n: f"--- Page {n}{' (last)' if n == count and count > 1 else ''} ---" for n in numbers
    }
    room = budget - len(header) - sum(len(labels[n]) + 2 for n in numbers)
    share = max(0, room // max(1, len(numbers)))
    body = []
    for number in numbers:
        page = " ".join((texts.get(number) or "").split(" "))
        page = page.strip()
        body.append(f"{labels[number]}\n{page[:share]}")
    return (header + "\n".join(body))[:budget]


# --- The answer ----------------------------------------------------------------------------------


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()
    return " ".join(plain.split())


def verify_quote(
    quote: Optional[str], page: Optional[int], pages: Mapping[int, str]
) -> tuple[bool, Optional[int]]:
    """Whether `quote` is on `page` (on any page when none is given), accents, case and spacing
    aside; and the page it is on. A quote that is not text is never found."""
    if not isinstance(quote, (str, type(None))):
        return False, None
    wanted = _plain(quote or "")
    if len(wanted) < 2:
        return False, page
    if page is not None:
        return wanted in _plain(pages.get(page, "")), page
    for number in sorted(pages):
        if wanted in _plain(pages[number]):
            return True, number
    return False, None


def parse_answer(reply: str) -> Any:
    """The JSON object in a reply, also inside code fences or other words; `ValueError` without."""
    text = reply.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("the answer holds no JSON object") from None
        return json.loads(text[start : end + 1])


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def problems(answer: Any) -> list[str]:
    """What keeps an answer from being used, in words; empty when it can be."""
    if not isinstance(answer, dict):
        return ["it is not a JSON object"]
    found = [f"{key} is missing" for key in SCHEMA["required"] if key not in answer]
    if answer.get("category") not in CATEGORIES:
        found.append(f"category must be one of {', '.join(CATEGORIES)}")
    if answer.get("type") not in TYPES:
        found.append(f"type must be one of {', '.join(TYPES)}")
    if "title" in answer and not (isinstance(answer["title"], str) and answer["title"].strip()):
        found.append("title must be a few words")
    author = answer.get("author")
    if author is not None and not (
        isinstance(author, dict) and isinstance(author.get("name"), str)
    ):
        found.append("author must be null or {name, evidence, page}")
    found += document_types.quote_problems("author", author)
    date = answer.get("date")
    found += document_types.quote_problems("date", date)
    if date is not None:
        try:
            NamingDate.parse(str((date or {}).get("value") if isinstance(date, dict) else ""))
        except NamingError:
            found.append("date.value must be YYYY, YYYY-MM or YYYY-MM-DD")
        if isinstance(date, dict) and date.get("kind") not in DATE_KINDS:
            found.append(f"date.kind must be one of {', '.join(DATE_KINDS)}")
    for key in ("people", "organizations", "tags", "filename_conflicts"):
        if key in answer and not _strings(answer[key]):
            found.append(f"{key} must be a list of words")
    if _strings(answer.get("tags")) and len(answer["tags"]) > MOST_TAGS:
        found.append(f"tags must be at most {MOST_TAGS}")
    if "other_dates" in answer and not isinstance(answer["other_dates"], list):
        found.append("other_dates must be a list")
    if "summary" in answer and not isinstance(answer["summary"], str):
        found.append("summary must be text")
    return found


@dataclass
class Classified:
    ok: bool
    answer: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    error: Optional[str] = None
    raw: str = ""


def _checked(answer: dict[str, Any], pages: Mapping[int, str]) -> dict[str, Any]:
    """The answer with each quote verified against its page, and the date's precision as its
    value shows it."""
    author = answer.get("author")
    if isinstance(author, dict):
        author["verified"], author["page"] = verify_quote(
            author.get("evidence"), author.get("page"), pages
        )
    date = answer.get("date")
    if isinstance(date, dict):
        date["precision"] = NamingDate.parse(str(date["value"])).precision
        date["verified"], date["page"] = verify_quote(date.get("evidence"), date.get("page"), pages)
    kept = []
    for other in (
        answer.get("other_dates") or []
    ):  # supporting dates: one of the wrong shape is left out
        if (
            isinstance(other, dict)
            and other.get("value")
            and not document_types.quote_problems("other_dates", other)
        ):
            other["verified"], other["page"] = verify_quote(
                other.get("evidence"), other.get("page"), pages
            )
            kept.append(other)
    answer["other_dates"] = kept
    return answer


def ask(
    client: Any,
    instruction: str,
    prompt: str,
    schema: dict[str, Any],
    check: Callable[[Any], list[str]],
    name: str = "caixa_document",
) -> Classified:
    """Ask once, and once more naming what was wrong when the answer cannot be used. An
    endpoint is given the schema as `response_format`; any other model finds it in its
    instructions. A failing provider raises (Chattr's `TranslationError`)."""
    if not isinstance(client, OpenAICompatibleTranslator):  # no schema mode: say it in words
        instruction += "\n\nThe JSON object follows this JSON Schema:\n" + json.dumps(schema)
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": True, "schema": schema},
    }
    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": prompt},
    ]
    result = Classified(ok=False)
    for attempt in (1, 2):
        result.attempts = attempt
        reply, _ = client.chat(messages, temperature=0, response_format=response_format)
        result.raw = reply
        try:
            answer = parse_answer(reply)
            wrong = check(answer)
        except ValueError as error:
            answer, wrong = None, [str(error) or "it is not JSON"]
        if not wrong:
            result.ok, result.answer, result.error = True, answer, None
            return result
        result.error = "; ".join(wrong)
        messages += [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": RETRY.format(reason=result.error)},
        ]
    return result


def classify(client: Any, document: DocumentInput, budget: int) -> Classified:
    """Ask the model what a document is (the classification schema), its quotes verified."""
    found = ask(client, INSTRUCTION, prepare(document, budget), SCHEMA, problems)
    if found.ok:
        found.answer = _checked(found.answer, dict(document.pages))
    return found


TYPE_INSTRUCTION = (
    "You read one document from a family archive, already known to be a {kind}, and give its "
    "facts as one JSON object: {meaning}. Use only what the document says. For each fact give "
    "its value as written (dates as YYYY-MM-DD), words copied exactly from one page that show "
    "it, and that page's number; write null for what the document does not say. Answer with "
    "the JSON object alone."
)


def classify_type(client: Any, document: DocumentInput, kind: str, budget: int) -> Classified:
    """Ask for a type's fields (`caixa.documents.types`), each quote verified, amounts given a
    number read by Caixa."""
    from caixa.documents import types

    instruction = TYPE_INSTRUCTION.format(kind=kind, meaning=types.MEANINGS[kind])
    prompt = f"Document type: {kind}\n" + prepare(document, budget - 40)
    found = ask(
        client, instruction, prompt, types.TYPE_SCHEMAS[kind],
        lambda answer: types.type_problems(kind, answer),
    )  # fmt: skip
    if not found.ok:
        return found
    pages = dict(document.pages)
    for name, value in found.answer.items():
        for one in value if isinstance(value, list) else [value]:
            if not isinstance(one, dict):
                continue
            one["verified"], one["page"] = verify_quote(one.get("evidence"), one.get("page"), pages)
            if name in types.AMOUNTS:
                one["number"] = types.parse_amount(one.get("value"))
    return found


__all__ = [
    "APPLE_BUDGET", "BUDGET", "CATEGORIES", "Classified", "DATE_KINDS", "DocumentInput",
    "EnrichUnavailable", "PROMPT_VERSION", "SCHEMA", "SCHEMA_VERSION", "TYPES", "classify",
    "ask", "classify_type", "close", "enrich_documents", "parse_answer", "prepare", "problems", "provider",
    "verify_quote",
]  # fmt: skip


# --- The stage ------------------------------------------------------------------------------------

#: The types that have fields of their own (`caixa.documents.types`).
TYPE_FIELDS = set(document_types.FIELDS)
#: Review reasons that keep a document from being read (its pages cannot be opened).
UNREADABLE = ("locked",)
#: After this many documents in a row the provider failed on, the stage stops: the rest wait.
FAILURES_IN_A_ROW = 2


def _properties(fields: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """A document's properties as they were read at import (kept as `pdf_metadata` fields)."""
    names = {"title": "title", "author": "author", "subject": "subject", "keywords": "keywords"}
    found: dict[str, str] = {}
    for one in fields:
        if one["source"] != "pdf_metadata" or not one["value"]:
            continue
        if one["field"] in names:
            found[names[one["field"]]] = str(one["value"])
        elif one["field"] == "creation_date":
            found["creationDate"] = "D:" + str(one["value"]).replace("-", "")
    return found


def _input(master: Any, item_id: str) -> DocumentInput:
    found = records.get_document(master, item_id)
    pages = [
        (int(r["page"]), str(r["text"] or ""))
        for r in master.connection.execute(
            "SELECT page, text FROM document_pages WHERE item_id = ? ORDER BY page", (item_id,)
        )
    ]
    return DocumentInput(
        filename=str(found["original_filename"]),
        properties=_properties(found["fields"]),
        pages=pages,
        page_count=int(found["pages"] or len(pages)),
        authors=records.author_names(master),
        tags=starter_tags(master),
    )


def _record(master: Any, item_id: str, answer: Mapping[str, Any], run: int) -> None:
    """The model's answer as proposals, each with its evidence and whether that was verified."""

    def add(name: str, value: Any, **extra: Any) -> None:
        if value not in (None, "", []):
            records.add_field(
                master, item_id, name, str(value), "ai_inference", run_id=run, **extra
            )

    add("type", answer.get("type"))
    add("category", answer.get("category"))
    add("title", answer.get("title"))
    author = answer.get("author") or {}
    add("author", author.get("name"), evidence=author.get("evidence"), page=author.get("page"),
        verified=author.get("verified"))  # fmt: skip
    date = answer.get("date") or {}
    add("date", date.get("value"), evidence=date.get("evidence"), page=date.get("page"),
        verified=date.get("verified"))  # fmt: skip
    add("date_kind", date.get("kind"))
    for other in answer.get("other_dates") or []:
        add(f"date_{other.get('kind') or 'other'}", other.get("value"),
            evidence=other.get("evidence"), page=other.get("page"), verified=other.get("verified"))  # fmt: skip
    for name, key in (("person", "people"), ("organization", "organizations"), ("tag", "tags"),
                      ("filename_conflict", "filename_conflicts")):  # fmt: skip
        for value in answer.get(key) or []:
            add(name, value)
    add("summary", answer.get("summary"))


def _record_type(master: Any, item_id: str, answer: Mapping[str, Any], run: int) -> None:
    """A type's fields as proposals, amounts with the number Caixa read."""
    for name, value in answer.items():
        for one in value if isinstance(value, list) else [value]:
            if isinstance(one, dict) and one.get("value"):
                records.add_field(
                    master, item_id, name, str(one["value"]), "ai_inference",
                    evidence=one.get("evidence"), page=one.get("page"),
                    verified=one.get("verified"), number=one.get("number"), run_id=run,
                )  # fmt: skip


def _summary_and_tags(master: Any, item_id: str, answer: Mapping[str, Any], model: str) -> None:
    """The summary (cut at a sentence within 50 words) and the tags, applied whether or not the
    document is confident: both are always shown as the model's."""
    from dataclasses import replace

    summary = " ".join(str(answer.get("summary") or "").split())
    if summary:
        summary = summaries._cut(summary)
        record = records.load_record(master, item_id)
        records.save_document(master, replace(record, summary=summary, summary_model=model), None)
    tags = normalize_tags(answer.get("tags") or [], starter_tags(master))
    records.set_tags(master, item_id, tags, "ai_inference")


def _set_status(master: Any, item_id: str, status: str) -> None:
    from dataclasses import replace

    record = records.load_record(master, item_id)
    records.save_document(master, replace(record, ai_status=status), None)


def _chosen(master: Any, item_ids: Optional[Sequence[str]], every: bool) -> list[str]:
    rows = master.connection.execute(
        "SELECT item_id, ai_status, review FROM documents ORDER BY created_at, item_id"
    ).fetchall()
    wanted = set(item_ids or [])
    chosen = []
    for row in rows:
        if any(reason in json.loads(row["review"] or "[]") for reason in UNREADABLE):
            continue
        if wanted:
            if row["item_id"] in wanted:
                chosen.append(row["item_id"])
        elif every or row["ai_status"] in ("pending", "processing"):
            chosen.append(row["item_id"])
    return chosen


def enrich_documents(
    box: Box,
    item_ids: Optional[Sequence[str]] = None,
    every: bool = False,
    progress: Callable[[Progress], None] = lambda step: None,
) -> dict[str, Any]:
    """Read documents with the model: those named, every one (`every`), or those still waiting.
    Each is committed as it is read, so a stopped run carries on where it stopped. Without a
    model, nothing is read and `reason` and `message` say why."""
    with box.master() as master:
        chosen = _chosen(master, item_ids, every)
    result: dict[str, Any] = {
        "enriched": 0, "needs_review": 0, "failed": 0, "waiting": len(chosen), "moved": [],
    }  # fmt: skip
    moved: list[tuple[str, str]] = result["moved"]
    if not chosen:
        return result
    try:
        client, info = provider(settings.load(box))
    except EnrichUnavailable as unavailable:
        return {**result, "reason": unavailable.reason, "message": unavailable.message}
    result.update(model=info["model"], provider=info["provider"])
    in_a_row = 0
    try:
        for number, item_id in enumerate(chosen, start=1):
            if in_a_row >= FAILURES_IN_A_ROW:
                result["stopped"] = (
                    f"The model failed {in_a_row} times in a row; {len(chosen) - number + 1} "
                    "documents wait to be read later."
                )
                break
            with box.master() as master:
                document = _input(master, item_id)
                _set_status(master, item_id, "processing")
            progress(Progress("enriching", number, len(chosen), document.filename))
            found: Optional[Classified] = None
            typed: Optional[Classified] = None
            problem: Optional[str] = None
            type_problem: Optional[str] = None
            try:
                found = classify(client, document, int(info["budget"]))
            except TranslationError as failure:
                problem = str(failure)
            kind = str(found.answer.get("type")) if found is not None and found.ok else ""
            if kind in TYPE_FIELDS:
                try:
                    typed = classify_type(client, document, kind, int(info["budget"]))
                except TranslationError as failure:
                    type_problem = str(failure)
            with box.master() as master:
                if found is None:
                    status = "failed"
                elif found.ok:
                    status = "completed"
                else:
                    status, problem = "needs_review", found.error
                run = records.add_run(
                    master, item_id, "enrich", status, tool=info["provider"],
                    model=info["model"], provider=info["provider"],
                    prompt_version=PROMPT_VERSION, schema_version=SCHEMA_VERSION,
                    report={
                        "attempts": found.attempts if found else 0,
                        "error": problem,
                        "type_attempts": typed.attempts if typed else 0,
                        "type_error": typed.error if typed and not typed.ok else type_problem,
                    },
                )  # fmt: skip
                if found is not None and found.ok:
                    records.clear_fields(master, item_id, "ai_inference")
                    _record(master, item_id, found.answer, run)
                    if typed is not None and typed.ok:
                        _record_type(master, item_id, typed.answer, run)
                    _summary_and_tags(master, item_id, found.answer, str(info["model"]))
                _set_status(master, item_id, status)
                if status in ("completed", "needs_review"):
                    from caixa.documents.reconcile import reconcile_document

                    moved += reconcile_document(
                        box, master, item_id, dict(document.pages), status == "completed"
                    )
            result["enriched" if status == "completed" else status] += 1
            in_a_row = in_a_row + 1 if status == "failed" else 0
    finally:
        close(client)
    return result
