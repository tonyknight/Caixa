"""A noisy mailbox: what a real Gmail Takeout looks like, in miniature.

A real mailbox is mostly noise: newsletters, notifications, mailing lists, shops, banks and
strangers, with the few conversations that matter mixed in. This builder writes one, for the mail
workflow's tests (reading, cleaning, sorting, importing, reducing), and says for every mail what the
workflow must make of it.

- `MAILS` declares every mail as data. Each one carries its **cleaning outcome** (`clean`,
  `junk:<group>` with the groups `lists`, `notices`, `unsubscribe`, `spam_trash`, `kept:receipt`
  or `kept:protected`) and the **cases** it illustrates, so a test can ask for "the mail without a
  Message-ID" or "every receipt" instead of counting lines.
- `build_noisy_mbox(out_dir)` writes the Gmail account's mbox, a second ("Work") account's mbox
  that shares one mail with the first, a zip of the first, and a Takeout-shaped zip of both.
  Boundaries, `From ` lines and zip entries are fixed, so every build is byte-identical.
- `write_large_mbox(path, size)` writes numbered copies of the Gmail account's mails until the file
  is at least `size` bytes, for the slow scale test (never committed).

The people are the fixture family's (Ana, João and Rui are people in the box; Maria is the owner).
Everyone else is invented, on reserved `example.*` domains. Never add real personal data.
"""

from __future__ import annotations

import io
import mailbox
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from email import encoders
from email.charset import QP, Charset
from email.generator import BytesGenerator
from email.header import Header
from email.message import Message
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime, formataddr
from pathlib import Path
from typing import Iterable, Optional

from fixtures import family
from fixtures.builders.media import GIF_1X1, png

MAILBOX_NAME = "All mail Including Spam and Trash.mbox"
WORK_MAILBOX_NAME = "Work.mbox"

#: The owner's second address: the "Work" account.
OWNER_WORK = "maria.costa@studio.example.org"

#: Every cleaning outcome a mail can have.
OUTCOMES = (
    "clean",
    "junk:lists",
    "junk:notices",
    "junk:unsubscribe",
    "junk:spam_trash",
    "kept:receipt",
    "kept:protected",
)

#: Every case the catalogue illustrates (a test checks each one is present).
CASES = (
    "gmail_thread",
    "references_thread",
    "thread_across_years",
    "owner_reply",
    "unanswered_owner_mail",
    "name_only_match",
    "stranger_owner_wrote_to",
    "stranger_never_answered",
    "same_mail_two_accounts",
    "html_only",
    "html_unsafe",
    "box_person_forwards_newsletter",
    "trash_from_box_person",
    "newsletter",
    "gmail_category",
    "esp_marker",
    "mailing_list",
    "list_thread_box_person",
    "list_thread_owner",
    "owner_answered_list",
    "notifications",
    "noreply_sender",
    "bounce",
    "unsubscribe_en",
    "unsubscribe_pt",
    "unsubscribe_es",
    "spam",
    "trash",
    "receipt_en",
    "receipt_pt",
    "receipt_es",
    "no_message_id",
    "latin1_body",
    "windows1252_subject",
    "signature_image",
    "tracking_pixel",
    "image001_clash",
    "from_line_in_body",
)

Address = tuple[str, str]  # (display name, address)


@dataclass(frozen=True)
class Attachment:
    """A file a mail carries. An inline one has a Content-ID its HTML points at (`cid:<name>`)."""

    name: str
    data: bytes
    mime: str
    inline: bool = False


@dataclass(frozen=True)
class Mail:
    key: str
    sender: Address
    to: tuple[Address, ...]
    subject: str
    moment: datetime
    text: Optional[str] = None
    html: Optional[str] = None
    cc: tuple[Address, ...] = ()
    labels: tuple[str, ...] = ("Inbox",)
    #: Gmail's thread id (`X-GM-THRID`); None for a mail threaded by its References alone.
    thread: Optional[str] = None
    has_message_id: bool = True
    #: Keys of the earlier mails it replies to, oldest first (its References).
    replies_to: tuple[str, ...] = ()
    headers: tuple[tuple[str, str], ...] = ()
    attachments: tuple[Attachment, ...] = ()
    charset: str = "utf-8"
    accounts: tuple[str, ...] = ("gmail",)
    clean: str = "clean"
    cases: tuple[str, ...] = ()

    def message_id(self, copy: str = "") -> Optional[str]:
        """`<key@sender's domain>`, or None for the mail that has none."""
        if not self.has_message_id:
            return None
        return f"<{self.key}{copy}@{self.sender[1].split('@')[1]}>"


