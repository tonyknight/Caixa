"""Caixa's master database: migrations, people, aliases, imports, and an append-only change log."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from caixa.master import Master
from caixa.schema import CURRENT_VERSION, MIGRATIONS


def _tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as db:
        return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_a_new_master_has_every_table(tmp_path: Path) -> None:
    path = tmp_path / ".caixa" / "caixa.sqlite"
    with Master(path):
        pass
    assert {
        "people",
        "aliases",
        "items",
        "item_people",
        "imports",
        "change_log",
        "schema_version",
    } <= _tables(path)


def test_migrations_are_ordered_and_idempotent(tmp_path: Path) -> None:
    assert [v for v, _ in MIGRATIONS] == list(range(1, len(MIGRATIONS) + 1))
    path = tmp_path / "caixa.sqlite"
    with Master(path):
        pass
    with sqlite3.connect(path) as db:
        before = db.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
    with Master(path) as master:
        assert master.version == CURRENT_VERSION
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall() == before
        assert db.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == CURRENT_VERSION


def test_the_database_is_created_with_its_folder(tmp_path: Path) -> None:
    path = tmp_path / "Box" / ".caixa" / "caixa.sqlite"
    with Master(path):
        pass
    assert path.is_file()


# --- People and aliases ---------------------------------------------------------------------


def test_people_are_get_or_create_and_case_insensitive(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        ana = master.add_person("Ana Costa")
        assert master.add_person("ana costa") == ana
        assert master.add_person("  Ana Costa ") == ana
        assert master.add_person("Rui Pereira") != ana
        assert [p.name for p in master.people()] == ["Ana Costa", "Rui Pereira"]
        assert master.person_id("ANA COSTA") == ana and master.person_id("Nobody") is None


def test_one_owner_at_most(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        maria = master.add_person("Maria Costa", is_owner=True)
        assert master.owner_id() == maria
        with pytest.raises(ValueError, match="owner"):
            master.add_person("Someone Else", is_owner=True)


def test_an_alias_names_a_person_by_a_phone_email_username_or_name(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        ana = master.add_person("Ana Costa")
        master.add_alias(ana, "+1 (555) 0101", "phone")
        master.add_alias(ana, "Ana.Costa@Example.com", "email")
        master.add_alias(ana, "anita", "username", service="Instagram")
        master.add_alias(ana, "Aninha", "name")
        found = {(a.kind, a.normalized, a.service) for a in master.aliases(ana)}
        assert found == {
            ("phone", "+15550101", None),
            ("email", "ana.costa@example.com", None),
            ("username", "anita", "Instagram"),
            ("name", "aninha", None),
        }
        assert (
            master.find_person("(555) 0101 ".replace("(", "+1 (")) == ana
        )  # same number, other punctuation
        assert master.find_person("ANA.COSTA@EXAMPLE.COM") == ana


def test_the_same_alias_cannot_name_two_people(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        ana, rui = master.add_person("Ana Costa"), master.add_person("Rui Pereira")
        master.add_alias(ana, "+15550101", "phone")
        master.add_alias(ana, "+1 555 0101", "phone")  # the same thing again: fine
        with pytest.raises(ValueError, match="already names"):
            master.add_alias(rui, "+15550101", "phone")


def test_an_alias_can_move_when_asked(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        ana, rui = master.add_person("Ana Costa"), master.add_person("Rui Pereira")
        master.add_alias(ana, "shared@example.com", "email")
        master.add_alias(rui, "shared@example.com", "email", move=True)
        assert master.find_person("shared@example.com") == rui


def test_a_bad_alias_kind_or_value_is_rejected(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        ana = master.add_person("Ana")
        with pytest.raises(ValueError, match="kind"):
            master.add_alias(ana, "x", "fax")
        with pytest.raises(ValueError, match="empty"):
            master.add_alias(ana, "  ", "name")


def test_aliases_json_is_what_chattr_reads(tmp_path: Path) -> None:
    out = tmp_path / "aliases.json"
    with Master(tmp_path / "m.sqlite") as master:
        ana = master.add_person("Ana Costa")
        master.add_alias(ana, "+1 555 0101", "phone")
        master.add_alias(ana, "ana.costa@example.com", "email")
        master.add_alias(
            master.add_person("Rui Pereira"), "rui.pereira.example", "username", service="Instagram"
        )
        assert master.export_aliases(out) == 3
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data == {
        "+1 555 0101": "Ana Costa",
        "ana.costa@example.com": "Ana Costa",
        "rui.pereira.example": "Rui Pereira",
    }
    assert out.read_text(encoding="utf-8").endswith("\n")


def test_aliases_json_is_the_same_every_time(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        ana = master.add_person("Ana")
        for value in ("b@example.com", "a@example.com", "+15550101"):
            master.add_alias(ana, value, "email" if "@" in value else "phone")
        master.export_aliases(tmp_path / "1.json")
        master.export_aliases(tmp_path / "2.json")
    assert (tmp_path / "1.json").read_bytes() == (tmp_path / "2.json").read_bytes()


# --- Imports and the change log -------------------------------------------------------------


def test_an_import_is_recorded_with_its_counts(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        import_id = master.start_import("chattr", tmp_path / "chattr.sqlite")
        master.finish_import(import_id, inserted=3, updated=1, unchanged=7, linked=2)
        (record,) = master.imports()
        assert (record.collector, record.inserted, record.updated, record.unchanged, record.linked) == (
            "chattr", 3, 1, 7, 2,
        )  # fmt: skip
        assert record.finished_at and record.status == "done"


def _item(master: Master, item_id: str = "m1") -> None:
    master.connection.execute(
        "INSERT INTO items (id, type, collector, timestamp_utc, content_hash) "
        "VALUES (?, 'text', 'chattr', '2024-01-01T00:00:00+00:00', 'h')",
        (item_id,),
    )


def test_change_numbers_only_grow(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        _item(master)
        numbers = [
            master.log_change("m1", "insert", 1, None),
            master.log_change("m1", "update", 2, None),
        ]
        assert numbers == sorted(numbers) and len(set(numbers)) == 2
        assert [c.operation for c in master.changes()] == ["insert", "update"]
        assert [c.change for c in master.changes(since=numbers[0])] == [numbers[1]]


def test_the_change_log_is_append_only(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        _item(master)
        master.log_change("m1", "insert", 1, None)
        db = master.connection
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db.execute("UPDATE change_log SET version = 9")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db.execute("DELETE FROM change_log")
        # even after deleting everything else, numbers are never reused
        first = master.log_change("m1", "update", 2, None)
        assert first > 1


def test_an_unknown_operation_is_rejected(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        _item(master)
        with pytest.raises(ValueError, match="operation"):
            master.log_change("m1", "explode", 1, None)


def test_items_need_a_known_privacy_and_role(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        _item(master)
        db = master.connection
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE items SET privacy = 'secret' WHERE id = 'm1'")
        person = master.add_person("Ana")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO item_people VALUES ('m1', ?, 'overlord')", (person,))
        db.execute("INSERT INTO item_people VALUES ('m1', ?, 'sender')", (person,))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO item_people VALUES ('nope', ?, 'sender')", (person,))


def test_a_new_item_is_private_by_default(tmp_path: Path) -> None:
    with Master(tmp_path / "m.sqlite") as master:
        _item(master)
        assert master.connection.execute("SELECT privacy, version FROM items").fetchone() == (
            "private",
            1,
        )
