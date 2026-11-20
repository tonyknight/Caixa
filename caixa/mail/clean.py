"""Cleaning: finding the junk in an mbox without losing what matters.

Cleaning is aggressive about junk and careful about everything else. A mail is **flagged** by what
gives bulk mail away (its list headers, a mass-mail service's markers, Gmail's labels and
categories, a no-reply sender, an unsubscribe link) and **protected** by what says it matters (the
owner sent it or wrote to its sender or in its thread, its sender is a person in the box, it reads
like a receipt or an order, or the owner kept its sender). Only a flagged mail with no protection is
left out of a Cleaned mbox.

The wording below is matched in English, Portuguese and Spanish (the languages of the project's
first archive and of its fixtures). A receipt is recognised by phrases rather than single words
where a single word would catch too much (an "order" in "in order to").
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from email.message import EmailMessage, Message
from typing import TYPE_CHECKING, Any, Iterable, Optional

from chattr.parsers.mbox_parser import html_to_text

if TYPE_CHECKING:
    from caixa.mail.index import MailIndex

#: An unsubscribe link or line, in a mail's text.
UNSUBSCRIBE = re.compile(
    r"unsubscribe|\bopt[ -]?out\b|manage (?:your )?(?:e-?mail )?(?:preferences|subscriptions)"
    r"|cancelar (?:a |la |sua |tu )?(?:subscri[çc][ãa]o|suscripci[óo]n|inscri[çc][ãa]o)"
    r"|anular a subscri[çc][ãa]o|descadastr|deixar de receber"
    r"|\bdar(?:se|te|me)? de baja\b|\bdate de baja\b|no (?:deseas|desea|quieres) recibir",
    re.IGNORECASE,
)

#: A receipt, an order, an invoice, a payment, a shipment, a booking or a ticket.
RECEIPT = re.compile(
    r"\b(?:your order|order (?:#|no\.?|number|confirmation|confirmed)|has (?:been )?shipped"
    r"|shipping confirmation|receipt|invoice|your payment|payment (?:received|confirmation)"
    r"|e-?ticket|booking|reservation|itinerary"
    r"|fatura|factura|recibo|encomenda|(?:o )?seu pedido|reserva|bilhete|pagamento"
    r"|tu pedido|su pedido|confirmaci[óo]n de (?:pedido|compra)|billete|\bpago\b)",
    re.IGNORECASE,
)


def _text_of(part: Message) -> str:
    try:
        content = part.get_content() if isinstance(part, EmailMessage) else part.get_payload()
    except (LookupError, UnicodeError, ValueError, KeyError, AssertionError):
        payload = part.get_payload(decode=True)
        content = payload.decode("utf-8", "replace") if isinstance(payload, bytes) else ""
    text = str(content or "")
    return html_to_text(text) if part.get_content_type() == "text/html" else text


def body_text(message: EmailMessage) -> str:
    """A mail's readable text: its plain part and its HTML part as text (either may be missing)."""
    found = []
    for kind in ("plain", "html"):
        try:
            part = message.get_body(preferencelist=(kind,))
        except (LookupError, UnicodeError, ValueError, KeyError, IndexError):
            part = None
        if part is not None:
            found.append(_text_of(part))
    return "\n".join(found)


#: Words one of which every match of UNSUBSCRIBE / RECEIPT contains (lower case): a quick look for
#: them first spares most mails the slower search.
UNSUBSCRIBE_HINTS = ("unsubscribe", "opt", "manage", "cancelar", "anular", "descadastr",
                     "deixar de receber", "baja", "recibir")  # fmt: skip
RECEIPT_HINTS = ("order", "shipped", "shipping", "receipt", "invoice", "payment", "ticket",
                 "booking", "reservation", "itinerary", "fatura", "factura", "recibo",
                 "encomenda", "pedido", "reserva", "bilhete", "pagamento", "confirmaci",
                 "billete", "pago")  # fmt: skip


def text_signals(text: str, subject: str) -> tuple[bool, bool]:
    """(a mail's text has an unsubscribe link, it reads like a receipt or an order)."""
    lowered = text.lower()
    unsubscribe = any(h in lowered for h in UNSUBSCRIBE_HINTS) and bool(UNSUBSCRIBE.search(text))
    both = f"{subject}\n{text}"
    receipt = any(h in both.lower() for h in RECEIPT_HINTS) and bool(RECEIPT.search(both))
    return unsubscribe, receipt


