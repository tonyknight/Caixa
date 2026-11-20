"""The mail workflow through the service layer and the command line."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

import pytest
from fixtures import family
from fixtures.builders.noisy_mbox import NoisyMail

from caixa import cli, settings
from caixa.service import Service, ServiceError


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Service]:
    with_box = Service(roots=[tmp_path])
    with_box.box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    yield with_box
    with_box.close()


def test_reading_an_mbox_is_a_job_that_reports_what_it_read(
    service: Service, noisy_mail: NoisyMail
) -> None:
    job = service.call("mail.read", {"source": str(noisy_mail.takeout_zip), "account": "Gmail"})
    assert job["kind"] == "mail-read" and job["source"] == str(noisy_mail.takeout_zip)
    done = service.wait(job["id"], timeout=60)
    assert done["status"] == "done", done["error"]
    result = done["result"]
    assert result["mails"] == 60 and len(result["sources"]) == 2
    assert {s["account"] for s in result["sources"]} == {"Gmail"}
    listed = service.call("mail.sources")
    assert [s["mails"] for s in listed["sources"]] == [56, 4]
    assert all(s["status"] == "read" for s in listed["sources"])
    assert (Path(service.call("box.status")["root"]) / ".caixa" / "mail" / "index.sqlite").is_file()


def test_the_account_is_remembered_and_needed(service: Service, noisy_mail: NoisyMail) -> None:
    with pytest.raises(ServiceError, match="account"):
        service.call("mail.read", {"source": str(noisy_mail.gmail)})
    first = service.wait(
        service.call("mail.read", {"source": str(noisy_mail.gmail), "account": "Gmail"})["id"],
        timeout=60,
    )
    again = service.wait(
        service.call("mail.read", {"source": str(noisy_mail.gmail)})["id"], timeout=60
    )
    assert first["status"] == again["status"] == "done"
    assert again["result"]["sources"][0]["reused"] is True
    assert again["result"]["sources"][0]["account"] == "Gmail"


def test_a_missing_source_or_a_bad_account_is_refused(service: Service, tmp_path: Path) -> None:
    with pytest.raises(ServiceError, match="Not found"):
        service.call("mail.read", {"source": str(tmp_path / "nope.mbox"), "account": "Gmail"})
    with pytest.raises(ServiceError, match="account"):
        service.call("mail.read", {"source": str(tmp_path), "account": "a/b"})


def test_reading_is_refused_when_the_box_is_read_only(
    tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    Service().box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    reader = Service(read_only=True)
    reader.box_open(str(tmp_path / "Box"))
    with pytest.raises(ServiceError):
        reader.call("mail.read", {"source": str(noisy_mail.gmail), "account": "Gmail"})
    assert reader.call("mail.sources") == {"sources": []}


def test_the_workers_setting(service: Service) -> None:
    spec = settings.SCHEMA["properties"]["workers"]
    assert spec["default"] == min(os.cpu_count() or 1, 12)
    assert spec["minimum"] == 1 and spec["maximum"] == 12
    assert service.call("settings.get")["values"]["workers"] == spec["default"]
    service.call("settings.set", {"values": {"workers": 3}})
    assert service.call("settings.get")["values"]["workers"] == 3
    with pytest.raises(ServiceError):
        service.call("settings.set", {"values": {"workers": 13}})


def test_the_command_line_reads_and_says_what_it_read(
    tmp_path: Path, noisy_mail: NoisyMail, capsys: pytest.CaptureFixture[str]
) -> None:
    box = tmp_path / "Box"
    assert cli.main(["box", "create", str(box), "--name", "Our box"]) == 0
    capsys.readouterr()
    code = cli.main(
        ["mail", "read", str(noisy_mail.gmail), "--account", "Gmail", "--workers", "2",
         "--box", str(box)]
    )  # fmt: skip
    out = capsys.readouterr().out
    assert code == 0
    assert "56 mails" in out and "All mail Including Spam and Trash.mbox" in out and "Gmail" in out
    assert cli.main(["mail", "read", str(noisy_mail.gmail), "--box", str(box), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["sources"][0]["reused"] is True
    assert cli.main(["mail", "read", str(tmp_path / "nope.mbox"), "--account", "G",
                     "--box", str(box)]) == 1  # fmt: skip
    assert "Not found" in capsys.readouterr().err


# --- Cleaning through the service (ticket 05) -------------------------------------------------------

import shutil  # noqa: E402

from fixtures.builders.noisy_mbox import MAILBOX_NAME  # noqa: E402

from caixa import owner  # noqa: E402
from caixa.box import Box  # noqa: E402


def _box(service: Service) -> Box:
    return Box.open(service.call("box.status")["root"])


def _with_family(service: Service) -> None:
    with _box(service).master() as master:
        for person in (family.ANA, family.JOAO, family.RUI):
            master.add_alias(master.add_person(person.name), person.emails[0], "email")
        master.commit()


def _read(service: Service, path: Path, account: str = "Gmail") -> int:
    done = service.wait(
        service.call("mail.read", {"source": str(path), "account": account})["id"], timeout=60
    )
    assert done["status"] == "done", done["error"]
    return int(done["result"]["sources"][0]["source_id"])


@pytest.fixture
def gmail(tmp_path: Path, noisy_mail: NoisyMail) -> Path:
    folder = tmp_path / "exports"
    folder.mkdir()
    return Path(shutil.copy(noisy_mail.gmail, folder / MAILBOX_NAME))


def test_cleaning_shows_the_groups_and_what_writing_would_leave_out(
    service: Service, gmail: Path
) -> None:
    _with_family(service)
    source = _read(service, gmail)
    reply = service.call("mail.clean", {"source": source})
    assert reply["source"]["id"] == source and reply["source"]["account"] == "Gmail"
    groups = {g["key"]: g for g in reply["groups"]}
    assert [g["key"] for g in reply["groups"]] == [
        "lists", "notices", "unsubscribe", "spam_trash", "receipts"
    ]  # fmt: skip
    assert (groups["lists"]["senders"], groups["lists"]["mails"]) == (5, 11)
    assert groups["lists"]["rows"][0] == {
        "name": "The Daily Fold",
        "address": "news@dailyfold.example.com",
        "mails": 6,
        "size": groups["lists"]["rows"][0]["size"],
    }
    assert (groups["receipts"]["senders"], groups["receipts"]["mails"]) == (4, 5)
    totals = reply["left_out"]
    assert totals["mails"] == 23 and totals["senders"] == 14
    assert totals["size"] == sum(g["size"] for g in reply["groups"] if g["key"] != "receipts")
    assert reply["kept"] == {"mails": 56 - 23, "senders": reply["kept"]["senders"]}
    assert reply["kept_senders"] == []


def test_a_box_persons_address_protects_their_mail(service: Service, gmail: Path) -> None:
    """(Ana, João and Rui are protected anyway: the owner wrote to each of them.)"""
    source = _read(service, gmail)
    before = service.call("mail.clean", {"source": source})
    unsubscribe = {g["key"]: g for g in before["groups"]}["unsubscribe"]
    assert "deals@shop.example.com" in {r["address"] for r in unsubscribe["rows"]}
    with _box(service).master() as master:
        master.add_alias(master.add_person("Shop Deals"), "deals@shop.example.com", "email")
        master.commit()
    after = service.call("mail.clean", {"source": source})
    unsubscribe = {g["key"]: g for g in after["groups"]}["unsubscribe"]
    assert "deals@shop.example.com" not in {r["address"] for r in unsubscribe["rows"]}


def test_keeping_a_sender_takes_its_mail_out_and_is_remembered(
    service: Service, gmail: Path
) -> None:
    source = _read(service, gmail)
    reply = service.call(
        "mail.keep", {"source": source, "addresses": ["News@DailyFold.example.com"]}
    )
    lists = {g["key"]: g for g in reply["groups"]}["lists"]
    assert "news@dailyfold.example.com" not in {r["address"] for r in lists["rows"]}
    assert reply["kept_senders"] == [
        {"address": "news@dailyfold.example.com", "name": "The Daily Fold", "mails": 6,
         "size": reply["kept_senders"][0]["size"]}
    ]  # fmt: skip
    assert owner.load(_box(service))["mail"]["kept"] == ["news@dailyfold.example.com"]
    service.call("box.reset", {})
    assert owner.load(_box(service))["mail"]["kept"] == ["news@dailyfold.example.com"]
    source = _read(service, gmail)
    again = service.call("mail.clean", {"source": source})
    assert [k["address"] for k in again["kept_senders"]] == ["news@dailyfold.example.com"]
    undone = service.call(
        "mail.keep",
        {"source": source, "addresses": ["news@dailyfold.example.com"], "keep": False},
    )
    lists = {g["key"]: g for g in undone["groups"]}["lists"]
    assert "news@dailyfold.example.com" in {r["address"] for r in lists["rows"]}
    assert owner.load(_box(service))["mail"]["kept"] == []


def test_a_senders_mail_can_be_looked_at_before_deciding(service: Service, gmail: Path) -> None:
    source = _read(service, gmail)
    preview = service.call(
        "mail.preview", {"source": source, "address": "beatriz.lima@example.net"}
    )
    subjects = [m["subject"] for m in preview["mails"]]
    assert subjects == ["Book club in April", "Re: Book club in March", "Book club in March"]
    assert preview["mails"][0]["snippet"].startswith("April: we read the next one.")
    assert preview["mails"][0]["recipients"] == [["to", "Maria Costa", "maria.costa@example.com"]]
    wedding = service.call("mail.preview", {"source": source, "address": family.ANA.emails[0]})
    position = next(m["position"] for m in wedding["mails"] if m["subject"] == "Wedding update")
    message = service.call("mail.message", {"source": source, "position": position})
    assert message["subject"] == "Wedding update" and message["from"] == [
        "Ana Costa", "ana.costa@example.com"
    ]  # fmt: skip
    assert "The date is set: 14 June." in message["text"] and "<h1>" not in message["text"]


def test_writing_the_cleaned_mbox_is_a_job(service: Service, gmail: Path) -> None:
    _with_family(service)
    source = _read(service, gmail)
    service.call("mail.clean", {"source": source})
    job = service.call("mail.clean.write", {"source": source})
    assert job["kind"] == "mail-clean"
    done = service.wait(job["id"], timeout=60)
    assert done["status"] == "done", done["error"]
    result = done["result"]
    written = Path(result["path"])
    assert written.parent == gmail.parent and written.name.endswith("[Cleaned].mbox")
    assert (result["mails"], result["left_out"]) == (33, 23)
    assert written.stat().st_size == result["size"]
    sources = service.call("mail.sources")["sources"]
    child = next(s for s in sources if s["path"] == str(written))
    assert child["kind"] == "cleaned" and child["parent_id"] == source


def test_the_command_line_cleans(
    tmp_path: Path, gmail: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    box = tmp_path / "Box"
    assert cli.main(["box", "create", str(box), "--name", "Our box"]) == 0
    assert cli.main(["mail", "keep", "deals@shop.example.com", "--box", str(box)]) == 0
    capsys.readouterr()
    code = cli.main(["mail", "clean", str(gmail), "--account", "Gmail", "--box", str(box)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Lists and newsletters: 5 senders, 11 mails" in out
    assert "Unsubscribe links: 2 senders, 2 mails" in out  # the shop's deals were kept
    assert "Writing the cleaned mbox would leave out" in out
    code = cli.main(["mail", "clean", str(gmail), "--box", str(box), "--write"])
    out = capsys.readouterr().out
    assert code == 0 and "[Cleaned].mbox" in out
    assert len(list(gmail.parent.glob("*[[]Cleaned[]].mbox"))) == 1
