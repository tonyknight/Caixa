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
