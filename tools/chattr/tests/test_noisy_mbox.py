"""The noisy mbox fixture: real mail's mix of family, strangers, lists, notices and receipts."""

from __future__ import annotations

import email
import email.policy
import mailbox
import zipfile
from email.message import EmailMessage
from pathlib import Path

import pytest
from fixtures.builders.noisy_mbox import (
    CASES,
    MAILBOX_NAME,
    OUTCOMES,
    OWNER_WORK,
    WORK_MAILBOX_NAME,
    NoisyMail,
    build_noisy_mbox,
)


@pytest.fixture(scope="module")
def noisy(tmp_path_factory: pytest.TempPathFactory) -> NoisyMail:
    return build_noisy_mbox(tmp_path_factory.mktemp("noisy"))


def _messages(path: Path) -> list[EmailMessage]:
    box = mailbox.mbox(str(path), create=False)
    try:
        found = []
        for key in box.keys():
            message = email.message_from_bytes(box.get_bytes(key), policy=email.policy.default)
            assert isinstance(message, EmailMessage)
            found.append(message)
        return found
    finally:
        box.close()


def test_builds_are_byte_identical(tmp_path: Path) -> None:
    first = build_noisy_mbox(tmp_path / "a")
    second = build_noisy_mbox(tmp_path / "b")
    for name in ("gmail", "work", "zip", "takeout_zip"):
        assert getattr(first, name).read_bytes() == getattr(second, name).read_bytes(), name


def test_every_mail_parses_and_the_counts_match_the_catalogue(noisy: NoisyMail) -> None:
    gmail = _messages(noisy.gmail)
    work = _messages(noisy.work)
    assert len(gmail) == sum(1 for m in noisy.catalogue.values() if "gmail" in m.accounts)
    assert len(work) == sum(1 for m in noisy.catalogue.values() if "work" in m.accounts)
    assert len(gmail) >= 50
    subjects = {str(m["Subject"]) for m in gmail}
    assert {m.subject for m in noisy.catalogue.values() if "gmail" in m.accounts} == subjects


def test_every_outcome_and_every_case_is_there(noisy: NoisyMail) -> None:
    outcomes = {m.clean for m in noisy.catalogue.values()}
    assert outcomes == set(OUTCOMES)
    cases = {case for m in noisy.catalogue.values() for case in m.cases}
    assert cases == set(CASES), set(CASES) ^ cases


def test_the_hard_cases_are_in_the_bytes(noisy: NoisyMail) -> None:
    raw = noisy.gmail.read_bytes()
    assert b"\n>From the attic" in raw  # a body line beginning "From " is escaped
    gmail = _messages(noisy.gmail)
    assert sum(1 for m in gmail if m["Message-ID"] is None) == 1
    labels = ",".join(str(m.get("X-Gmail-Labels", "")) for m in gmail)
    for label in (
        "Sent",
        "Spam",
        "Trash",
        "Category Promotions",
        "Category Updates",
        "Category Social",
        "Category Forums",
    ):
        assert label in labels
    assert any(m.get_content_charset() == "iso-8859-1" for m in gmail if not m.is_multipart())


def test_the_same_mail_is_in_both_accounts(noisy: NoisyMail) -> None:
    gmail_ids = {str(m["Message-ID"]) for m in _messages(noisy.gmail) if m["Message-ID"]}
    work = _messages(noisy.work)
    shared = [m for m in work if str(m["Message-ID"]) in gmail_ids]
    assert len(shared) == 1
    assert OWNER_WORK in str(shared[0]["To"]) + str(shared[0]["Cc"])


def _attachments(noisy: NoisyMail) -> list[tuple[str, str, bytes]]:
    """(date, file name, bytes) of every attachment and inline file in the Gmail mbox."""
    found = []
    for message in _messages(noisy.gmail):
        for part in message.walk():
            name = part.get_filename()
            if name:
                payload = part.get_payload(decode=True)
                assert isinstance(payload, bytes)
                date = str(message["Date"])
                found.append((date, name, payload))
    return found


def test_attachments_for_the_filing_rules(noisy: NoisyMail) -> None:
    files = _attachments(noisy)
    logos = [data for _, name, data in files if name == "logo.png"]
    assert len(logos) >= 3 and len(set(logos)) == len(logos)  # a signature, re-encoded each time
    assert len({data[16:24] for data in logos}) == 1  # …but always the same pixel size
    pixels = [data for _, name, data in files if name.endswith(".gif") and len(data) < 64]
    assert len(pixels) >= 2  # tracking pixels
    clashes = [(date[:16], data) for date, name, data in files if name == "image001.png"]
    days = {}
    for day, data in clashes:
        days.setdefault(day[:11], set()).add(data)
    assert any(len(contents) == 2 for contents in days.values())  # same day, same name, two files


def test_html_with_scripts_and_remote_content(noisy: NoisyMail) -> None:
    html = [
        part.get_content()
        for message in _messages(noisy.gmail)
        for part in message.walk()
        if part.get_content_type() == "text/html"
    ]
    joined = "\n".join(html)
    assert "<script" in joined and "onload=" in joined and "https://tracker.example.com/" in joined


def test_the_zips(noisy: NoisyMail) -> None:
    with zipfile.ZipFile(noisy.zip) as plain:
        assert plain.namelist() == [MAILBOX_NAME]
        assert plain.read(MAILBOX_NAME) == noisy.gmail.read_bytes()
    with zipfile.ZipFile(noisy.takeout_zip) as takeout:
        assert sorted(takeout.namelist()) == sorted(
            [f"Takeout/Mail/{MAILBOX_NAME}", f"Takeout/Mail/{WORK_MAILBOX_NAME}"]
        )
        assert takeout.getinfo(f"Takeout/Mail/{MAILBOX_NAME}").compress_type == zipfile.ZIP_DEFLATED


def test_a_large_mbox_is_valid_deterministic_and_big_enough(tmp_path: Path) -> None:
    from fixtures.builders.noisy_mbox import write_large_mbox

    size = 3_000_000
    first = tmp_path / "large-1.mbox"
    count = write_large_mbox(first, size)
    assert first.stat().st_size >= size
    messages = _messages(first)
    assert len(messages) == count > 56
    ids = [str(m["Message-ID"]) for m in messages if m["Message-ID"]]
    assert len(ids) == len(set(ids))
    second = tmp_path / "large-2.mbox"
    assert write_large_mbox(second, size) == count
    assert first.read_bytes() == second.read_bytes()
