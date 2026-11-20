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


# --- Sorting through the service (ticket 06) --------------------------------------------------------


def _categories(reply: dict) -> dict[str, set[str]]:  # type: ignore[type-arg]
    return {c["key"]: {r["address"] for r in c["rows"]} for c in reply["categories"]}


def test_the_senders_are_sorted_with_the_boxs_people(service: Service, gmail: Path) -> None:
    _with_family(service)
    source = _read(service, gmail)
    reply = service.call("mail.senders", {"source": source})
    found = _categories(reply)
    assert [c["key"] for c in reply["categories"]] == [
        "known", "to_sort", "to_import", "ignored", "imported"
    ]  # fmt: skip
    assert found["to_import"] == {
        "ana.costa@example.com", "joao.costa@example.org", "rui.pereira@example.org"
    }  # fmt: skip
    home = next(
        r for c in reply["categories"] for r in c["rows"] if r["address"] == "rui.home@example.net"
    )
    assert (home["known_by"], home["person"], home["chosen"]) == ("name", "Rui Pereira", False)
    assert reply["selection"] == {
        "threads": 7, "mails": 14, "size": reply["selection"]["size"], "senders": 3
    }  # fmt: skip


def test_choices_and_ignores_are_remembered(service: Service, gmail: Path) -> None:
    _with_family(service)
    source = _read(service, gmail)
    reply = service.call(
        "mail.choose", {"source": source, "addresses": ["beatriz.lima@example.net"]}
    )
    assert "beatriz.lima@example.net" in _categories(reply)["to_import"]
    assert reply["selection"]["mails"] == 18
    reply = service.call("mail.ignore", {"source": source, "addresses": ["ana.costa@example.com"]})
    assert "ana.costa@example.com" in _categories(reply)["ignored"]
    assert reply["selection"]["mails"] == 14
    service.call("box.reset", {})
    _with_family(service)
    source = _read(service, gmail)
    service.call("mail.clean", {"source": source})
    done = service.wait(service.call("mail.clean.write", {"source": source})["id"], timeout=60)
    child = done["result"]["source_id"]
    found = _categories(service.call("mail.senders", {"source": child}))
    assert "beatriz.lima@example.net" in found["to_import"]
    assert "ana.costa@example.com" in found["ignored"]
    undone = service.call(
        "mail.ignore", {"source": child, "addresses": ["ana.costa@example.com"], "ignore": False}
    )
    assert "ana.costa@example.com" in _categories(undone)["to_import"]


def test_the_owners_addresses_are_proposed_and_confirmed(service: Service, gmail: Path) -> None:
    source = _read(service, gmail)
    proposed = service.call("mail.owner", {"source": source})
    assert proposed == {
        "account": "Gmail", "confirmed": [], "proposed": ["maria.costa@example.com"]
    }  # fmt: skip
    confirmed = service.call(
        "mail.owner.set", {"source": source, "addresses": ["maria.costa@example.com"]}
    )
    assert confirmed["confirmed"] == ["maria.costa@example.com"]
    assert owner.mail_owner(_box(service), "Gmail") == ["maria.costa@example.com"]


def test_the_command_line_sorts(
    tmp_path: Path, gmail: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    box = tmp_path / "Box"
    assert cli.main(["box", "create", str(box), "--name", "Our box"]) == 0
    with Box.open(box).master() as master:
        master.add_alias(master.add_person("Ana Costa"), "ana.costa@example.com", "email")
        master.commit()
    assert cli.main(["mail", "choose", "beatriz.lima@example.net", "--box", str(box)]) == 0
    assert cli.main(["mail", "ignore", "news@dailyfold.example.com", "--box", str(box)]) == 0
    capsys.readouterr()
    code = cli.main(["mail", "senders", str(gmail), "--account", "Gmail", "--box", str(box)])
    out = capsys.readouterr().out
    assert code == 0
    assert "To import: 2 senders" in out and "Ignored: 1 sender" in out
    assert "Importing would bring 8 mails in 5 conversations" in out


# --- Importing the chosen conversations (ticket 09) -------------------------------------------------


def _subjects(service: Service) -> list[str]:
    with _box(service).master() as master:
        return sorted(r[0] for r in master.connection.execute("SELECT subject FROM mail"))


def _imported(service: Service, source: int) -> dict:  # type: ignore[type-arg]
    job = service.call("mail.import", {"source": source})
    assert job["kind"] == "mail-import"
    done = service.wait(job["id"], timeout=120)
    assert done["status"] == "done", done["error"]
    return done


def test_importing_brings_exactly_the_chosen_conversations(service: Service, gmail: Path) -> None:
    with _box(service).master() as master:
        master.add_alias(master.add_person("Rui Pereira"), family.RUI.emails[0], "email")
        master.add_alias(master.add_person("João Costa"), family.JOAO.emails[0], "email")
        master.commit()
    source = _read(service, gmail)
    service.call("mail.choose", {"source": source, "addresses": ["beatriz.lima@example.net"]})
    preview = service.call("mail.import.preview", {"source": source})
    assert (preview["senders"], preview["conversations"], preview["mails"]) == (3, 6, 14)
    assert preview["files"] == 5 and preview["size"] > 0
    done = _imported(service, source)
    assert done["result"]["mails"] == 14 and done["result"]["conversations"] == 6
    found = _subjects(service)
    assert found.count("Lunch next week?") == 1  # the owner's unanswered mail to Rui
    assert sum("Book club" in s for s in found) == 4
    assert "Sintra walk on Saturday" not in found  # Pedro's post on the list
    assert found.count("Re: Sintra walk on Saturday") == 2  # João's and the owner's
    assert len(found) == 14
    assert not list((_box(service).caixa_dir / "work" / "mail").glob("*.mbox"))


def test_importing_again_adds_nothing_and_the_chosen_are_imported(
    service: Service, gmail: Path
) -> None:
    source = _read(service, gmail)
    service.call("mail.choose", {"source": source, "addresses": ["beatriz.lima@example.net"]})
    first = _imported(service, source)
    assert first["result"]["inserted"] == 4
    reply = service.call("mail.senders", {"source": source})
    assert "beatriz.lima@example.net" in _categories(reply)["imported"]
    assert "beatriz.lima@example.net" not in _categories(reply)["to_import"]
    with pytest.raises(ServiceError, match="Nothing"):
        service.call("mail.import", {"source": source})


def test_an_import_of_mail_can_be_undone(service: Service, gmail: Path) -> None:
    source = _read(service, gmail)
    service.call("mail.choose", {"source": source, "addresses": ["beatriz.lima@example.net"]})
    _imported(service, source)
    assert len(_subjects(service)) == 4
    done = service.wait(service.call("import.undo")["id"], timeout=120)
    assert done["status"] == "done", done["error"]
    assert _subjects(service) == []


def test_the_command_line_imports(
    tmp_path: Path, gmail: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    box = tmp_path / "Box"
    assert cli.main(["box", "create", str(box), "--name", "Our box"]) == 0
    assert cli.main(["mail", "choose", "beatriz.lima@example.net", "--box", str(box)]) == 0
    capsys.readouterr()
    code = cli.main(["mail", "import", str(gmail), "--account", "Gmail", "--box", str(box)])
    out = capsys.readouterr().out
    assert code == 0 and "4 new" in out and "2 conversations" in out
