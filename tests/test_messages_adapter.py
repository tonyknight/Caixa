"""The messages adapter: Chattr's database into the master, by stable id, with a change log."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from fixtures import family

from caixa.collectors.messages import sync_chattr
from caixa.master import Master

ANA, JOAO, OWNER = family.ANA, family.JOAO, family.OWNER


@pytest.fixture
def chattr_copy(chattr_archive, tmp_path: Path) -> Path:
    """A private copy of chattr.sqlite the test may change."""
    copy = tmp_path / "chattr.sqlite"
    shutil.copy(chattr_archive.database, copy)
    return copy


def _count(path: Path, sql: str, *params: object) -> int:
    with sqlite3.connect(path) as db:
        return int(db.execute(sql, params).fetchone()[0])


def _roles(master: Master, body_start: str) -> set[tuple[str, str]]:
    rows = master.connection.execute(
        "SELECT p.name, ip.role FROM item_people ip JOIN people p ON p.id = ip.person_id "
        "JOIN items i ON i.id = ip.item_id WHERE i.text LIKE ?",
        (body_start + "%",),
    ).fetchall()
    return {(r[0], r[1]) for r in rows}


def test_every_message_becomes_an_item_with_its_stable_id(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        result = sync_chattr(master, chattr_archive.database)
        total = _count(chattr_archive.database, "SELECT COUNT(*) FROM messages")
        assert result.inserted == total > 0 and result.updated == 0 and result.unchanged == 0
        items = master.connection.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        assert items == total
        with sqlite3.connect(chattr_archive.database) as db:
            ids = {r[0] for r in db.execute("SELECT id FROM messages")}
        assert {r[0] for r in master.connection.execute("SELECT id FROM items")} == ids


def test_items_carry_type_time_text_hash_version_and_an_anchor(
    chattr_archive, tmp_path: Path
) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_archive.database)
        row = master.connection.execute(
            "SELECT * FROM items WHERE text LIKE 'Que lindo%'"
        ).fetchone()
    assert (row["type"], row["collector"], row["service"]) == ("text", "chattr", "WhatsApp")
    assert row["timestamp_utc"].startswith("2024-03-01T14:06") and row["time_precision"] == "second"
    assert row["privacy"] == "private" and row["version"] == 1 and row["content_hash"]
    assert row["anchor"] == f"#m-{row['id']}" and row["file_path"] is None


def test_a_voicemails_transcript_and_a_calls_type_are_kept(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_archive.database)
        types = {r[0] for r in master.connection.execute("SELECT DISTINCT type FROM items")}
        voicemail = master.connection.execute(
            "SELECT text FROM items WHERE type = 'voicemail'"
        ).fetchone()
    assert {"text", "media", "system", "call", "voicemail", "email"} <= types
    assert voicemail["text"].startswith("Hi Mãe, it's Ana.")


def test_each_insert_is_one_change_log_row_with_a_growing_number(
    chattr_archive, tmp_path: Path
) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        result = sync_chattr(master, chattr_archive.database)
        changes = master.changes()
    assert len(changes) == result.inserted
    assert [c.operation for c in changes] == ["insert"] * len(changes)
    numbers = [c.change for c in changes]
    assert numbers == sorted(numbers) and len(set(numbers)) == len(numbers)
    assert {c.import_id for c in changes} == {result.import_id} and {
        c.version for c in changes
    } == {1}


def test_the_import_is_recorded(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        result = sync_chattr(master, chattr_archive.database)
        (record,) = master.imports()
    assert (record.collector, record.status) == ("chattr", "done")
    assert record.inserted == result.inserted and record.source == str(chattr_archive.database)


# --- People -----------------------------------------------------------------------------------


def test_senders_recipients_and_the_owner_are_linked(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_archive.database)
        assert master.owner_id() == master.person_id(OWNER.name)
        assert _roles(master, "Bom dia Mãe") == {(ANA.name, "sender"), (OWNER.name, "recipient")}
        assert _roles(master, "Thank God") == {(OWNER.name, "sender"), (ANA.name, "recipient")}


def test_group_messages_link_the_other_participants(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_archive.database)
        assert _roles(master, "Christmas at my place") == {
            (JOAO.name, "sender"),
            (ANA.name, "participant"),
            (OWNER.name, "participant"),
        }


def test_mail_recipients_are_found_through_the_aliases(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_archive.database)
        assert _roles(master, "Olá Maria,") == {(JOAO.name, "sender"), (OWNER.name, "recipient")}


def test_an_unknown_sender_has_no_person_links(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_archive.database)
        assert _roles(master, "Your package") == {(OWNER.name, "recipient")}


def test_the_handles_chattr_resolved_become_aliases(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        result = sync_chattr(master, chattr_archive.database)
        ana = master.person_id(ANA.name)
        assert master.find_person(ANA.phones[0]) == ana
        assert master.find_person(JOAO.emails[0]) == master.person_id(JOAO.name)
        assert result.aliases > 0 and result.people >= 3
        assert {a.source for a in master.aliases(ana)} == {"chattr"}


def test_aliases_json_from_the_master_feeds_chattr_back(chattr_archive, tmp_path: Path) -> None:
    from chattr.people import Aliases

    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_archive.database)
        master.export_aliases(tmp_path / "aliases.json")
    aliases = Aliases.from_json(tmp_path / "aliases.json")
    assert aliases.lookup(ANA.phones[0]) == ANA.name and aliases.lookup(JOAO.emails[0]) == JOAO.name


def test_unresolved_handles_are_reported(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        result = sync_chattr(master, chattr_archive.database)
    unresolved = {(u.service, u.identifier): u for u in result.unresolved}
    assert unresolved[("iMessage", family.UNKNOWN_HANDLE)].messages == 1
    assert ("iMessage", ANA.phones[0]) not in unresolved


# --- Syncing again --------------------------------------------------------------------------


def test_syncing_unchanged_data_writes_no_change_log_rows(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        first = sync_chattr(master, chattr_archive.database)
        before = len(master.changes())
        second = sync_chattr(master, chattr_archive.database)
        assert len(master.changes()) == before
        assert (second.inserted, second.updated, second.linked) == (0, 0, 0)
        assert second.unchanged == first.inserted
        assert len(master.imports()) == 2  # each run is still recorded


def test_a_changed_message_is_an_update_with_a_new_version(
    chattr_copy: Path, tmp_path: Path
) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_copy)
        with sqlite3.connect(chattr_copy) as db:
            message_id = db.execute(
                "SELECT id FROM messages WHERE body LIKE 'Que lindo%'"
            ).fetchone()[0]
            db.execute(
                "UPDATE messages SET body = 'Que lindo! Buy three.', content_hash = 'new', version = 2 WHERE id = ?",
                (message_id,),
            )
        before = len(master.changes())
        result = sync_chattr(master, chattr_copy)
        assert (result.inserted, result.updated) == (0, 1)
        update = master.changes()[before:]
        assert [(c.operation, c.item_id, c.version) for c in update] == [("update", message_id, 2)]
        assert master.connection.execute(
            "SELECT text, version FROM items WHERE id = ?", (message_id,)
        ).fetchone()[:] == ("Que lindo! Buy three.", 2)


def test_what_a_person_decided_survives_an_update(chattr_copy: Path, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_copy)
        master.connection.execute(
            "UPDATE items SET privacy = 'family' WHERE text LIKE 'Que lindo%'"
        )
        with sqlite3.connect(chattr_copy) as db:
            db.execute(
                "UPDATE messages SET content_hash = 'new', version = 2 WHERE body LIKE 'Que lindo%'"
            )
        sync_chattr(master, chattr_copy)
        assert (
            master.connection.execute(
                "SELECT privacy FROM items WHERE text LIKE 'Que lindo%'"
            ).fetchone()[0]
            == "family"
        )


def test_linking_a_handle_later_logs_a_link_for_exactly_its_items(
    chattr_copy: Path, tmp_path: Path
) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_copy)
        before = len(master.changes())
        with sqlite3.connect(chattr_copy) as db:
            db.execute(
                "UPDATE handles SET person = 'Delivery Service' WHERE identifier = ?",
                (family.UNKNOWN_HANDLE,),
            )
            stranger = {
                r[0]
                for r in db.execute(
                    "SELECT m.id FROM messages m JOIN handles h ON h.id = m.sender_handle_id WHERE h.identifier = ?",
                    (family.UNKNOWN_HANDLE,),
                )
            }
        result = sync_chattr(master, chattr_copy)
        logged = master.changes()[before:]
        assert {(c.operation, c.item_id) for c in logged} == {("link", i) for i in stranger}
        assert result.linked == len(stranger) and result.inserted == 0 and result.updated == 0
        assert ("Delivery Service", "sender") in _roles(master, "Your package")
        assert master.find_person(family.UNKNOWN_HANDLE) == master.person_id("Delivery Service")
        assert result.unresolved == [] or all(
            u.identifier != family.UNKNOWN_HANDLE for u in result.unresolved
        )


def test_an_overlapping_second_archive_adds_only_what_is_new(
    chattr_archive, chattr_copy: Path, tmp_path: Path
) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        first = sync_chattr(master, chattr_archive.database)
        before = len(master.changes())
        with sqlite3.connect(chattr_copy) as db:
            conversation = db.execute("SELECT id FROM conversations LIMIT 1").fetchone()[0]
            db.execute(
                "INSERT INTO messages (id, conversation_id, timestamp_utc, content_type, body, content_hash) "
                "VALUES ('extra-1', ?, '2026-01-01T00:00:00+00:00', 'text', 'a brand new message', 'h')",
                (conversation,),
            )
        second = sync_chattr(master, chattr_copy)
        assert (second.inserted, second.updated) == (1, 0) and second.unchanged == first.inserted
        assert [c.item_id for c in master.changes()[before:]] == ["extra-1"]


def test_pages_are_recorded_without_touching_the_change_log(chattr_archive, tmp_path: Path) -> None:
    with sqlite3.connect(chattr_archive.database) as db:
        message_id = db.execute("SELECT id FROM messages WHERE body LIKE 'Que lindo%'").fetchone()[
            0
        ]
    page = "Messages/Ana Costa/(2024) Ana Costa.html"
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_archive.database)
        before = len(master.changes())
        result = sync_chattr(master, chattr_archive.database, pages={message_id: page})
        assert (
            master.connection.execute(
                "SELECT file_path FROM items WHERE id = ?", (message_id,)
            ).fetchone()[0]
            == page
        )
        assert len(master.changes()) == before and result.updated == 0
        sync_chattr(master, chattr_archive.database)  # a sync without pages keeps what it knew
        assert (
            master.connection.execute(
                "SELECT file_path FROM items WHERE id = ?", (message_id,)
            ).fetchone()[0]
            == page
        )


def test_no_duplicate_links(chattr_archive, tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_archive.database)
        sync_chattr(master, chattr_archive.database)
        dupes = master.connection.execute(
            "SELECT COUNT(*) FROM (SELECT 1 FROM item_people GROUP BY item_id, person_id, role HAVING COUNT(*) > 1)"
        ).fetchone()[0]
    assert dupes == 0


# --- The handoff ----------------------------------------------------------------------------


def test_chattrs_database_is_read_only_to_the_adapter(chattr_copy: Path, tmp_path: Path) -> None:
    before = hashlib.sha256(chattr_copy.read_bytes()).hexdigest()
    with Master(tmp_path / "caixa.sqlite") as master:
        sync_chattr(master, chattr_copy)
        with pytest.raises(sqlite3.OperationalError):
            master.connection.execute(
                "ATTACH DATABASE ? AS probe", (f"file:{chattr_copy}?mode=ro",)
            )
            master.connection.execute("CREATE TABLE probe.intruder (a)")
    assert hashlib.sha256(chattr_copy.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in chattr_copy.parent.iterdir() if p.name.startswith("chattr")) == [
        "chattr.sqlite"
    ]


def test_a_missing_chattr_database_is_a_plain_error(tmp_path: Path) -> None:
    with Master(tmp_path / "caixa.sqlite") as master:
        with pytest.raises(FileNotFoundError):
            sync_chattr(master, tmp_path / "nothing.sqlite")
        assert master.imports() == []  # nothing recorded for a run that never started


def test_a_failed_sync_leaves_the_master_unchanged(chattr_copy: Path, tmp_path: Path) -> None:
    with sqlite3.connect(chattr_copy) as db:
        db.execute("DROP TABLE reactions")
        db.execute("ALTER TABLE messages RENAME COLUMN timestamp_utc TO broken")
    with Master(tmp_path / "caixa.sqlite") as master:
        with pytest.raises(sqlite3.Error):
            sync_chattr(master, chattr_copy)
        assert master.connection.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
        assert master.changes() == []
        (record,) = master.imports()
        assert record.status == "failed"
