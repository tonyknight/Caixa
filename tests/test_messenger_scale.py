"""A whole Meta export: many threads under several top folders, imported without slowing down.

Facebook's export keeps threads in `inbox`, `e2ee_cutover`, `archived_threads`, `filtered_threads`,
`message_requests`, … Each holds one folder per thread with a `message_1.json`. Pointing Caixa at the
`messages` folder imports them all; the work per thread must not grow with the threads already read.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fixtures import family

from caixa.box import Box
from caixa.collectors.base import Collector, Progress
from caixa.collectors.chattr import collectors
from caixa.collectors.inputs import InputError
from caixa.collectors.options import validate

TOPS = ("e2ee_cutover", "inbox", "archived_threads", "filtered_threads", "message_requests")


@pytest.fixture(scope="module")
def messenger() -> Collector:
    return next(c for c in collectors() if c.info.id == "messenger")


@pytest.fixture
def box(tmp_path: Path) -> Box:
    new = Box.create(tmp_path / "Box", name="Test box")
    with new.master() as master:
        master.add_person(family.OWNER.name, is_owner=True)
    return new


def _thread(folder: Path, other: str, count: int, start: int = 0) -> None:
    folder.mkdir(parents=True)
    body = {
        "participants": [{"name": other}, {"name": family.OWNER.name}],
        "messages": [
            {
                "sender_name": other if n % 2 else family.OWNER.name,
                "timestamp_ms": 1_600_000_000_000 + (start + n) * 60_000,
                "content": f"message {start + n}",
            }
            for n in range(count)
        ],
        "title": other,
        "is_still_participant": True,
        "thread_path": f"{folder.parent.name}/{folder.name}",
    }
    (folder / "message_1.json").write_text(json.dumps(body), encoding="utf-8")


def _export(root: Path, per_top: int = 3, messages: int = 4) -> Path:
    """`your_facebook_activity/messages/<top>/<thread>/message_1.json`, plus the loose files."""
    base = root / "your_facebook_activity" / "messages"
    for top in TOPS:
        for n in range(per_top):
            _thread(base / top / f"friend{n}_{top}_{1000 + n}", f"Friend {top} {n}", messages)
    for loose in ("messaging_settings.json", "secret_conversations.json"):
        (base / loose).write_text("{}", encoding="utf-8")
    (base / "photos").mkdir()
    (base / "photos" / "1.jpg").write_bytes(b"jpg")
    return base


def test_every_top_folder_of_the_export_is_read(messenger: Collector, tmp_path: Path) -> None:
    preview = messenger.preview(_export(tmp_path), {})
    assert preview.conversations == len(TOPS) * 3
    assert preview.items == len(TOPS) * 3 * 4


def test_the_folder_above_messages_works_too(messenger: Collector, tmp_path: Path) -> None:
    source = _export(tmp_path).parent.parent  # the unzipped export itself
    assert messenger.preview(source, {}).conversations == len(TOPS) * 3


def test_people_are_linked_once_not_once_per_thread(
    messenger: Collector, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from chattr.database_manager import DatabaseManager

    calls = 0
    real = DatabaseManager.resolve_people

    def counting(self: DatabaseManager, *args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return real(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(DatabaseManager, "resolve_people", counting)
    messenger.preview(_export(tmp_path, per_top=6), {})
    assert calls <= 2  # it was 30 (one per thread, each over the whole archive)


def test_a_thread_with_no_messages_is_skipped_and_reported(
    messenger: Collector, tmp_path: Path
) -> None:
    base = _export(tmp_path)
    for n in range(2):
        _thread(base / "message_requests" / f"empty{n}_1", f"Empty {n}", 0)
    preview = messenger.preview(base, {})
    assert preview.conversations == len(TOPS) * 3
    assert any("2 conversations had no messages" in note for note in preview.warnings)


def test_an_export_where_every_thread_is_empty_is_still_refused(
    messenger: Collector, tmp_path: Path
) -> None:
    base = tmp_path / "messages"
    _thread(base / "inbox" / "empty_1", "Empty", 0)
    with pytest.raises(InputError, match="(?i)no messages"):
        messenger.preview(base, {})


def test_a_thread_split_across_two_top_folders_is_one_conversation_per_folder_but_one_person(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    base = tmp_path / "messages"
    _thread(base / "inbox" / "anacosta_1", family.ANA.name, 3)
    _thread(base / "e2ee_cutover" / "anacosta_9", family.ANA.name, 3, start=100)
    events: list[Progress] = []
    result = messenger.run(box, base, validate(messenger.info.options_schema, {}), events.append)
    assert result.inserted == 6
    with box.master() as master:
        people = [row[0] for row in master.connection.execute("SELECT name FROM people")]
    assert people.count(family.ANA.name) <= 1  # one Ana, however many folders she is in


def test_progress_counts_threads_as_they_are_read(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    events: list[Progress] = []
    messenger.run(
        box, _export(tmp_path), validate(messenger.info.options_schema, {}), events.append
    )
    importing = [e for e in events if e.stage == "importing"]
    assert importing[0].total == len(TOPS) * 3 and importing[-1].current == len(TOPS) * 3
    assert [e.current for e in importing] == sorted(e.current for e in importing)
