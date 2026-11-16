"""Messenger limited to the owner's Facebook friends: Marketplace and strangers are left out, and
friends are named by the name Facebook gives them."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from caixa.box import Box
from caixa.collectors.base import Collector
from caixa.collectors.inputs import InputError
from caixa.collectors.options import validate
from caixa.collectors.registry import discover

ME = "Maria Costa"


def _mojibake(text: str) -> str:
    return text.encode("utf-8").decode("latin-1")


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")


def _thread(root: Path, folder: str, people: list[str], app: str = "facebook") -> None:
    others = [p for p in people if p != ME]
    _write(
        root / f"your_{app}_activity" / "messages" / "inbox" / folder / "message_1.json",
        {
            "participants": [{"name": _mojibake(p)} for p in people],
            "messages": [
                # in a group, the owner writes too (groups they never wrote in are left out)
                {"sender_name": _mojibake(ME if n and len(others) > 1 else others[0]),
                 "timestamp_ms": 1600000000000 + n, "content": f"message {n} in {folder}"}
                for n in range(2)
            ],
            "title": _mojibake(", ".join(others)),
            "thread_path": f"inbox/{folder}",
        },
    )  # fmt: skip


def _export(root: Path, friends: bool = True) -> Path:
    _thread(root, "joaocosta_1", ["João Costa", ME])  # a friend
    _thread(root, "ruipereira_2", ["Rui Pereira", ME])  # unfriended since
    _thread(root, "buyer_3", ["Marketplace Buyer", ME])  # a stranger
    _thread(root, "seller_4", ["Sofa Seller", ME])  # another
    _thread(root, "family_5", ["João Costa", "Cousin Not Friend", ME])  # a group with a friend
    _thread(root, "igfriend_6", ["Insta Person", ME], app="instagram")  # Instagram: untouched
    if friends:
        _write(root / "connections" / "friends" / "your_friends.json",
               {"friends_v2": [{"name": _mojibake("João Costa"), "timestamp": 1}]})  # fmt: skip
        _write(root / "connections" / "friends" / "removed_friends.json",
               {"deleted_friends_v2": [{"name": "Rui Pereira", "timestamp": 2}]})  # fmt: skip
    return root


@pytest.fixture(scope="module")
def messenger() -> Collector:
    return discover().get("messenger")


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box.create(tmp_path / "Box", "Test box")


def _run(collector: Collector, box: Box, source: Path, options: dict | None = None):
    chosen = validate(collector.info.options_schema, options or {})
    return collector.run(box, source, {**chosen, "owner": ME}, lambda step: None)


def _people(box: Box) -> set[str]:
    return {p.name for p in (box.root / "People").iterdir() if p.is_dir()}


def _groups(box: Box) -> set[str]:
    folder = box.root / "Groups"
    return {p.name for p in folder.iterdir()} if folder.is_dir() else set()


def test_only_threads_with_a_friend_or_a_removed_friend_are_imported(
    messenger: Collector, box: Box, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _run(messenger, box, _export(tmp_path / "export"))
    assert result.inserted == 2 * 4  # João, Rui, the family group and the Instagram thread
    people = _people(box)
    assert {"João Costa", "Rui Pereira", "Insta Person"} <= people
    assert not {"Marketplace Buyer", "Sofa Seller"} & people
    (note,) = [w for w in result.warnings if "left out" in w]
    assert note.startswith("2 Messenger conversations with nobody from your Facebook friends")
    log = capsys.readouterr().out
    assert "Marketplace Buyer" in log and "Sofa Seller" in log and ME not in log


def test_friends_are_named_and_so_not_listed_as_not_yet_named(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    result = _run(messenger, box, _export(tmp_path / "export"))
    unnamed = " ".join(result.unresolved)
    assert "João Costa" not in unnamed and "Rui Pereira" not in unnamed
    # in a kept group, but never wrote in it: not brought in at all
    assert "Cousin Not Friend" not in unnamed


def test_a_zip_of_the_whole_export_works_the_same(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    export = _export(tmp_path / "export")
    archive = tmp_path / "facebook-maria.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for file in export.rglob("*"):
            if file.is_file():
                z.write(file, file.relative_to(export))
    result = _run(messenger, box, archive)
    assert result.inserted == 2 * 4 and any("left out" in w for w in result.warnings)


def test_the_preview_counts_what_the_import_will_bring(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    preview = messenger.preview(_export(tmp_path / "export"), {}, box)
    assert preview.items == 2 * 4 and preview.conversations == 4
    assert any("left out" in w and "log" not in w for w in preview.warnings)


def test_everything_is_kept_when_asked(messenger: Collector, box: Box, tmp_path: Path) -> None:
    result = _run(messenger, box, _export(tmp_path / "export"), {"only_friends": False})
    assert result.inserted == 2 * 6 and not any("left out" in w for w in result.warnings)
    # friends are still named by Facebook's own list
    assert "João Costa" not in " ".join(result.unresolved)


def test_without_a_friends_list_everything_is_kept_and_it_says_so(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    result = _run(messenger, box, _export(tmp_path / "export", friends=False))
    assert result.inserted == 2 * 6
    (note,) = [w for w in result.warnings if "friends list" in w]
    assert note.startswith("No Facebook friends list was found")


def test_a_friends_list_downloaded_separately_can_be_pointed_at(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    messages = _export(tmp_path / "messages-only", friends=False)
    elsewhere = tmp_path / "other-download"
    _write(elsewhere / "connections" / "friends" / "your_friends.json",
           {"friends_v2": [{"name": _mojibake("João Costa"), "timestamp": 1}]})  # fmt: skip
    result = _run(messenger, box, messages, {"friends_list": str(elsewhere / "connections")})
    assert result.inserted == 2 * 3  # João, the family group, Instagram
    with pytest.raises(InputError, match="No Facebook friends list could be read"):
        _run(messenger, box, messages, {"friends_list": str(tmp_path / "nowhere")})


# --- Deactivated accounts ("Facebook user") ------------------------------------------------------------


def test_threads_with_a_deactivated_account_come_through_one_person_each(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    export = _export(tmp_path / "export")
    _thread(export, "facebookuser_7", ["Facebook user", ME])
    _thread(export, "facebookuser_8", ["Facebook user", ME])
    result = _run(messenger, box, export)
    assert result.inserted == 2 * 6  # the four kept before, and both deactivated threads
    unnamed = [h for h in result.unresolved if "Facebook user" in h]
    assert len(unnamed) == 2  # one handle each, so each can be linked to its own person
    assert all("facebookuser_" in h for h in unnamed)
    people = _people(box)
    assert len([p for p in people if p.startswith("Facebook user")]) == 2


# --- Only conversations you were part of ----------------------------------------------------------------


def _group(
    root: Path, folder: str, people: list[str], writers: list[str], place: str = "inbox"
) -> None:
    _write(
        root / "your_facebook_activity" / "messages" / place / folder / "message_1.json",
        {
            "participants": [{"name": _mojibake(p)} for p in people],
            "messages": [
                {"sender_name": _mojibake(w), "timestamp_ms": 1600000000000 + n, "content": f"hi {n}"}
                for n, w in enumerate(writers)
            ],
            "title": folder,
            "thread_path": f"{place}/{folder}",
        },
    )  # fmt: skip


def _noisy(root: Path) -> Path:
    export = _export(root)
    # a group a friend added you to, full of strangers, that you never wrote in (and left)
    _group(export, "promo_9", ["João Costa", "Spammer One", "Spammer Two"], ["Spammer One"] * 3)
    # a group you did write in
    _group(export, "dinner_10", ["João Costa", "New Friend", ME], ["New Friend", ME])
    # requests you never accepted, and what Facebook filtered as spam
    _group(export, "request_11", ["João Costa", ME], ["João Costa"], place="message_requests")
    _group(export, "spam_12", ["Rui Pereira", ME], ["Rui Pereira"], place="filtered_threads")
    return export


def test_groups_you_never_wrote_in_and_requests_are_left_out(
    messenger: Collector, box: Box, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = _run(messenger, box, _noisy(tmp_path / "export"))
    assert result.inserted == 2 * 4 + 2  # as before, and the dinner group
    groups = _groups(box)
    assert "dinner_10" in groups and "promo_9" not in groups
    notes = " ".join(result.warnings)
    assert "1 group conversation you never wrote in was left out" in notes
    assert "2 conversations from message requests and filtered (spam) messages" in notes
    log = capsys.readouterr().out
    assert "promo_9" in log and "request_11" in log and "spam_12" in log


def test_strangers_who_only_sat_in_a_group_are_not_waiting_to_be_named(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    export = _noisy(tmp_path / "export")
    _group(export, "big_13", ["João Costa", "Silent Member", "Talker", ME], ["Talker", ME])
    result = _run(messenger, box, export)
    unnamed = " | ".join(result.unresolved)
    assert "Talker" in unnamed  # wrote something: worth a name
    assert "Silent Member" not in unnamed  # only listed as a member of a group
    assert "Spammer" not in unnamed


def test_all_of_it_can_be_kept_when_asked(messenger: Collector, box: Box, tmp_path: Path) -> None:
    options = {"only_friends": False, "include_requests": True}
    result = _run(messenger, box, _noisy(tmp_path / "export"), options)
    assert result.inserted == 2 * 6 + 2 + 1 + 1  # all but the group you never wrote in
    assert [w for w in result.warnings if "left out" in w] == [
        "1 group conversation you never wrote in was left out. Who they were with is in the "
        "job's log."
    ]


def test_your_own_facebook_name_counts_when_it_is_not_the_boxs(
    messenger: Collector, box: Box, tmp_path: Path
) -> None:
    export = _export(tmp_path / "export")
    _group(
        export, "dinner_10", ["João Costa", "New Friend", "Maria C."], ["New Friend", "Maria C."]
    )
    _write(
        export / "personal_information" / "profile_information" / "profile_information.json",
        {"profile_v2": {"name": {"full_name": "Maria C."}}},
    )
    result = _run(messenger, box, export)
    assert "dinner_10" in _groups(box)  # she wrote in it, under her Facebook name
    assert not any("never wrote in" in w for w in result.warnings)
    assert "Maria C." not in _people(box)  # her Facebook name is her, not someone else
