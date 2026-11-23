"""One account exported as two mboxes, received and sent (as Apple Mail or Outlook do): read as
a folder, each sorted and imported in turn, in either order. The owner's replies join the
conversations they answer, on the same person's page, and each mail keeps the mbox it came from.

No Gmail thread ids here: the conversations join through Message-ID and References alone."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family

from caixa.service import Service

ME, ANA, RUI = family.OWNER, family.ANA, family.RUI


def _mail(sender: tuple[str, str], to: tuple[str, str], subject: str, when: str, mid: str,
          body: str, replies: tuple[str, ...] = ()) -> bytes:  # fmt: skip
    headers = [
        f"From {sender[1]} Fri Mar  1 10:00:00 2024",
        f"From: {sender[0]} <{sender[1]}>",
        f"To: {to[0]} <{to[1]}>",
        f"Subject: {subject}",
        f"Date: {when}",
        f"Message-ID: <{mid}>",
    ]
    if replies:
        headers += [
            f"In-Reply-To: <{replies[-1]}>",
            "References: " + " ".join(f"<{r}>" for r in replies),
        ]
    return ("\n".join(headers) + "\n\n" + body + "\n\n").encode()


ME_, ANA_, RUI_ = (ME.name, ME.emails[0]), (ANA.name, ANA.emails[0]), (RUI.name, RUI.emails[0])
INBOX = _mail(ANA_, ME_, "Dinner on Friday", "Fri, 01 Mar 2024 10:00:00 +0000", "dinner-1@example.com",
              "Shall we have dinner on Friday?") + _mail(
    ANA_, ME_, "Re: Dinner on Friday", "Fri, 01 Mar 2024 12:00:00 +0000", "dinner-3@example.com",
    "Perfect, see you at eight.", ("dinner-1@example.com", "dinner-2@example.com"))  # fmt: skip
SENT = _mail(ME_, ANA_, "Re: Dinner on Friday", "Fri, 01 Mar 2024 11:00:00 +0000", "dinner-2@example.com",
             "Yes! At eight?", ("dinner-1@example.com",)) + _mail(
    ME_, RUI_, "Lunch next week", "Mon, 04 Mar 2024 09:00:00 +0000", "lunch-1@example.com",
    "Free for lunch next week?")  # fmt: skip


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Service]:
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Our box", owner=ME.name)
    yield made
    made.close()


def _read_folder(service: Service, tmp_path: Path) -> dict[str, int]:
    folder = tmp_path / "Work mail"
    folder.mkdir()
    (folder / "Inbox.mbox").write_bytes(INBOX)
    (folder / "Sent.mbox").write_bytes(SENT)
    job = service.call("mail.read", {"source": str(folder), "account": "Work"})
    done = service.wait(job["id"], timeout=60)
    assert done["status"] == "done", done["error"]
    return {Path(s["path"]).stem: s["source_id"] for s in done["result"]["sources"]}


def _imported(service: Service, source: int) -> None:
    done = service.wait(service.call("mail.import", {"source": source})["id"], timeout=120)
    assert done["status"] == "done", done["error"]


@pytest.mark.parametrize(
    "order", [("Inbox", "Sent"), ("Sent", "Inbox")], ids=["inbox-first", "sent-first"]
)
def test_received_and_sent_join_in_one_account(
    service: Service, tmp_path: Path, order: tuple[str, str]
) -> None:
    sources = _read_folder(service, tmp_path)
    assert set(sources) == {"Inbox", "Sent"}  # both read, both listed for later
    listed = {s["id"] for s in service.call("mail.sources")["sources"]}
    assert set(sources.values()) <= listed
    service.call("mail.owner.set", {"source": sources["Inbox"], "addresses": [ME.emails[0]]})
    service.call(
        "mail.choose", {"source": sources["Inbox"], "addresses": [ANA.emails[0], RUI.emails[0]]}
    )
    # (a choice holds for the whole box: the second mbox needs no sorting again)
    second = service.call("mail.senders", {"source": sources["Sent"]})
    to_import = next(c for c in second["categories"] if c["key"] == "to_import")
    assert {r["address"] for r in to_import["rows"]} >= {ANA.emails[0], RUI.emails[0]}

    for name in order:
        _imported(service, sources[name])

    with service._require_box().master() as master:
        threads = master.connection.execute(
            "SELECT subject, mails FROM mail_threads ORDER BY subject"
        ).fetchall()
        folders = dict(master.connection.execute("SELECT message_id, subject FROM mail").fetchall())
    assert [tuple(t) for t in threads] == [("Dinner on Friday", 3), ("Lunch next week", 1)]
    assert len(folders) == 4  # every mail once

    root = service._require_box().root
    ana = (root / "People" / ANA.name / f"{ANA.name}.html").read_text(encoding="utf-8")
    assert ana.count("Dinner on Friday") >= 1 and "3 mails" in ana  # one conversation, all three
    page = html.unescape(
        (
            root / "People" / ANA.name / "Mail" / "Work" / "(2024-03-01) Dinner on Friday.html"
        ).read_text(encoding="utf-8")
    )
    for said in ("Shall we have dinner on Friday?", "Yes! At eight?", "Perfect, see you at eight."):
        assert said in page
    # Rui never wrote back and nobody named him: his tile is his address (Unrecognized) until named
    lunch = root / "People" / RUI.emails[0] / "Mail" / "Work" / "(2024-03-04) Lunch next week.html"
    assert lunch.is_file()

    index = html.unescape((root / "index.html").read_text(encoding="utf-8"))
    rows = re.findall(r"<li data-account=\"Work\" data-labels=\"(.*?)\">.*?<a [^>]*>(.*?)</a>", index)
    assert dict((title, labels) for labels, title in rows) == {
        "Dinner on Friday": '["Inbox", "Sent"]',  # Mail ▸ Work ▸ Inbox and ▸ Sent: both hold it
        "Lunch next week": '["Sent"]',
    }