@dataclass(frozen=True)
class NoisyMail:
    """Where `build_noisy_mbox` wrote everything, and what is in it."""

    gmail: Path
    work: Path
    zip: Path
    takeout_zip: Path
    catalogue: dict[str, Mail]


# --- The people -------------------------------------------------------------------------------


def _person(p: family.Person) -> Address:
    return (p.name, p.emails[0])


ME = _person(family.OWNER)
ME_WORK: Address = (family.OWNER.name, OWNER_WORK)
ANA, JOAO, RUI = _person(family.ANA), _person(family.JOAO), _person(family.RUI)
RUI_HOME: Address = (family.RUI.name, "rui.home@example.net")  # a box person's name, a new address
BEATRIZ: Address = ("Beatriz Lima", "beatriz.lima@example.net")
CARLOS: Address = ("Carlos Mendes", "carlos.mendes@example.net")
INES: Address = ("Inês Rocha", "ines.rocha@example.net")
PEDRO: Address = ("Pedro Alves", "pedro.alves@example.net")
SOFIA: Address = ("Sofia Reis", "sofia.reis@example.net")
HIKERS: Address = ("Lisbon Hikers", "hikers@lists.example.org")
FOLD: Address = ("The Daily Fold", "news@dailyfold.example.com")
SCHOOL: Address = ("Escola Azul", "news@escola.example.org")
CLIENT: Address = ("Studio Client", "client@client.example.com")

EAST, LISBON = family.TZ_EAST, family.TZ_LISBON
at = family.at

# --- Bodies and files -------------------------------------------------------------------------

FOLD_HEADERS = (
    ("List-Id", "The Daily Fold <dailyfold.example.com>"),
    ("List-Unsubscribe", "<https://dailyfold.example.com/unsubscribe>"),
    ("Precedence", "bulk"),
)
HIKERS_HEADERS = (
    ("List-Id", "Lisbon Hikers <hikers.lists.example.org>"),
    ("List-Post", "<mailto:hikers@lists.example.org>"),
    ("List-Unsubscribe", "<mailto:hikers-leave@lists.example.org>"),
)
SCHOOL_HEADERS = (
    ("List-Id", "Escola Azul families <families.escola.example.org>"),
    ("List-Unsubscribe", "<https://escola.example.org/leave>"),
)
SHOP_LIST = (("List-Unsubscribe", "<https://shop.example.com/unsubscribe>"),)


def _logo(variant: int) -> Attachment:
    """Beatriz's signature logo: always 40×12 pixels, re-encoded (different bytes) every time."""
    return Attachment("logo.png", png(40, 12, (30, 60, 90 + variant)), "image/png", inline=True)


PIXEL = Attachment("pixel.gif", GIF_1X1, "image/gif", inline=True)


def _fold_issue(number: int) -> str:
    return (
        f"<html><body><h1>The Daily Fold</h1><p>Issue {number}: folding chairs, folding maps.</p>"
        f'<img src="https://tracker.example.com/open?issue={number}" width="1" height="1">'
        '<p><a href="https://dailyfold.example.com/unsubscribe">Unsubscribe</a></p></body></html>'
    )


def _fold(n: int, month: int) -> Mail:
    return Mail(
        f"fold-{n}",
        FOLD,
        (ME,),
        f"The Daily Fold — issue {n}",
        at(2024, month, 3, 7, 0),
        html=_fold_issue(n),
        headers=FOLD_HEADERS,
        labels=("Inbox", "Category Promotions"),
        attachments=(PIXEL,) if n == 1 else (),
        clean="junk:lists",
        cases=("newsletter", "tracking_pixel") if n == 1 else ("newsletter",),
    )


def _social(n: int) -> Mail:
    return Mail(
        f"social-{n}",
        ("Social Site", "notifications@social.example.com"),
        (ME,),
        f"You have {n + 2} new notifications",
        at(2023, 4, n, 18, 0),
        text="Someone liked your photo. See what you missed.\n",
        headers=(("Auto-Submitted", "auto-generated"),),
        labels=("Inbox", "Category Social"),
        clean="junk:notices",
        cases=("notifications",),
    )


