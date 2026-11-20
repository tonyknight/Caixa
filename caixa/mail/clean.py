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

import re
from email.message import EmailMessage, Message

from chattr.parsers.mbox_parser import html_to_text

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


def body_signals(message: EmailMessage, subject: str) -> tuple[bool, bool]:
    """(has an unsubscribe link, reads like a receipt or an order)."""
    text = body_text(message)
    return bool(UNSUBSCRIBE.search(text)), bool(RECEIPT.search(f"{subject}\n{text}"))
