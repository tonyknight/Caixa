"""`caixa …` on the command line: the same service layer the worker uses, so the same results."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fixtures import family

from caixa import cli
from caixa.service import Service


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _whatsapp(fixture_family) -> str:
    return str(fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt")


@pytest.fixture
def box(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    path = tmp_path / "Box"
    code, _, _ = _run(
        capsys, "box", "create", str(path), "--name", "Our box", "--owner", family.OWNER.name
    )
    assert code == 0
    return path


def _rows(box: Path) -> list[tuple[Any, ...]]:
    with sqlite3.connect(box / ".caixa" / "caixa.sqlite") as db:
        return [
            tuple(r)
            for r in db.execute("SELECT id, type, file_path, anchor FROM items ORDER BY id")
        ]


def _files(box: Path) -> list[str]:
    return sorted(
        str(p.relative_to(box))
        for p in box.rglob("*")
        if p.is_file() and not str(p.relative_to(box)).startswith(".caixa")
    )


# --- Boxes and collectors -------------------------------------------------------------------


def test_a_box_is_created_and_described(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(
        capsys, "box", "create", str(tmp_path / "Box"), "--name", "Our box", "--json"
    )
    assert code == 0 and json.loads(out)["name"] == "Our box"
    code, out, _ = _run(capsys, "box", "status", "--box", str(tmp_path / "Box"))
    assert code == 0 and "Our box" in out and "0 items" in out
    code, out, err = _run(capsys, "box", "create", str(tmp_path / "Box"))
    assert code == 1 and "already" in err and out == ""


def test_the_box_can_come_from_the_environment_or_the_folder_you_are_in(
    box: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    code, _, err = _run(capsys, "box", "status")
    assert code == 1 and "--box" in err and "CAIXA_BOX" in err
    monkeypatch.setenv("CAIXA_BOX", str(box))
    assert _run(capsys, "box", "status")[0] == 0
    monkeypatch.delenv("CAIXA_BOX")
    monkeypatch.chdir(box)
    assert _run(capsys, "box", "status")[0] == 0


def test_collectors_are_listed_and_explained(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys, "collectors")
    assert code == 0 and "whatsapp" in out and "iMessage" in out
    code, out, _ = _run(capsys, "collectors", "whatsapp")
    assert code == 0 and "Export chat" in out and "contacts" in out
    code, out, _ = _run(capsys, "collectors", "--json")
    assert {c["id"] for c in json.loads(out)} >= {"imessage", "voicemail"}
    code, _, err = _run(capsys, "collectors", "telegram")
    assert code == 1 and "No collector" in err


# --- Importing ------------------------------------------------------------------------------


def test_an_import_reports_what_it_did(
    box: Path, fixture_family, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = _run(
        capsys, "import", "whatsapp", _whatsapp(fixture_family), "--box", str(box)
    )
    assert code == 0, err
    assert "7 new" in out and "0 changed" in out and "Ana Costa" in out  # unnamed handle reported
    assert "rendering" in err  # progress goes to stderr, results to stdout
    assert len(_rows(box)) == 7
    code, out, _ = _run(capsys, "import", "whatsapp", _whatsapp(fixture_family), "--box", str(box))
    assert code == 0 and "0 new" in out and "7 unchanged" in out


def test_a_cli_import_gives_the_same_rows_and_files_as_the_service(
    box: Path, fixture_family, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sources = [
        ("whatsapp", _whatsapp(fixture_family)),
        ("mail", str(fixture_family.paths["mbox"])),
        ("googlevoice", str(fixture_family.paths["google_voice"])),
    ]
    for collector, source in sources:
        assert _run(capsys, "import", collector, source, "--box", str(box))[0] == 0
    other = Service(roots=[tmp_path])
    other.box_create(str(tmp_path / "Other"), owner=family.OWNER.name)
    for collector, source in sources:
        job = other.import_start(collector, source)
        assert other.wait(job["id"], 60)["status"] == "done"
    other.close()
    assert _rows(box) == _rows(tmp_path / "Other") and len(_rows(box)) == 7 + 4 + 6
    assert _files(box) == _files(tmp_path / "Other")


def test_a_preview_counts_and_writes_nothing(
    box: Path, fixture_family, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = _run(
        capsys, "import", "whatsapp", _whatsapp(fixture_family), "--box", str(box), "--preview"
    )
    assert code == 0 and "7 items" in out and "1 conversation" in out and "2024-03-01" in out
    assert _rows(box) == [] and _run(capsys, "jobs", "--box", str(box))[1].strip() == "No jobs yet."
    code, out, _ = _run(
        capsys,
        "import",
        "whatsapp",
        _whatsapp(fixture_family),
        "--box",
        str(box),
        "--preview",
        "--json",
    )
    assert json.loads(out)["items"] == 7


def test_options_are_typed_by_the_collectors_schema(
    box: Path, fixture_family, capsys: pytest.CaptureFixture[str]
) -> None:
    source = str(fixture_family.paths["imessage"])
    code, out, err = _run(
        capsys, "import", "imessage", source, "--box", str(box),
        "--option", "spam_mode=disabled", "--option", "workers=1",
    )  # fmt: skip
    assert code == 0, err
    assert "7 new" in out
    code, _, err = _run(
        capsys, "import", "imessage", source, "--box", str(box),
        "--option", "spam_mode=nope", "--option", "colour=red",
    )  # fmt: skip
    assert code == 1 and "spam_mode" in err and "colour" in err
    code, _, err = _run(
        capsys, "import", "imessage", source, "--box", str(box), "--option", "workers"
    )
    assert code == 1 and "name=value" in err
    code, _, err = _run(
        capsys, "import", "imessage", source, "--box", str(box), "--option", "workers=lots"
    )
    assert code == 1 and "workers" in err


def test_a_missing_source_and_a_failed_import_are_explained(
    box: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = _run(
        capsys, "import", "whatsapp", str(tmp_path / "none.txt"), "--box", str(box)
    )
    assert code == 1 and "Not found" in err and out == ""
    (tmp_path / "empty").mkdir()
    code, out, err = _run(capsys, "import", "whatsapp", str(tmp_path / "empty"), "--box", str(box))
    assert code == 1 and "Nothing to import" in err


def test_jobs_are_listed(box: Path, fixture_family, capsys: pytest.CaptureFixture[str]) -> None:
    _run(capsys, "import", "whatsapp", _whatsapp(fixture_family), "--box", str(box))
    code, out, _ = _run(capsys, "jobs", "--box", str(box))
    assert code == 0 and "whatsapp" in out and "done" in out
    code, out, _ = _run(capsys, "jobs", "--box", str(box), "--json", "--limit", "1")
    assert [j["status"] for j in json.loads(out)] == ["done"]


# --- People ---------------------------------------------------------------------------------


def test_people_are_named_renamed_and_merged_from_the_command_line(
    box: Path, fixture_family, capsys: pytest.CaptureFixture[str]
) -> None:
    b = str(box)
    _run(capsys, "import", "whatsapp", _whatsapp(fixture_family), "--box", b)
    _run(capsys, "import", "imessage", str(fixture_family.paths["imessage"]), "--box", b)
    code, out, _ = _run(capsys, "people", "unresolved", "--box", b)
    assert code == 0 and "WhatsApp" in out and "Ana Costa" in out
    code, out, err = _run(capsys, "people", "link", "WhatsApp", "Ana Costa", "Ana A", "--box", b)
    assert code == 0, err
    assert (box / "Messages" / "Ana A" / "(2024) Ana A.html").is_file()
    assert not (box / "Messages" / "Ana Costa" / "(2024) Ana Costa.html").exists()
    _run(capsys, "people", "link", "iMessage", family.ANA.phones[0], "Ana B", "--box", b)
    code, out, _ = _run(capsys, "people", "list", "--box", b, "--json")
    ids = {p["name"]: p["id"] for p in json.loads(out)["people"]}
    code, _, err = _run(
        capsys, "people", "link", "iMessage", family.ANA.phones[0], "Ana A", "--box", b
    )
    assert code == 1 and "already names Ana B" in err
    code, _, err = _run(capsys, "people", "rename", str(ids["Ana A"]), "Ana B", "--box", b)
    assert code == 1 and "merge" in err
    assert _run(capsys, "people", "rename", str(ids["Ana A"]), "Ana Cruz", "--box", b)[0] == 0
    assert (box / "Messages" / "Ana Cruz" / "(2024) Ana Cruz.html").is_file()
    code, out, err = _run(
        capsys, "people", "merge", str(ids["Ana B"]), str(ids["Ana A"]), "--box", b
    )
    assert code == 0, err
    _, out, _ = _run(capsys, "people", "list", "--box", b, "--json")
    assert "Ana B" not in {p["name"] for p in json.loads(out)["people"]}


def test_the_owner_cannot_be_merged_away_from_the_command_line(
    box: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, out, _ = _run(capsys, "people", "list", "--box", str(box), "--json")
    owner = next(p for p in json.loads(out)["people"] if p["is_owner"])
    code, _, err = _run(capsys, "people", "merge", str(owner["id"]), "99", "--box", str(box))
    assert code == 1 and err


# --- The worker -----------------------------------------------------------------------------


def test_the_worker_command_hands_over_to_the_worker(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr("caixa.worker.main", lambda argv: seen.append(list(argv)) or 0)
    code = cli.main(["worker", "--box", str(tmp_path), "--read-only"])
    assert code == 0 and seen == [["--box", str(tmp_path), "--read-only"]]


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys)
    assert code == 0 and "import" in out and "worker" in out