def _mails() -> tuple[Mail, ...]:
    mails = [
        # --- João: a Gmail thread, with two different image001.png on one day -----------------
        Mail(
            "joao-photos-1",
            JOAO,
            (ME,),
            "Fotos de São Martinho",
            at(2019, 11, 2, 9, 30, tz=LISBON),
            text="Olá Maria,\n\nAs fotos da festa de São Martinho estão prontas.\n",
            html="<p>Olá Maria,</p><p>As fotos da festa de <b>São Martinho</b> estão prontas.</p>",
            thread="1790000000000000001",
            labels=("Inbox", "Família"),
            cases=("gmail_thread",),
        ),
        Mail(
            "joao-photos-2",
            ME,
            (JOAO,),
            "Re: Fotos de São Martinho",
            at(2019, 11, 2, 9, 15, tz=EAST),
            text="Que maravilha! Send them all, please.\n\n> As fotos estão prontas.\n",
            thread="1790000000000000001",
            labels=("Sent",),
            replies_to=("joao-photos-1",),
            cases=("owner_reply",),
        ),
        Mail(
            "joao-photos-3",
            JOAO,
            (ME,),
            "Re: Fotos de São Martinho",
            at(2019, 11, 2, 16, 0, tz=LISBON),
            text="Here is the best one. The rest are on the drive.\n",
            thread="1790000000000000001",
            labels=("Inbox", "Família"),
            replies_to=("joao-photos-1", "joao-photos-2"),
            attachments=(Attachment("image001.png", png(3, 3, (10, 10, 10)), "image/png"),),
            cases=("image001_clash",),
        ),
        Mail(
            "joao-photos-4",
            ME,
            (JOAO,),
            "Re: Fotos de São Martinho",
            at(2019, 11, 2, 12, 0, tz=EAST),
            text="And here is mine, from the kitchen window.\n",
            thread="1790000000000000001",
            labels=("Sent",),
            replies_to=("joao-photos-1", "joao-photos-2", "joao-photos-3"),
            attachments=(Attachment("image001.png", png(3, 3, (20, 20, 20)), "image/png"),),
            cases=("image001_clash",),
        ),
        # --- João: a References thread over three years, with a "From " line in a body --------
        Mail(
            "joao-attic-1",
            JOAO,
            (ME,),
            "The attic boxes",
            at(2019, 12, 20, 10, 0, tz=LISBON),
            text="Maria,\n\nFrom the attic I brought down three boxes of letters.\nShall I keep them?\n",
            charset="us-ascii",
            cases=("references_thread", "from_line_in_body"),
        ),
        Mail(
            "joao-attic-2",
            ME,
            (JOAO,),
            "Re: The attic boxes",
            at(2020, 1, 5, 20, 0),
            text="Keep them all. I will read them at Easter.\n",
            labels=("Sent",),
            replies_to=("joao-attic-1",),
        ),
        Mail(
            "joao-attic-3",
            JOAO,
            (ME,),
            "Re: The attic boxes",
            at(2021, 3, 14, 11, 0, tz=LISBON),
            text="I found the letters from Grandpa in the third box.\n",
            replies_to=("joao-attic-1", "joao-attic-2"),
            cases=("thread_across_years",),
        ),
        # --- Ana: the mail in both accounts, a forwarded newsletter, a trashed mail -----------
        Mail(
            "ana-wedding-1",
            ANA,
            (ME,),
            "Wedding update",
            at(2025, 1, 15, 20, 45),
            html="<html><body><h1>Wedding update</h1><p>The date is set: 14 June.</p></body></html>",
            cc=(ME_WORK,),
            thread="1790000000000000002",
            labels=("Inbox", "Important"),
            accounts=("gmail", "work"),
            cases=("same_mail_two_accounts", "html_only"),
        ),
        Mail(
            "ana-wedding-2",
            ME,
            (ANA,),
            "Re: Wedding update",
            at(2025, 1, 16, 8, 10),
            text="Wonderful! We will be there.\n",
            thread="1790000000000000002",
            labels=("Sent",),
            replies_to=("ana-wedding-1",),
        ),
        Mail(
            "ana-forward",
            ANA,
            (ME,),
            "Fwd: The Daily Fold — spring issue",
            at(2024, 4, 9, 13, 0),
            text=(
                "Look at the chairs on page two!\n\n---------- Forwarded message ----------\n"
                "The Daily Fold, spring issue.\n"
                "Unsubscribe here: https://dailyfold.example.com/unsubscribe\n"
            ),
            clean="kept:protected",
            cases=("box_person_forwards_newsletter",),
        ),
        Mail(
            "ana-trashed",
            ANA,
            (ME,),
            "Parking at the venue",
            at(2025, 2, 2, 9, 0),
            text="Parking is behind the church.\n",
            labels=("Trash",),
            clean="kept:protected",
            cases=("trash_from_box_person",),
        ),
        # --- Rui: the owner's unanswered mail; his name from an address the box does not know -
        Mail(
            "rui-unanswered",
            ME,
            (RUI,),
            "Lunch next week?",
            at(2024, 5, 2, 12, 30),
            text="Rui, are you free for lunch on Thursday?\n",
            labels=("Sent",),
            cases=("unanswered_owner_mail",),
        ),
        Mail(
            "rui-home",
            RUI_HOME,
            (ME,),
            "Bolo de aniversário",
            at(2024, 6, 10, 17, 0),
            text="A receita do bolo, como prometido.\n",
            cases=("name_only_match",),
        ),
        # --- Beatriz: a stranger the owner wrote to; signature logos; unsafe HTML -------------
        Mail(
            "beatriz-1",
            BEATRIZ,
            (ME,),
            "Book club in March",
            at(2023, 2, 1, 19, 0),
            text="Hi Maria, we meet on the 9th. Beatriz\n",
            html='<p>Hi Maria, we meet on the 9th.</p><p>Beatriz<br><img src="cid:logo.png"></p>',
            attachments=(_logo(1),),
            cases=("stranger_owner_wrote_to", "signature_image"),
        ),
        Mail(
            "beatriz-2",
            ME,
            (BEATRIZ,),
            "Re: Book club in March",
            at(2023, 2, 2, 9, 0),
            text="I will bring the cake.\n",
            labels=("Sent",),
            replies_to=("beatriz-1",),
        ),
        Mail(
            "beatriz-3",
            BEATRIZ,
            (ME,),
            "Re: Book club in March",
            at(2023, 2, 2, 21, 0),
            text="Lovely, thank you. Beatriz\n",
            html=(
                "<html><head><script>document.title='x'</script></head>"
                '<body onload="track()"><p>Lovely, thank you.</p>'
                '<img src="https://tracker.example.com/b.gif" width="1" height="1">'
                '<p>Beatriz<br><img src="cid:logo.png"></p></body></html>'
            ),
            replies_to=("beatriz-1", "beatriz-2"),
            attachments=(_logo(2),),
            cases=("html_unsafe", "signature_image"),
        ),
        Mail(
            "beatriz-4",
            BEATRIZ,
            (ME,),
            "Book club in April",
            at(2023, 3, 28, 19, 0),
            text="April: we read the next one. Beatriz\n",
            html='<p>April: we read the next one.</p><p>Beatriz<br><img src="cid:logo.png"></p>',
            attachments=(_logo(3),),
            cases=("signature_image",),
        ),
        # --- Carlos and Inês: strangers who were never answered; odd encodings ----------------
        Mail(
            "carlos-nomid",
            CARLOS,
            (ME,),
            "Hello from the conference",
            at(2022, 9, 10, 15, 0),
            text="It was good to meet you in Porto.\n",
            has_message_id=False,
            cases=("stranger_never_answered", "no_message_id"),
        ),
        Mail(
            "carlos-pixel",
            CARLOS,
            (ME,),
            "Slides",
            at(2022, 9, 12, 10, 0),
            text="The slides are attached to the link below.\n",
            html='<p>The slides are attached to the link below.</p><img src="cid:pixel.gif">',
            attachments=(PIXEL,),
            cases=("tracking_pixel",),
        ),
        Mail(
            "ines-latin1",
            INES,
            (ME,),
            "Receita de bacalhau",
            at(2021, 12, 23, 18, 0),
            text="Bacalhau, batatas, cebola e azeite. Não esqueças o pão.\n",
            charset="iso-8859-1",
            cases=("latin1_body",),
        ),
        Mail(
            "ines-cp1252",
            INES,
            (ME,),
            "Café na sexta — confirmas?",
            at(2022, 1, 20, 9, 0),
            text="Às dez, no sítio do costume.\n",
            charset="windows-1252",
            cases=("windows1252_subject",),
        ),
        # --- Newsletters and other bulk mail ---------------------------------------------------
        *(_fold(n, month) for n, month in ((1, 1), (2, 2), (3, 3), (4, 5), (5, 6), (6, 7))),
        Mail(
            "gardening-1",
            ("Gardening Weekly", "newsletter@gardening.example.com"),
            (ME,),
            "Tomatoes in November",
            at(2023, 11, 4, 6, 0),
            text="This week: what to plant before the frost.\n",
            labels=("Category Promotions",),
            clean="junk:lists",
            cases=("gmail_category",),
        ),
        Mail(
            "gardening-2",
            ("Gardening Weekly", "newsletter@gardening.example.com"),
            (ME,),
            "Bulbs for spring",
            at(2023, 11, 11, 6, 0),
            text="This week: bulbs, and where to put them.\n",
            labels=("Category Promotions",),
            clean="junk:lists",
        ),
        Mail(
            "app-updates",
            ("App Updates", "updates@app.example.com"),
            (ME,),
            "What's new in version 4",
            at(2024, 2, 1, 12, 0),
            text="Version 4 brings a new home screen.\n",
            headers=(("Feedback-ID", "4:newsletter:app:sendservice"),),
            clean="junk:lists",
            cases=("esp_marker",),
        ),
        # --- A mailing list: one thread the owner and a box person wrote in, one they did not --
        Mail(
            "hikers-1",
            PEDRO,
            (HIKERS,),
            "Sintra walk on Saturday",
            at(2023, 5, 1, 8, 0, tz=LISBON),
            text="Meet at Rossio station at nine.\n",
            headers=HIKERS_HEADERS,
            clean="kept:protected",
            cases=("mailing_list",),
        ),
        Mail(
            "hikers-2",
            SOFIA,
            (HIKERS,),
            "Re: Sintra walk on Saturday",
            at(2023, 5, 1, 9, 0, tz=LISBON),
            text="I will bring sandwiches.\n",
            headers=HIKERS_HEADERS,
            replies_to=("hikers-1",),
            clean="kept:protected",
        ),
        Mail(
            "hikers-joao",
            JOAO,
            (HIKERS,),
            "Re: Sintra walk on Saturday",
            at(2023, 5, 1, 10, 0, tz=LISBON),
            text="Count me in, with my sister.\n",
            headers=HIKERS_HEADERS,
            replies_to=("hikers-1", "hikers-2"),
            clean="kept:protected",
            cases=("list_thread_box_person",),
        ),
        Mail(
            "hikers-owner",
            ME,
            (HIKERS,),
            "Re: Sintra walk on Saturday",
            at(2023, 5, 1, 7, 0),
            text="See you all there!\n",
            headers=HIKERS_HEADERS,
            labels=("Sent",),
            replies_to=("hikers-1", "hikers-2", "hikers-joao"),
            clean="kept:protected",
            cases=("list_thread_owner",),
        ),
        Mail(
            "hikers-bottle-1",
            PEDRO,
            (HIKERS,),
            "Lost water bottle",
            at(2023, 5, 7, 8, 0, tz=LISBON),
            text="Did anyone find a blue water bottle on the walk?\n",
            headers=HIKERS_HEADERS,
            labels=("Inbox", "Category Forums"),
            clean="junk:lists",
        ),
        Mail(
            "hikers-bottle-2",
            SOFIA,
            (HIKERS,),
            "Re: Lost water bottle",
            at(2023, 5, 7, 9, 30, tz=LISBON),
            text="Yes, I have it.\n",
            headers=HIKERS_HEADERS,
            labels=("Inbox", "Category Forums"),
            replies_to=("hikers-bottle-1",),
            clean="junk:lists",
        ),
        # --- A school list the owner answered: its sender is protected ------------------------
        Mail(
            "school-1",
            SCHOOL,
            (ME,),
            "Term calendar",
            at(2022, 9, 1, 8, 0, tz=LISBON),
            text="The term calendar is attached to our site.\n",
            headers=SCHOOL_HEADERS,
            clean="kept:protected",
            cases=("owner_answered_list",),
        ),
        Mail(
            "school-2",
            ME,
            (SCHOOL,),
            "Re: Term calendar",
            at(2022, 9, 1, 19, 0),
            text="Thank you. Is the 3rd of October a holiday?\n",
            labels=("Sent",),
            replies_to=("school-1",),
            clean="clean",  # the owner's own plain reply: nothing flags it
        ),
        Mail(
            "school-3",
            SCHOOL,
            (ME,),
            "Christmas concert",
            at(2022, 12, 1, 8, 0, tz=LISBON),
            text="The concert is on the 16th at six.\n",
            headers=SCHOOL_HEADERS,
            clean="kept:protected",
        ),
        # --- Notices and no-reply ---------------------------------------------------------------
        *(_social(n) for n in (1, 2, 3)),
        Mail(
            "bank-1",
            ("Bank Alerts", "no-reply@bank.example.com"),
            (ME,),
            "Your statement is ready",
            at(2024, 3, 1, 6, 0),
            text="Your March statement is ready to view.\n",
            clean="junk:notices",
            cases=("noreply_sender",),
        ),
        Mail(
            "bank-2",
            ("Bank Alerts", "no-reply@bank.example.com"),
            (ME,),
            "A new device signed in",
            at(2024, 3, 9, 22, 0),
            text="A new device signed in to your account.\n",
            clean="junk:notices",
        ),
        Mail(
            "bounce",
            ("Mail Delivery Subsystem", "mailer-daemon@example.com"),
            (ME,),
            "Delivery Status Notification (Failure)",
            at(2024, 5, 2, 12, 31),
            text="Your message to old.friend@example.net could not be delivered.\n",
            clean="junk:notices",
            cases=("bounce",),
        ),
        Mail(
            "cloud-full",
            ("Cloud Drive", "donotreply@cloud.example.com"),
            (ME,),
            "Storage almost full",
            at(2024, 8, 20, 10, 0),
            text="You have used 95% of your storage.\n",
            labels=("Inbox", "Category Updates"),
            clean="junk:notices",
            cases=("gmail_category",),
        ),
        # --- Unsubscribe links in the body only, in three languages -----------------------------
        Mail(
            "deals-en",
            ("Shop Deals", "deals@shop.example.com"),
            (ME,),
            "Black Friday: 40% off everything",
            at(2024, 11, 29, 6, 0),
            text="Everything is 40% off today.\nTo unsubscribe, click https://shop.example.com/u\n",
            clean="junk:unsubscribe",
            cases=("unsubscribe_en",),
        ),
        Mail(
            "deals-pt",
            ("Loja Verde", "ofertas@lojaverde.example.com"),
            (ME,),
            "Promoções de outono",
            at(2024, 10, 1, 6, 0),
            text="Tudo para o seu jardim.\nPara cancelar a subscrição, clique aqui.\n",
            clean="junk:unsubscribe",
            cases=("unsubscribe_pt",),
        ),
        Mail(
            "deals-es",
            ("Tienda Sol", "ofertas@tiendasol.example.com"),
            (ME,),
            "Rebajas de invierno",
            at(2024, 1, 8, 6, 0),
            text="Todo rebajado.\nSi no deseas recibir más correos, puedes darte de baja aquí.\n",
            clean="junk:unsubscribe",
            cases=("unsubscribe_es",),
        ),
        # --- Spam and Trash ---------------------------------------------------------------------
        Mail(
            "spam",
            ("Prize Office", "winner@lottery.example.com"),
            (ME,),
            "You have won!!!",
            at(2024, 7, 4, 3, 0),
            text="Send your bank details to claim your prize.\n",
            labels=("Spam",),
            clean="junk:spam_trash",
            cases=("spam",),
        ),
        Mail(
            "trash",
            ("Old Forum", "forum@oldforum.example.com"),
            (ME,),
            "Weekly digest",
            at(2024, 7, 5, 3, 0),
            text="Five new topics this week.\n",
            labels=("Trash",),
            clean="junk:spam_trash",
            cases=("trash",),
        ),
        # --- Receipts and orders: from no-reply senders, with unsubscribe links, still kept -----
        Mail(
            "order-en",
            ("Shop", "no-reply@shop.example.com"),
            (ME,),
            "Your order #40211 has shipped",
            at(2024, 12, 2, 9, 0),
            text="Your order #40211 is on its way.\nTo unsubscribe from marketing, click here.\n",
            headers=SHOP_LIST,
            clean="kept:receipt",
            cases=("receipt_en",),
        ),
        Mail(
            "receipt-en",
            ("Shop", "no-reply@shop.example.com"),
            (ME,),
            "Receipt for your payment",
            at(2024, 12, 1, 9, 0),
            text="Thank you for your payment of $42.10. Receipt number 7781.\n",
            headers=SHOP_LIST,
            clean="kept:receipt",
            cases=("receipt_en",),
        ),
        Mail(
            "invoice-pt",
            ("Energia Lisboa", "faturas@energia.example.com"),
            (ME,),
            "Fatura n.º 2024/118 disponível",
            at(2024, 6, 5, 9, 0, tz=LISBON),
            text="A sua fatura de maio está disponível.\nPara cancelar a subscrição, clique aqui.\n",
            headers=(("List-Unsubscribe", "<https://energia.example.com/sair>"),),
            clean="kept:receipt",
            cases=("receipt_pt",),
        ),
        Mail(
            "booking-es",
            ("Hotel Mar", "reservas@hotelmar.example.com"),
            (ME,),
            "Confirmación de tu reserva",
            at(2024, 8, 1, 9, 0, tz=LISBON),
            text="Tu reserva para dos noches está confirmada.\nPuedes darte de baja aquí.\n",
            clean="kept:receipt",
            cases=("receipt_es",),
        ),
        Mail(
            "eticket-en",
            ("Air Example", "noreply@air.example.com"),
            (ME,),
            "Your e-ticket and booking confirmation",
            at(2024, 7, 20, 9, 0),
            text="Your e-ticket for flight EX 101 is attached to your booking.\n",
            headers=(("Auto-Submitted", "auto-generated"),),
            clean="kept:receipt",
            cases=("receipt_en",),
        ),
        # --- The Work account ---------------------------------------------------------------------
        Mail(
            "work-brief",
            CLIENT,
            (ME_WORK,),
            "Project brief",
            at(2024, 9, 2, 10, 0),
            text="Here is the brief for the autumn catalogue.\n",
            accounts=("work",),
        ),
        Mail(
            "work-reply",
            ME_WORK,
            (CLIENT,),
            "Re: Project brief",
            at(2024, 9, 2, 15, 0),
            text="Thank you, I will send sketches on Friday.\n",
            labels=("Sent",),
            replies_to=("work-brief",),
            accounts=("work",),
        ),
        Mail(
            "work-digest",
            ("Design Digest", "digest@design.example.com"),
            (ME_WORK,),
            "This week in design",
            at(2024, 9, 6, 7, 0),
            text="Ten covers we liked.\n",
            headers=(
                ("List-Id", "Design Digest <digest.design.example.com>"),
                ("List-Unsubscribe", "<https://design.example.com/leave>"),
            ),
            accounts=("work",),
            clean="junk:lists",
        ),
    ]
    return tuple(mails)