# --- Classifying an indexed source -------------------------------------------------------------

#: The cleaning groups, in the order the Clean mail window lists them.
GROUPS = ("lists", "notices", "unsubscribe", "spam_trash", "receipts")
LABELS = {
    "lists": "Lists and newsletters",
    "notices": "Notices and no-reply",
    "unsubscribe": "Unsubscribe links",
    "spam_trash": "Spam and Trash",
    "receipts": "Receipts and orders (kept)",
}
#: The group each flag puts a mail in.
FLAG_GROUP = {
    "spam": "spam_trash",
    "trash": "spam_trash",
    "list-headers": "lists",
    "bulk": "lists",
    "mass-mail": "lists",
    "promotions": "lists",
    "forums": "lists",
    "auto-submitted": "notices",
    "no-reply": "notices",
    "updates": "notices",
    "social": "notices",
    "unsubscribe": "unsubscribe",
}
#: The strongest group first: a mail with flags of several groups goes in the first.
STRENGTH = ("spam_trash", "lists", "notices", "unsubscribe")
LIST_HEADERS = ("list-id", "list-post", "list-unsubscribe")
MASS_MAIL = ("feedback-id", "x-campaign", "x-campaignid", "x-mc-user", "x-sg-eid", "x-mailgun-sid",
             "x-ses-outgoing")  # fmt: skip
