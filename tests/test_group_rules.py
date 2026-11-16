"""Group conversations, from any source: kept only if the owner wrote in them; of their members,
only those who wrote are brought in, and never by a phone number alone."""

from __future__ import annotations

from pathlib import Path

import pytest
from fixtures import family

from caixa.box import Box
from caixa.collectors.base import Collector
from caixa.collectors.options import validate
from caixa.collectors.registry import discover

ME = family.OWNER.name


@pytest.fixture(scope="module")
def whatsapp() -> Collector:
    return discover().get("whatsapp")


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box.create(tmp_path / "Box", "Test box")


def _chat(folder: Path, name: str, lines: list[str]) -> Path:
    chat = folder / f"WhatsApp Chat - {name}" / "_chat.txt"
    chat.parent.mkdir(parents=True)
    chat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return chat


def _run(collector: Collector, box: Box, source: Path):
    options = validate(collector.info.options_schema, {"owner": ME})
    return collector.run(box, source, options, lambda step: None)


def _people(box: Box) -> set[str]:
    with box.master() as master:
        return {p.name for p in master.people()}


def test_a_group_the_owner_never_wrote_in_is_left_out(
    whatsapp: Collector, box: Box, tmp_path: Path
) -> None:
    chats = tmp_path / "chats"
    _chat(chats, "Promo", [
        "[01/03/2024, 14:05:09] Seller One: Big sale!",
        "[01/03/2024, 14:06:00] Seller Two: Today only",
        "[01/03/2024, 14:07:00] +351 912 345 678: Interested",
    ])  # fmt: skip
    _chat(chats, "Family", [
        "[02/03/2024, 10:00:00] Tia Lurdes: Olá a todos",
        "[02/03/2024, 10:01:00] Primo Rui: Olá!",
        f"[02/03/2024, 10:02:00] {ME}: Bom dia",
    ])  # fmt: skip
    result = _run(whatsapp, box, chats)
    assert result.inserted == 3  # the family group only
    assert (box.root / "Groups").is_dir() and [p.name for p in (box.root / "Groups").iterdir()]
    assert not {"Seller One", "Seller Two"} & _people(box)
    assert any("group conversation you never wrote in" in w for w in result.warnings)


def test_only_members_who_wrote_are_brought_in_and_never_a_number(
    whatsapp: Collector, box: Box, tmp_path: Path
) -> None:
    chat = _chat(tmp_path, "Family", [
        "[02/03/2024, 10:00:00] Tia Lurdes: Olá a todos",
        "[02/03/2024, 10:01:00] +351 912 345 678: Quem é?",
        f"[02/03/2024, 10:02:00] {ME}: Bom dia",
    ])  # fmt: skip
    result = _run(whatsapp, box, chat)
    assert result.inserted == 3  # every message is kept, the number's too
    assert "Tia Lurdes" in _people(box)  # wrote, shown by a name: a person
    assert not any("912" in p for p in _people(box))
    assert not any("912" in h for h in result.unresolved)  # a number in a group: never brought in
    page = next((box.root / "Groups").rglob("*.html")).read_text(encoding="utf-8")
    assert "Quem é?" in page  # what the number said is still on the group's page


def test_a_number_from_a_direct_conversation_still_waits_for_a_name(
    whatsapp: Collector, box: Box, tmp_path: Path
) -> None:
    chat = _chat(tmp_path, "+351 912 345 678", [
        "[02/03/2024, 10:01:00] +351 912 345 678: Olá, sou eu",
        f"[02/03/2024, 10:02:00] {ME}: Quem?",
    ])  # fmt: skip
    result = _run(whatsapp, box, chat)
    assert any("912" in h for h in result.unresolved)