MAILS: tuple[Mail, ...] = _mails()


# --- Writing -----------------------------------------------------------------------------------


def _header(value: str, charset: str = "utf-8") -> str:
    return value if value.isascii() else Header(value, charset).encode()


def _address(address: Address) -> str:
    return formataddr(address, charset="utf-8")


def _text(body: str, subtype: str, charset: str) -> MIMEText:
    if charset == "utf-8":  # quoted-printable, as most mail programs write it
        utf8 = Charset("utf-8")
        utf8.body_encoding = QP
        return MIMEText(body, subtype, utf8)  # type: ignore[arg-type]
    return MIMEText(body, subtype, charset)


def _file(attachment: Attachment, key: str) -> MIMEBase:
    maintype, subtype = attachment.mime.split("/")
    part = MIMEBase(maintype, subtype, name=attachment.name)
    part.set_payload(attachment.data)
    encoders.encode_base64(part)
    if attachment.inline:
        part.add_header("Content-ID", f"<{attachment.name}.{key}@noisy.example>")
        part.add_header("Content-Disposition", "inline", filename=attachment.name)
    else:
        part.add_header("Content-Disposition", "attachment", filename=attachment.name)
    return part


def render(mail: Mail, by_key: dict[str, Mail], copy: str = "") -> Message:
    """One mail as an email message (compat32, so the bytes are exactly what we ask for)."""
    html = mail.html
    if html is not None:
        for a in mail.attachments:
            if a.inline:
                html = html.replace(f"cid:{a.name}", f"cid:{a.name}.{mail.key}@noisy.example")
    bodies = [
        _text(body, subtype, mail.charset)
        for body, subtype in ((mail.text, "plain"), (html, "html"))
        if body is not None
    ]
    message: Message = bodies[0]
    if len(bodies) == 2:
        message = MIMEMultipart("alternative", _subparts=bodies)
    inline = [a for a in mail.attachments if a.inline]
    files = [a for a in mail.attachments if not a.inline]
    if inline:
        message = MIMEMultipart(
            "related", _subparts=[message, *(_file(a, mail.key) for a in inline)]
        )
    if files:
        message = MIMEMultipart("mixed", _subparts=[message, *(_file(a, mail.key) for a in files)])
    for number, part in enumerate(message.walk()):
        if part.is_multipart():
            part.set_boundary(f"==noisy-{mail.key}-{number}==")

    message["From"] = _address(mail.sender)
    message["To"] = ", ".join(_address(a) for a in mail.to)
    if mail.cc:
        message["Cc"] = ", ".join(_address(a) for a in mail.cc)
    message["Subject"] = _header(
        mail.subject, mail.charset if mail.charset != "us-ascii" else "utf-8"
    )
    message["Date"] = format_datetime(mail.moment)
    message_id = mail.message_id(copy)
    if message_id:
        message["Message-ID"] = message_id
    references = [i for k in mail.replies_to if (i := by_key[k].message_id(copy))]
    if references:
        message["In-Reply-To"] = references[-1]
        message["References"] = " ".join(references)
    if mail.thread:
        message["X-GM-THRID"] = mail.thread + copy
    message["X-Gmail-Labels"] = ",".join(mail.labels)
    for name, value in mail.headers:
        message[name] = value
    sent = mail.moment.astimezone(timezone.utc)
    message.set_unixfrom(f"From {mail.sender[1]} {sent:%a %b %d %H:%M:%S %Y}")
    return message


