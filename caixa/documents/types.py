"""The facts each type of document holds (schema version 1), and amounts read as people write them.

After a document is classified, the model is asked for its type's fields: a statement's
institution and balances, a cheque's number and payee, a bill's provider and amount due…. Each
field is `{value, evidence, page}` (the words that show it, and their page), or null when the
document does not say. An agreement's parties are a list of them.

Money is read by Caixa, never computed by the model: `parse_amount` turns `2,310.55`, `2.104,33`,
`23,40` or `€ 1 200,00` into a number, and that number is stored beside the text as written.
"""

from __future__ import annotations

import re
from typing import Any, Optional

TYPE_SCHEMA_VERSION = "1"

FIELDS: dict[str, tuple[str, ...]] = {
    "statement": ("institution", "account_type", "account_suffix", "period_start", "period_end",
                  "opening_balance", "closing_balance"),
    "cheque": ("number", "date", "payee", "amount"),
    "bill": ("provider", "service_address", "period_start", "period_end", "amount_due", "due_date"),
    "invoice": ("vendor", "number", "date", "total"),
    "insurance": ("insurer", "policy_number", "coverage_start", "coverage_end"),
    "tax": ("issuer", "tax_year", "form"),
    "agreement": ("parties", "subject", "execution_date"),
    "correspondence": ("sender", "recipient", "date", "subject"),
}  # fmt: skip
#: Fields that hold a list of values.
LISTS = {"parties"}
#: Fields that are money.
AMOUNTS = {"opening_balance", "closing_balance", "amount", "amount_due", "total"}
#: What a type's fields mean, for the model.
MEANINGS: dict[str, str] = {
    "statement": "the bank or institution, the account's type and the last digits of its number, "
    "the first and last day of the period, and the opening and closing balances",
    "cheque": "the cheque's number, the date it was written, who it is paid to, and the amount",
    "bill": "who sent the bill, the address served, the period billed, the amount due and when it "
    "is due",
    "invoice": "who sold, the invoice or receipt number, its date and its total",
    "insurance": "the insurer, the policy number, and when the cover starts and ends",
    "tax": "who issued it, the tax year and the form's name or number",
    "agreement": "every party to it, what it is about, and when it was signed",
    "correspondence": "who wrote it, to whom, its date and what it is about",
}

_ONE = {
    "type": ["object", "null"],
    "additionalProperties": False,
    "required": ["value", "evidence", "page"],
    "properties": {
        "value": {"type": "string"},
        "evidence": {"type": ["string", "null"]},
        "page": {"type": ["integer", "null"]},
    },
}


def _schema(fields: tuple[str, ...]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(fields),
        "properties": {
            name: ({"type": "array", "items": _ONE} if name in LISTS else _ONE) for name in fields
        },
    }


TYPE_SCHEMAS: dict[str, dict[str, Any]] = {kind: _schema(names) for kind, names in FIELDS.items()}

_NUMBER = re.compile(r"[-+]?\d[\d\s.,]*")


def parse_amount(written: Optional[str]) -> Optional[float]:
    """An amount as people write it (`2,310.55`, `2.104,33`, `23,40`, `€ 1 200,00`, `$450`), as a
    number; None when there is none. The last `.` or `,` followed by two digits marks the cents."""
    if not written:
        return None
    text = str(written).strip()
    if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", text):
        return None  # a date, not an amount
    found = _NUMBER.search(text)
    if not found:
        return None
    raw = found.group(0).strip()
    sign = -1.0 if raw.startswith("-") else 1.0
    digits = raw.lstrip("+-").replace(" ", "")
    cents = re.search(r"[.,](\d{2})$", digits)
    if cents:
        whole = re.sub(r"[.,]", "", digits[: cents.start()])
        number = f"{whole or '0'}.{cents.group(1)}"
    else:
        number = re.sub(r"[.,]", "", digits)
    try:
        return sign * float(number)
    except ValueError:
        return None


def quote_problems(name: str, value: Any) -> list[str]:
    """What is wrong with the `evidence` and `page` of a fact {…, evidence, page} named `name`:
    a quote is text or null, a page a whole number or null."""
    if not isinstance(value, dict):
        return []
    found = []
    if not isinstance(value.get("evidence"), (str, type(None))):
        found.append(f"{name}.evidence must be words copied from one page, or null")
    page = value.get("page")
    if isinstance(page, bool) or not isinstance(page, (int, type(None))):
        found.append(f"{name}.page must be a page number, or null")
    return found


def type_problems(kind: str, answer: Any) -> list[str]:
    """What keeps a type's answer from being used, in words; empty when it can be."""
    if not isinstance(answer, dict):
        return ["it is not a JSON object"]
    found = []
    for name in FIELDS[kind]:
        if name not in answer:
            found.append(f"{name} is missing")
            continue
        value = answer[name]
        ones = value if name in LISTS and isinstance(value, list) else [value]
        if name in LISTS and not isinstance(value, list):
            found.append(f"{name} must be a list of {{value, evidence, page}}")
            continue
        for one in ones:
            if one is not None and not (
                isinstance(one, dict) and isinstance(one.get("value"), str)
            ):
                found.append(f"{name} must be null or {{value, evidence, page}}")
                break
            wrong = quote_problems(name, one)
            if wrong:
                found += wrong
                break
    return found


__all__ = [
    "AMOUNTS", "FIELDS", "LISTS", "MEANINGS", "TYPE_SCHEMAS", "TYPE_SCHEMA_VERSION",
    "parse_amount", "quote_problems", "type_problems",
]  # fmt: skip
