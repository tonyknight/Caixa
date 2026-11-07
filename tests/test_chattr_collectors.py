"""Chattr's six sources as collectors: declared, previewed without writing, and run into a box."""

from __future__ import annotations

import json
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest
from fixtures import family

from caixa.box import Box
from caixa.collectors.base import Collector, Progress
from caixa.collectors.chattr import collectors
from caixa.collectors.inputs import InputError
from caixa.collectors.options import validate

IDS = ["googlevoice", "imessage", "mail", "messenger", "voicemail", "whatsapp"]


@pytest.fixture(scope="module")
def six() -> dict[str, Collector]:
    return {c.info.id: c for c in collectors()}


@pytest.fixture
def box(tmp_path: Path) -> Box:
    new = Box.create(tmp_path / "Box", name="Test box")
    with new.master() as master:
        master.add_person(family.OWNER.name, is_owner=True)
    return new


def _tree(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*"))


def _source(fixture_family, collector_id: str) -> Path:
    paths = fixture_family.paths
    return {
        "imessage": paths["imessage"],
        "whatsapp": paths["whatsapp"] / "WhatsApp Chat - Ana Costa" / "_chat.txt",
        "messenger": paths["messenger"],
        "mail": paths["mbox"],
        "googlevoice": paths["google_voice"],
        "voicemail": paths["iphone_voicemail"],
    }[collector_id]


# --- Declarations ---------------------------------------------------------------------------


def test_the_six_sources_are_declared(six: dict[str, Collector]) -> None:
    assert sorted(six) == IDS
    for collector in six.values():
        info = collector.info
        assert info.name and info.platform and info.inputs
        assert len(info.how_to_export) > 80  # real instructions, not a placeholder
        assert info.options_schema["type"] == "object"
        json.dumps(info.options_schema)


def test_how_to_export_names_the_steps_that_matter(six: dict[str, Collector]) -> None:
    assert "Full Disk Access" in six["imessage"].info.how_to_export
    assert "Export chat" in six["whatsapp"].info.how_to_export
    assert "Download your information" in six["messenger"].info.how_to_export
    assert (
        "Takeout" in six["mail"].info.how_to_export
        and "Takeout" in six["googlevoice"].info.how_to_export
    )
    assert "voicemail.db" in six["voicemail"].info.how_to_export


def test_option_defaults_are_seeded_from_chattrs_own_defaults(six: dict[str, Collector]) -> None:
    import chattr

    defaults = json.loads(
        (Path(chattr.__file__).parent / "defaults" / "Services" / "iMessage.json").read_text()
    )["preferences"]
    schema = six["imessage"].info.options_schema["properties"]
    assert schema["spam_mode"]["default"] == defaults["spam_filtering"]["mode"]
    assert schema["workers"]["default"] == defaults["performance"]["workers"]
    assert set(schema["spam_mode"]["enum"]) == set(defaults["spam_filtering"]["available_modes"])


def test_every_collectors_defaults_validate(six: dict[str, Collector]) -> None:
    for collector in six.values():
        validate(collector.info.options_schema, {})


# --- Preview --------------------------------------------------------------------------------

EXPECTED_ITEMS = {
    "imessage": 7,
    "whatsapp": 7,
    "messenger": 5,
    "mail": 4,
    "googlevoice": 6,
    "voicemail": 2,
}


@pytest.mark.parametrize("collector_id", IDS)
def test_a_preview_counts_without_writing_anything(
    six: dict[str, Collector], fixture_family, box: Box, collector_id: str
) -> None:
    source = _source(fixture_family, collector_id)
    around = source if source.is_dir() else source.parent
    before_source, before_box = _tree(around), _tree(box.root)
    preview = six[collector_id].preview(
        source, validate(six[collector_id].info.options_schema, {}), box
    )
    assert preview.items == EXPECTED_ITEMS[collector_id]
    assert preview.first and preview.last and preview.first <= preview.last
    assert preview.participants
    assert _tree(around) == before_source and _tree(box.root) == before_box


def test_a_preview_reports_the_handles_no_alias_names(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    source = _source(fixture_family, "imessage")
    options = validate(six["imessage"].info.options_schema, {})
    preview = six["imessage"].preview(source, options, box)
    assert (
        family.UNKNOWN_HANDLE in preview.unresolved and family.ANA.phones[0] in preview.unresolved
    )
    with box.master() as master:
        master.add_alias(master.add_person(family.ANA.name), family.ANA.phones[0], "phone")
    again = six["imessage"].preview(source, options, box)
    assert (
        family.ANA.phones[0] not in again.unresolved and family.UNKNOWN_HANDLE in again.unresolved
    )


def test_a_preview_spans_several_inputs(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    folder = fixture_family.paths["whatsapp"]  # three chats in one folder
    preview = six["whatsapp"].preview(
        folder, validate(six["whatsapp"].info.options_schema, {}), box
    )
    assert preview.conversations == 3 and preview.items == 7 + 4 + 7


def test_a_missing_source_is_explained(six: dict[str, Collector], tmp_path: Path) -> None:
    with pytest.raises(InputError, match="Not found"):
        six["mail"].preview(tmp_path / "nothing.mbox", {})
    (tmp_path / "empty").mkdir()
    with pytest.raises(InputError, match="Nothing to import"):
        six["whatsapp"].preview(tmp_path / "empty", {})


# --- Run ------------------------------------------------------------------------------------


def _run(collector: Collector, box: Box, source: Path, options: dict | None = None):
    events: list[Progress] = []
    result = collector.run(
        box, source, validate(collector.info.options_schema, options or {}), events.append
    )
    return result, events


def test_running_imports_into_the_box(six: dict[str, Collector], fixture_family, box: Box) -> None:
    result, _ = _run(six["whatsapp"], box, _source(fixture_family, "whatsapp"))
    assert result.inserted == 7 and result.updated == 0
    status = box.status()
    assert status["items"] == 7
    assert status["people"] == 1  # the owner: Ana is only a name until someone links her
    assert result.unresolved == ["WhatsApp: Ana Costa"]
    assert (box.root / "Messages" / family.ANA.name).is_dir()  # pages for Ana's chat
    pages = sorted((box.root / "Messages" / family.ANA.name).glob("(*) *.html"))
    assert pages and "Que lindo! Buy two." in pages[0].read_text(encoding="utf-8")
    assert (box.root / "index.html").is_file()
    assert (box.work_dir("chattr") / "Database" / "chattr.sqlite").is_file()


def test_the_pages_are_recorded_on_the_items(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    _run(six["whatsapp"], box, _source(fixture_family, "whatsapp"))
    with box.master() as master:
        rows = master.connection.execute("SELECT file_path, anchor, id FROM items").fetchall()
    assert all(r["file_path"] and r["file_path"].startswith("Messages/") for r in rows)
    assert all(r["anchor"] == f"#m-{r['id']}" for r in rows)
    assert all((box.root / r["file_path"]).is_file() for r in rows)


def test_progress_arrives_in_order_and_ends_done(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    _, events = _run(six["mail"], box, _source(fixture_family, "mail"))
    stages = [e.stage for e in events]
    assert stages[0] == "preparing" and stages[-1] == "done"
    order = ["preparing", "importing", "linking", "rendering", "syncing", "done"]
    assert [s for s in order if s in stages] == order
    assert stages == sorted(stages, key=order.index)


def test_running_again_changes_nothing(six: dict[str, Collector], fixture_family, box: Box) -> None:
    source = _source(fixture_family, "whatsapp")
    first, _ = _run(six["whatsapp"], box, source)
    with box.master() as master:
        changes = len(master.changes())
    second, _ = _run(six["whatsapp"], box, source)
    assert (second.inserted, second.updated) == (0, 0) and second.unchanged == first.inserted
    with box.master() as master:
        assert len(master.changes()) == changes


def test_all_six_sources_make_one_box(six: dict[str, Collector], fixture_family, box: Box) -> None:
    for collector_id in IDS:
        _run(six[collector_id], box, _source(fixture_family, collector_id))
    status = box.status()
    assert status["items"] == sum(EXPECTED_ITEMS.values())
    assert {"text", "call", "voicemail", "email", "media", "system"} <= set(status["by_type"])
    ana = box.root / "Messages" / family.ANA.name
    years = {p.name for p in ana.glob("(*) *.html")}
    assert {f"(2018) {family.ANA.name}.html", f"(2024) {family.ANA.name}.html"} <= years
    assert list((box.root / "Mail").rglob("*.html"))


def test_mail_attachments_and_voicemail_audio_live_in_the_box(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    _run(six["mail"], box, _source(fixture_family, "mail"))
    _run(six["voicemail"], box, _source(fixture_family, "voicemail"))
    assert list((box.root / "Mail" / "Attachments").rglob("*.png"))
    assert list((box.root / "Audio" / "Voicemail").rglob("*.amr"))
    page = next((box.root / "Mail").rglob("(2019-11-02)*.html")).read_text(encoding="utf-8")
    assert "familia.png" in page and "file not in this archive" not in page


def test_whatsapp_media_is_filed_under_the_person(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    _run(six["whatsapp"], box, _source(fixture_family, "whatsapp"))
    photos = list(
        (box.root / "Messages" / family.ANA.name / "Attachments").glob("(2024-03-01) 14-05-09 *")
    )
    assert len(photos) == 1


def test_the_boxs_aliases_and_owner_are_given_to_chattr(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    with box.master() as master:
        ana = master.add_person("Ana (daughter)")
        master.add_alias(ana, family.ANA.name, "name", service="WhatsApp")
    _run(six["whatsapp"], box, _source(fixture_family, "whatsapp"))
    assert (box.root / "Messages" / "Ana (daughter)").is_dir()
    aliases = json.loads((box.work_dir("chattr") / "aliases.json").read_text())
    assert aliases[family.ANA.name] == "Ana (daughter)"


def test_contacts_can_be_given_as_an_option(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    result, _ = _run(
        six["imessage"],
        box,
        _source(fixture_family, "imessage"),
        {"contacts": str(fixture_family.paths["contacts"])},
    )
    assert [u for u in result.unresolved] == [f"iMessage: {family.UNKNOWN_HANDLE}"]


def test_a_run_reports_the_handles_still_unnamed(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    result, _ = _run(six["googlevoice"], box, _source(fixture_family, "googlevoice"))
    assert any(family.UNKNOWN_HANDLE in u for u in result.unresolved)


# --- Zips and folders -----------------------------------------------------------------------


def _zip(folder: Path, target: Path) -> Path:
    with zipfile.ZipFile(target, "w") as bundle:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(folder.parent))
    return target


def test_a_whatsapp_zip_is_unpacked_and_imported(
    six: dict[str, Collector], fixture_family, box: Box, tmp_path: Path
) -> None:
    archive = _zip(
        fixture_family.paths["whatsapp"] / "WhatsApp Chat - Ana Costa", tmp_path / "chat.zip"
    )
    preview = six["whatsapp"].preview(archive, {}, box)
    assert preview.items == 7
    result, _ = _run(six["whatsapp"], box, archive)
    assert result.inserted == 7
    assert list(
        (box.root / "Messages" / family.ANA.name / "Attachments").glob("*.png")
    )  # the media came too


def test_a_meta_export_with_both_services_imports_every_thread(
    six: dict[str, Collector], fixture_family, box: Box, tmp_path: Path
) -> None:
    export = fixture_family.paths["messenger"].parents[4]  # the folder holding both threads
    result, _ = _run(six["messenger"], box, export)
    assert result.inserted == 5 + 2
    with box.master() as master:
        services = {r[0] for r in master.connection.execute("SELECT DISTINCT service FROM items")}
    assert {"Messenger", "Instagram"} <= services


def test_an_unsafe_zip_is_refused(six: dict[str, Collector], tmp_path: Path, box: Box) -> None:
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as bundle:
        bundle.writestr("../../escape.txt", "gotcha")
        bundle.writestr("_chat.txt", "01/01/2024, 10:00 - A: hi")
    with pytest.raises(InputError, match="unsafe"):
        six["whatsapp"].preview(evil, {}, box)
    assert not (tmp_path.parent / "escape.txt").exists()


def test_a_file_that_is_not_a_zip_is_explained(
    six: dict[str, Collector], tmp_path: Path, box: Box
) -> None:
    fake = tmp_path / "chat.zip"
    fake.write_text("not a zip")
    with pytest.raises(InputError, match="not a readable zip"):
        six["whatsapp"].preview(fake, {}, box)


def test_the_source_is_never_changed(
    six: dict[str, Collector], fixture_family, box: Box, tmp_path: Path
) -> None:
    copy = tmp_path / "mail"
    shutil.copytree(fixture_family.paths["mbox"].parents[2], copy)
    before = {p: p.read_bytes() for p in copy.rglob("*") if p.is_file()}
    _run(six["mail"], box, copy)
    assert {p: p.read_bytes() for p in copy.rglob("*") if p.is_file()} == before


# --- Discovery through the installed entry point --------------------------------------------


def test_the_registry_finds_the_six_through_the_entry_point() -> None:
    from caixa.collectors.registry import discover

    registry = discover()
    assert registry.problems == []
    assert sorted(c.info.id for c in registry.all()) >= IDS
    assert [c["id"] for c in registry.describe() if c["id"] in IDS] == [
        c.info.id for c in registry.all() if c.info.id in IDS
    ]


def test_the_description_the_interface_reads_is_plain_json() -> None:
    from caixa.collectors.registry import discover

    described = json.loads(json.dumps(discover().describe()))
    by_id = {entry["id"]: entry for entry in described}
    assert set(IDS) <= set(by_id)
    for entry in by_id.values():
        assert entry["how_to_export"] and entry["options_schema"]["type"] == "object"


# --- Voicemail as audio files named for their time and caller -------------------------------


def _voicemail_zip(tmp_path: Path, *extra: tuple[str, bytes]) -> Path:
    """A zip like the one a phone's voicemail export gives: just audio files, no database."""
    archive = tmp_path / "iPhone Voicemail.zip"
    names = [
        f"(2018-12-21) 15 02 31 - {family.ANA.name}.amr",
        f"(2019-01-03) 09 05 00 - {family.JOAO.name}.amr",
        f"(2019-02-10) 18 30 12 - {family.ANA.name}.amr",
    ]
    with zipfile.ZipFile(archive, "w") as z:
        for name in names:
            z.writestr(f"iPhone Voicemail/{name}", f"audio of {name}")
        for name, data in extra:
            z.writestr(name, data)
    return archive


def test_a_zip_of_named_voicemail_files_is_previewed(
    six: dict[str, Collector], tmp_path: Path
) -> None:
    preview = six["voicemail"].preview(_voicemail_zip(tmp_path), {})
    assert preview.items == 3 and preview.conversations == 2
    assert (preview.first, preview.last) == ("2018-12-21", "2019-02-10")
    assert sorted(preview.participants) == sorted([family.ANA.name, family.JOAO.name])


def test_a_zip_of_named_voicemail_files_is_imported_with_its_audio(
    six: dict[str, Collector], box: Box, tmp_path: Path
) -> None:
    junk = (
        ("__MACOSX/iPhone Voicemail/._(2018-12-21) 15 02 31 - Ana Costa.amr", b"apple double"),
        ("iPhone Voicemail/.DS_Store", b"x"),
    )
    result, _ = _run(six["voicemail"], box, _voicemail_zip(tmp_path, *junk))
    assert result.inserted == 3
    assert len(list((box.root / "Audio" / "Voicemail").rglob("*.amr"))) == 3
    pages = list((box.root / "Messages").rglob("*.html"))
    assert pages and any(family.ANA.name in str(page) for page in pages)


def test_a_zip_with_no_voicemail_in_it_says_so(
    six: dict[str, Collector], box: Box, tmp_path: Path
) -> None:
    archive = tmp_path / "other.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("notes.txt", "nothing here")
    with pytest.raises(InputError, match="Nothing to import"):
        six["voicemail"].preview(archive, {})


# --- The speech model and language come from the box's settings -------------------------------


def _speech_settings(box: Box, model: str, language: str = "") -> None:
    from caixa import settings

    settings.save(box, {"speech.model": model, "speech.language": language})


def test_the_speech_options_name_the_setting_they_follow(six: dict[str, Collector]) -> None:
    properties = six["voicemail"].info.options_schema["properties"]
    assert properties["model"]["x-setting"] == "speech.model"
    assert properties["language"]["x-setting"] == "speech.language"
    assert properties["model"]["x-picker"] == "file"  # the form offers to browse for it
    validate(six["voicemail"].info.options_schema, {})  # and the extra keywords are accepted


def test_a_saved_model_is_not_enough_to_turn_transcription_on(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    _speech_settings(box, "/nowhere/ggml-model.bin")
    result, _ = _run(six["voicemail"], box, _source(fixture_family, "voicemail"))
    assert result.inserted == 2  # no transcriber was made, so the missing model never mattered


def test_ticking_transcribe_uses_the_saved_model_and_language(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    _speech_settings(box, "/nowhere/ggml-model.bin", "pt")
    with pytest.raises(Exception, match="/nowhere/ggml-model.bin"):
        _run(six["voicemail"], box, _source(fixture_family, "voicemail"), {"transcribe": True})


def test_a_model_given_in_the_options_beats_the_saved_one(
    six: dict[str, Collector], fixture_family, box: Box
) -> None:
    _speech_settings(box, "/nowhere/saved.bin")
    with pytest.raises(Exception, match="/nowhere/chosen.bin"):
        _run(
            six["voicemail"],
            box,
            _source(fixture_family, "voicemail"),
            {"transcribe": True, "model": "/nowhere/chosen.bin"},
        )