def _write_mbox(path: Path, messages: Iterable[Message]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    box = mailbox.mbox(str(path), create=True)
    try:
        box.lock()
        for message in messages:
            box.add(message)
        box.flush()
    finally:
        box.unlock()
        box.close()
    path.with_name(path.name + ".lock").unlink(missing_ok=True)
    return path


def _zip(path: Path, members: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as out:
        for name, data in members.items():
            info = zipfile.ZipInfo(name, date_time=(2025, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            out.writestr(info, data)
    return path


def _account(account: str) -> list[Mail]:
    return [m for m in MAILS if account in m.accounts]


def build_noisy_mbox(out_dir: Path) -> NoisyMail:
    """Write both accounts' mboxes and the zips into `out_dir`; return where, and the catalogue."""
    by_key = {m.key: m for m in MAILS}
    gmail = _write_mbox(
        out_dir / "Takeout" / "Mail" / MAILBOX_NAME,
        (render(m, by_key) for m in sorted(_account("gmail"), key=lambda m: m.moment)),
    )
    work = _write_mbox(
        out_dir / "Work" / WORK_MAILBOX_NAME,
        (render(m, by_key) for m in sorted(_account("work"), key=lambda m: m.moment)),
    )
    plain = _zip(out_dir / "zipped" / "gmail-mbox.zip", {MAILBOX_NAME: gmail.read_bytes()})
    takeout = _zip(
        out_dir / "zipped" / "takeout-20250101T000000Z-001.zip",
        {
            f"Takeout/Mail/{MAILBOX_NAME}": gmail.read_bytes(),
            f"Takeout/Mail/{WORK_MAILBOX_NAME}": work.read_bytes(),
        },
    )
    return NoisyMail(gmail, work, plain, takeout, dict(by_key))


# --- A large mailbox, for the scale test --------------------------------------------------------

_COPY = "~N~"


def _entry(message: Message) -> bytes:
    """One mbox entry: its `From ` line, the message with `From ` lines in bodies escaped, a blank
    line (as `mailbox.mbox` writes it)."""
    buffer = io.BytesIO()
    BytesGenerator(buffer, mangle_from_=True, maxheaderlen=0).flatten(message, unixfrom=True)
    data = buffer.getvalue().replace(b"\r\n", b"\n")
    return data + (b"\n" if data.endswith(b"\n") else b"\n\n")


#: Filler that pads a mail to a realistic size: lines like a base64 attachment's, after the mail's
#: own end (a multipart mail's epilogue, a single-part mail's last lines), never a `From ` line.
_FILLER_LINE = b"QWxsIG1haWwgcGFkZGluZyBmb3IgdGhlIHNjYWxlIHRlc3Q" * 2 + b"\n"


def _padded(entry: bytes, average: int) -> bytes:
    missing = average - len(entry)
    if missing <= 0:
        return entry
    lines = _FILLER_LINE * (missing // len(_FILLER_LINE) + 1)
    return entry.rstrip(b"\n") + b"\n" + lines + b"\n"


def write_large_mbox(path: Path, size_bytes: int, average: int = 0) -> int:
    """Numbered copies of the Gmail account's mails (new Message-IDs and thread ids per copy),
    streamed to `path` until it holds at least `size_bytes`. Returns the number of mails.

    With `average`, every mail is padded to about that many bytes (real mail averages tens of
    kilobytes; the catalogue's mails are a few hundred bytes)."""
    by_key = {m.key: m for m in MAILS}
    templates = [
        _padded(_entry(render(m, by_key, copy=_COPY)), average)
        for m in sorted(_account("gmail"), key=lambda m: m.moment)
    ]
    token = re.escape(_COPY.encode())
    written = count = copy = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as out:
        while written < size_bytes:
            copy += 1
            number = str(copy).encode()
            for template in templates:
                data = re.sub(token, number, template)
                out.write(data)
                written += len(data)
                count += 1
                if written >= size_bytes:
                    break
    return count