CATEGORY_FLAGS = {
    "category promotions": "promotions",
    "category forums": "forums",
    "category updates": "updates",
    "category social": "social",
}
NO_REPLY = re.compile(
    r"^(?:no-?reply|do-?not-?reply|donotreply|notifications?|notify|mailer-daemon|postmaster"
    r"|bounces?|alerts?)(?:[+._-].*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SenderRow:
    name: str
    address: str
    mails: int
    size: int


@dataclass(frozen=True)
class Group:
    key: str
    label: str
    senders: int
    mails: int
    size: int
    rows: tuple[SenderRow, ...]


def flags_of(
    sender: Optional[str], labels: Iterable[str], signals: dict[str, str], unsubscribe: bool
) -> list[str]:
    """What gives a mail away as bulk mail, in a fixed order."""
    found: list[str] = []
    named = {label.strip().lower() for label in labels}
    if "spam" in named:
        found.append("spam")
    if "trash" in named:
        found.append("trash")
    if any(h in signals for h in LIST_HEADERS):
        found.append("list-headers")
    if signals.get("precedence", "").strip().lower() in ("bulk", "list", "junk"):
        found.append("bulk")
    if any(h in signals for h in MASS_MAIL):
        found.append("mass-mail")
    found += [flag for label, flag in CATEGORY_FLAGS.items() if label in named]
    auto = signals.get("auto-submitted", "").strip().lower()
    if auto and auto != "no":
        found.append("auto-submitted")
    if sender and NO_REPLY.match(sender.split("@")[0]):
        found.append("no-reply")
    if unsubscribe:
        found.append("unsubscribe")
    return found


def group_of(flags: Iterable[str]) -> Optional[str]:
    """The strongest group among a mail's flags (None for a mail with none)."""
    groups = {FLAG_GROUP[f] for f in flags}
    return next((g for g in STRENGTH if g in groups), None)


def outcome(flags: list[str], protections: list[str]) -> str:
    """What cleaning makes of a mail: `clean`, `junk:<group>`, `kept:receipt` or `kept:protected`."""
    if not flags:
        return "clean"
    if not protections:
        return f"junk:{group_of(flags)}"
    return "kept:receipt" if protections == ["receipt"] else "kept:protected"


def owner_addresses_from_sent(index: "MailIndex") -> set[str]:
    """The addresses the owner's mail labelled `Sent` came from, in every source of the index."""
    rows = index.connection.execute(
        "SELECT DISTINCT sender_address FROM mails, json_each(mails.labels) "
        "WHERE json_each.value = 'Sent' AND sender_address IS NOT NULL"
    )
    return {str(r[0]) for r in rows}


def classify(
    index: "MailIndex",
    source_id: int,
    owner: set[str],
    known_addresses: set[str],
    known_names: set[str],
    kept: Optional[set[str]] = None,
) -> None:
    """Flag and protect every mail of a source, and put each sender in its group."""
    db = index.connection
    owner = {a.lower() for a in owner}
    known = {a.lower() for a in known_addresses}
    names = {n.strip().casefold() for n in known_names if n.strip()}
    keep = {a.lower() for a in kept or ()}
    wrote: dict[str, int] = {}
    # Once per mail: a Cleaned or Reduced copy holds the same mails as its source.
    for _, sender, recipients in db.execute(
        "SELECT DISTINCT sha256, sender_address, recipients FROM mails "
        "WHERE sender_address IS NOT NULL"
    ):
        if sender in owner:
            for _, _, address in json.loads(recipients):
                wrote[address] = wrote.get(address, 0) + 1
    owner_threads = {
        r[0]
        for r in db.execute(
            "SELECT DISTINCT thread_key FROM mails WHERE source_id = ? AND sender_address IN "
            f"({', '.join('?' for _ in owner) or 'NULL'})",
            (source_id, *owner),
        )
    }
    updates = []
    strongest: dict[str, int] = {}
    for position, sender, name, labels, signals, unsubscribe, receipt, thread in db.execute(
        "SELECT position, sender_address, sender_name, labels, signals, unsubscribe, receipt, "
        "thread_key FROM mails WHERE source_id = ?",
        (source_id,),
    ).fetchall():
        flags = flags_of(sender, json.loads(labels), json.loads(signals), bool(unsubscribe))
        protections = []
        if sender in owner:
            protections.append("owner")
        if sender in known or (name or "").strip().casefold() in names:
            protections.append("box_person")
        if sender in wrote:
            protections.append("owner_wrote")
        if thread in owner_threads:
            protections.append("owner_thread")
        if receipt:
            protections.append("receipt")
        if sender in keep:
            protections.append("kept")
        updates.append(
            (json.dumps(flags), json.dumps(protections), int(sender in owner), source_id, position)
        )
        group = group_of(flags) if flags and not protections else None
        if group and sender:
            rank = STRENGTH.index(group)
            strongest[sender] = min(strongest.get(sender, rank), rank)
    db.execute("BEGIN")
    try:
        db.executemany(
            "UPDATE mails SET flags = ?, protections = ?, by_owner = ? "
            "WHERE source_id = ? AND position = ?",
            updates,
        )
        db.execute(
            "UPDATE senders SET grp = NULL, owner_wrote = 0 WHERE source_id = ?", (source_id,)
        )
        db.executemany(
            "UPDATE senders SET grp = ? WHERE source_id = ? AND address = ?",
            [(STRENGTH[rank], source_id, address) for address, rank in strongest.items()],
        )
        db.executemany(
            "UPDATE senders SET owner_wrote = ? WHERE source_id = ? AND address = ?",
            [(count, source_id, address) for address, count in wrote.items()],
        )
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


def groups(index: "MailIndex", source_id: int) -> list[Group]:
    """What cleaning would leave out, by group and sender (with the receipts it keeps), each with
    its number of senders and mails and the space they take."""
    totals: dict[str, dict[str, list[Any]]] = {key: {} for key in GROUPS}
    for sender, name, length, flags, protections in index.connection.execute(
        "SELECT sender_address, sender_name, length, flags, protections FROM mails "
        "WHERE source_id = ? AND flags IS NOT NULL AND flags != '[]'",
        (source_id,),
    ):
        guarded = json.loads(protections)
        if guarded == ["receipt"]:
            key: Optional[str] = "receipts"
        elif not guarded:
            key = group_of(json.loads(flags))
        else:
            continue
        if key is None:
            continue
        address = sender or ""
        entry = totals[key].setdefault(address, [name or "", 0, 0])
        entry[0] = entry[0] or name or ""
        entry[1] += 1
        entry[2] += length
    found = []
    for key in GROUPS:
        rows = tuple(
            sorted(
                (SenderRow(n or a, a, m, s) for a, (n, m, s) in totals[key].items()),
                key=lambda r: (-r.mails, r.name.casefold(), r.address),
            )
        )
        found.append(
            Group(
                key,
                LABELS[key],
                len(rows),
                sum(r.mails for r in rows),
                sum(r.size for r in rows),
                rows,
            )
        )
    return found
