"""Chattr's six sources as Caixa collectors.

Each collector wraps one Chattr service: it says how to export from the app, finds what to read in
whatever a person points at (a file, a folder or a zip), previews it in a scratch Chattr root so
nothing in the box or the source changes, and runs it into the box's own Chattr root
(`.caixa/work/chattr/`), where Chattr keeps its database. After the import the pages are drawn into
the box (`Messages/<Person>/…`, `Mail/<year>/…`, `index.html`) and the master database is brought
up to date from Chattr's, with each item pointing at the page that shows it.

Chattr is the engine; this file only decides where things go inside a box and what to ask a person.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import chattr.commands as commands
import chattr.preflight as preflight
from chattr.config import Settings
from chattr.database_manager import DatabaseManager
from chattr.parsers.voicemail_parser import AUDIO_SUFFIXES, audio_files
from chattr.render import Renderer
from chattr.transcription import TranscriptionUnavailable, make_transcriber
from chattr.translation import TranslationError, translate_archive

from caixa import settings as box_settings
from caixa import translation
from caixa.box import Box
from caixa.collectors import inputs
from caixa.collectors.base import CollectorInfo, Preview, Progress, RunResult
from caixa.collectors.inputs import InputError
from caixa.collectors.messages import sync_chattr
from caixa.collectors.options import defaults

#: Importers put the files they extract in a working folder inside `.caixa/` (one per kind).
#: Publishing then files each one where a person would look for it, under the person it came from
#: (`People/<Person>/<Service>/(date) time sender.ext`, see `chattr.filing`), and empties these.
INCOMING = Path("work") / "incoming"
MESSAGES = "messages"
MAIL_ATTACHMENTS = "mail"
VOICEMAIL_AUDIO = "voicemail"
GOOGLE_VOICE_AUDIO = "googlevoice"
IMESSAGE_FILES = "imessage"
STAGES = (MESSAGES, MAIL_ATTACHMENTS, VOICEMAIL_AUDIO, GOOGLE_VOICE_AUDIO, IMESSAGE_FILES)

_COMMON_OPTIONS: dict[str, Any] = {
    "contacts": {
        "type": "string",
        "default": "",
        "title": "Contacts file (.vcf)",
        "description": (
            "A vCard export of your address book, used to name phone numbers and emails. "
            "Set it once in Settings, under Contacts; leave this as it is to use that file."
        ),
        "x-setting": "contacts.file",
        "x-picker": "file",
    },
    "owner": {
        "type": "string",
        "default": "",
        "title": "Your name",
        "description": "Who 'me' is. Leave empty to use the owner of this box.",
    },
}


#: The key, in the options a source's `convert` is given, that holds the progress callback.
REPORT = "_report"


def audio_seconds(audio: Path) -> Optional[float]:
    """How long a recording is, when ffprobe is installed and can tell."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    command = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of",
               "default=nw=1:nk=1", str(audio)]  # fmt: skip
    try:
        said = subprocess.run(command, capture_output=True, text=True, timeout=30).stdout
        return float(said.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


class TimedTranscriber:
    """A speech-to-text engine that says how it is getting on: which recording, how many of how
    many, how long each took and how that compares with the recording's own length. Each line
    is also printed, which puts it in the job's log."""

    def __init__(
        self,
        inner: Any,
        progress: Callable[[Progress], None],
        clock: Callable[[], float] = time.monotonic,
        length: Callable[[Path], Optional[float]] = audio_seconds,
    ) -> None:
        self.inner, self.progress, self.clock, self.length = inner, progress, clock, length
        if hasattr(inner, "transcribe_many"):
            # the engine takes every recording in one run (the model is loaded once): time each
            # as it comes out. The first one's time includes loading the model.
            self.transcribe_many = self._many
        self.total: Optional[int] = None
        self.done = 0
        self.spent = 0.0
        self.heard = 0.0

    def expect(self, count: int) -> None:
        self.total = count
        self.progress(Progress("transcribing", 0, count, "Starting speech-to-text"))

    def transcribe(self, audio: Path) -> Any:
        self.progress(Progress("transcribing", self.done, self.total, f"Listening to {audio.name}"))
        started = self.clock()
        failed = ""
        try:
            return self.inner.transcribe(audio)
        except Exception as error:
            failed = self._why(error)
            raise
        finally:
            self._finished(audio, self.clock() - started, failed)

    def _many(self, files: Any) -> Any:
        files = list(files)
        self.progress(
            Progress("transcribing", self.done, self.total, "Loading the speech model (once)")
        )
        started = self.clock()
        for audio, result in self.inner.transcribe_many(files):
            now = self.clock()
            failed = self._why(result) if isinstance(result, Exception) else ""
            note = " (includes loading the model)" if self.done == 0 else ""
            self._finished(audio, now - started, failed + note)
            started = now
            yield audio, result

    @staticmethod
    def _why(error: BaseException) -> str:
        return f" (failed: {str(error)[:120] or type(error).__name__})"

    def _finished(self, audio: Path, took: float, note: str) -> None:
        long = self.length(audio)
        self.done += 1
        self.spent += took
        line = f"{audio.name}: {took:.1f} s"
        if long:
            self.heard += long
            line += f" for {long:.0f} s of audio"
            if took > 0:
                line += f" ({long / took:.1f}x real time)"
        line += note
        summary = f"{line}; average {self.spent / self.done:.1f} s each"
        print(f"Speech-to-text {self.done}/{self.total or '?'}: {summary}")
        self.progress(Progress("transcribing", self.done, self.total, summary))


#: The speech-to-text options of every source that has recordings (voicemail, Google Voice).
_SPEECH_OPTIONS: dict[str, Any] = {
    "transcribe": {
        "type": "boolean",
        "default": False,
        "title": "Transcribe on this computer",
        "description": (
            "Turn each voicemail into text with a speech model stored here. On to begin with "
            "when a speech model is saved in Settings; untick it to skip transcription for "
            "this import."
        ),
        "x-on-when-set": "speech.model",
    },
    "model": {
        "type": "string",
        "default": "",
        "title": "Speech model",
        "description": (
            "Path to a local speech-to-text model file (never downloaded). "
            "Empty uses the one in Settings."
        ),
        "x-setting": "speech.model",
        "x-picker": "file",
    },
    "language": {
        "type": "string",
        "default": "",
        "title": "Language",
        "description": (
            "A language code such as 'en' or 'pt'; empty uses the one in Settings, "
            "and if that is empty too, detects it."
        ),
        "x-setting": "speech.language",
    },
}


def _schema(**extra: Any) -> dict[str, Any]:
    return {"type": "object", "properties": {**_COMMON_OPTIONS, **extra}}


def _imessage_defaults() -> dict[str, Any]:
    """Chattr's own defaults for iMessage (spam mode, workers), so Caixa never restates them."""
    import chattr

    path = Path(chattr.__file__).parent / "defaults" / "Services" / "iMessage.json"
    return dict(json.loads(path.read_text(encoding="utf-8"))["preferences"])


def _preview_error(error: commands.CommandError) -> InputError:
    return InputError(str(error))


def _transcriber(settings: Settings, options: Mapping[str, Any], final: bool) -> Optional[Any]:
    """The speech-to-text engine these options ask for (None when transcription is not ticked, or
    this is only a preview), reporting each recording as it goes."""
    if not (final and options.get("transcribe")):
        return None
    try:
        transcriber: Any = make_transcriber(
            settings,
            enabled=True,
            model_path=options.get("model") or None,
            language=options.get("language") or None,
        )
    except TranscriptionUnavailable as error:
        raise commands.CommandError(str(error)) from error
    if transcriber is None:
        raise commands.CommandError(
            "No speech-to-text model is set. Give the model path in the options, or once in "
            "Settings."
        )
    if options.get(REPORT):
        transcriber = TimedTranscriber(transcriber, options[REPORT])
    return transcriber


class _Chattr:
    """The shared behaviour; each source supplies `info`, `locate` and `_convert`."""

    info: CollectorInfo
    #: the folder, inside a box, for files this source extracts (None: it extracts none)
    attachments: Optional[str] = None  # which working folder this source's files wait in

    # --- What each source says --------------------------------------------------------------

    def locate(self, source: Path, workdir: Path) -> list[Path]:
        raise NotImplementedError

    def convert(
        self,
        settings: Settings,
        item: Path,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
        attachments_dir: Optional[Path],
        final: bool,
    ) -> Optional[list[str]]:
        """Convert one input. May return notes for the person (shown with the result)."""
        raise NotImplementedError

    # --- Shared -----------------------------------------------------------------------------

    def _options(self, options: Mapping[str, Any], box: Optional[Box] = None) -> dict[str, Any]:
        """The options with defaults filled in. An option that names a box setting (`x-setting`)
        and was left empty takes that setting's value, so a saved speech model is used."""
        merged = {**defaults(self.info.options_schema), **options}
        saved = box_settings.load(box) if box is not None else {}
        for name, spec in self.info.options_schema["properties"].items():
            key = spec.get("x-setting")
            unset = name not in options or options[name] in (None, "")
            if key and unset and saved.get(key) not in (None, ""):
                merged[name] = saved[key]
            flag = spec.get("x-on-when-set")  # on unless said otherwise, once that setting is set
            if flag and name not in options:
                merged[name] = saved.get(flag) not in (None, "")
        # Contacts are a setting of the box, the same for every source (an option, where a source
        # has one, has already taken its place above). Without a box nobody's Contacts are read.
        merged.setdefault("mac_contacts", bool(saved.get("contacts.mac", False)))
        if not merged.get("region"):
            merged["region"] = saved.get("contacts.region") or ""
        return merged

    @staticmethod
    def _name_people(
        settings: Settings,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
    ) -> None:
        """Link every handle to a person: the box's aliases, the contacts file, this Mac's Contacts."""
        try:
            commands.people(
                settings,
                owner,
                aliases,
                options.get("contacts") or None,
                options.get("region") or None,
                mac_contacts=bool(options.get("mac_contacts")),
            )
        except commands.CommandError as error:
            raise InputError(
                f"{error} (The contacts file is set in Settings, under Contacts, or in this "
                "import's options.)"
            ) from error

    def _owner(self, options: Mapping[str, Any], box: Optional[Box]) -> Optional[str]:
        if options.get("owner"):
            return str(options["owner"])
        if box is not None and box.master_path.exists():
            with box.master() as master:
                owner = master.owner_id()
                if owner is not None:
                    return next(p.name for p in master.people() if p.id == owner)
        return None

    def _aliases(self, box: Optional[Box], target: Path) -> Optional[Path]:
        if box is None or not box.master_path.exists():
            return None
        with box.master() as master:
            master.export_aliases(target)
        return target

    def _settings(self, root: Path) -> Settings:
        if not preflight.ensure_root(str(root)):
            raise InputError(f"Could not set up Chattr's working folder at {root}.")
        return Settings.load(root)

    def _import_all(
        self,
        settings: Settings,
        items: list[Path],
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
        attachments_dir: Optional[Path],
        final: bool,
        progress: Callable[[Progress], None],
    ) -> list[str]:
        """Convert every input; returns notes about any that held nothing (they are skipped).

        People are linked once afterwards by the caller, not per input: an export can hold
        thousands of conversations.
        """
        empty: list[Path] = []
        notes: list[str] = []
        # (a source that works on each file for a while, such as speech-to-text, reports through this)
        options = {**options, REPORT: progress}
        for number, item in enumerate(items, 1):
            progress(Progress("importing", number - 1, len(items), self._label(item)))
            try:
                said = self.convert(settings, item, options, owner, aliases, attachments_dir, final)
                notes.extend(said or [])
            except commands.NothingFound as error:
                if len(items) == 1:
                    raise InputError(str(error)) from error
                empty.append(item)
            except commands.CommandError as error:
                raise InputError(str(error)) from error
        progress(Progress("importing", len(items), len(items)))
        if empty and len(empty) == len(items):
            raise InputError(
                f"All {len(items)} conversations in this export had no messages, so there is "
                "nothing to import."
            )
        if empty:
            count = len(empty)
            notes.insert(
                0,
                f"{count} conversation{'s' if count != 1 else ''} had no messages and "
                f"{'were' if count != 1 else 'was'} skipped.",
            )
        return notes

    @staticmethod
    def _label(item: Path) -> str:
        """What to call an input while it is read: a thread's folder says more than `message_1.json`."""
        generic = item.name in ("message_1.json", "_chat.txt", "voicemail.db", "chat.db")
        return item.parent.name if generic and item.parent.name else item.name

    # --- Preview ----------------------------------------------------------------------------

    def preview(
        self,
        source: Path,
        options: Mapping[str, Any],
        box: Optional[Box] = None,
        progress: Optional[Callable[[Progress], None]] = None,
    ) -> Preview:
        """Read everything in a scratch Chattr root and count it; the box and source are untouched.

        `progress`, when given, is told about each input as it is read (a large export takes a
        while to count), and may raise to stop the preview.
        """
        report = progress or (lambda _progress: None)
        report(Progress("preparing", message=f"Reading {Path(source).name}"))
        opts = self._options(options, box)
        with tempfile.TemporaryDirectory(prefix="caixa-preview-") as scratch_name:
            scratch = Path(scratch_name)
            items = self.locate(Path(source), scratch / "inputs")
            settings = self._settings(scratch / "chattr")
            aliases = self._aliases(box, scratch / "aliases.json")
            owner = self._owner(opts, box)
            notes = self._import_all(settings, items, opts, owner, aliases, None, False, report)
            report(Progress("linking", message="Matching people"))
            described = self._describe(settings, opts, owner, aliases)
            described.warnings[:0] = notes
            return described

    def _describe(
        self,
        settings: Settings,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
    ) -> Preview:
        self._name_people(settings, options, owner, aliases)
        database = commands.central_database(settings)
        with DatabaseManager(database) as db:
            unresolved = [handle.identifier for handle in db.unresolved_handles()]
        link = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
        try:
            items, first, last = link.execute(
                "SELECT COUNT(*), MIN(timestamp_utc), MAX(timestamp_utc) FROM messages"
            ).fetchone()
            conversations = link.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            people = [
                row[0]
                for row in link.execute(
                    "SELECT DISTINCT COALESCE(h.person, h.display_name, h.identifier) "
                    "FROM handles h WHERE h.id IN ("
                    "  SELECT handle_id FROM participants WHERE role != 'owner' "
                    "  UNION SELECT sender_handle_id FROM messages "
                    "  WHERE is_from_owner = 0 AND sender_handle_id IS NOT NULL) "
                    "ORDER BY 1"
                )
            ]
        finally:
            link.close()
        return Preview(
            items=items,
            conversations=conversations,
            first=first[:10] if first else None,
            last=last[:10] if last else None,
            participants=people,
            unresolved=unresolved,
        )

    # --- Run --------------------------------------------------------------------------------

    def run(
        self,
        box: Box,
        source: Path,
        options: Mapping[str, Any],
        progress: Callable[[Progress], None],
    ) -> RunResult:
        opts = self._options(options, box)
        progress(Progress("preparing", message=f"Reading {Path(source).name}"))
        root = box.work_dir("chattr")
        items = self.locate(Path(source), box.work_dir("imports"))
        settings = self._settings(root)
        aliases = self._aliases(box, root / "aliases.json")
        owner = self._owner(opts, box)
        attachments = box.caixa_dir / INCOMING / self.attachments if self.attachments else None

        notes = self._import_all(settings, items, opts, owner, aliases, attachments, True, progress)

        progress(Progress("linking", message="Matching people"))
        self._name_people(settings, opts, owner, aliases)
        translated, said = self._translate(box, settings, progress)
        result = self._publish(box, settings, progress)
        result.translated = translated
        result.warnings[:0] = [*notes, *said]
        return result

    @staticmethod
    def _translate(
        box: Box, settings: Settings, progress: Callable[[Progress], None]
    ) -> tuple[int, list[str]]:
        """Translate what needs it, when the box's settings turn translation on.

        Every message in the box is considered, so turning translation on and importing anything
        catches up on what was imported before; a message that has a translation is never sent
        again. Returns how many were translated and what a person should know. A translation
        service that is missing or failing never fails the import.
        """
        values = box_settings.load(box)
        if not values.get("translation.enabled"):
            return 0, []
        wrong = translation.problems(values)
        if wrong:
            return 0, [f"Nothing was translated. {wrong[0]}"]
        try:
            translator = translation.translator(values)
        except TranslationError as error:
            return 0, [f"Nothing was translated. {error}"]

        def report(done: int, total: int) -> None:
            progress(Progress("translating", done, total, "Translating messages"))

        progress(Progress("translating", message="Looking for messages to translate"))
        with DatabaseManager(commands.central_database(settings)) as db:
            stats = translate_archive(
                db, translator, workers=translation.workers(values), on_progress=report
            )
        said: list[str] = []
        if stats.aborted:
            said.append(
                f"Translation stopped after {stats.translated:,} messages because the "
                f"translation service kept failing: {stats.errors[-1]} What was translated is "
                "kept. Check it in Settings (Test), then import again to translate the rest."
            )
        elif stats.failed:
            said.append(
                f"{stats.failed:,} messages could not be translated ({stats.errors[-1]}). "
                "If that keeps happening, check the service in Settings (Test). Import again to "
                "try them once more."
            )
        return stats.translated, said

    # --- Pages and the master (after an import, or after people changed) ---------------------

    work_key = "chattr"

    def _page_files(self, box: Box) -> set[str]:
        if not box.master_path.exists():
            return set()
        with box.master() as master:
            return {
                row[0]
                for row in master.connection.execute(
                    "SELECT DISTINCT file_path FROM items "
                    "WHERE collector = 'chattr' AND file_path IS NOT NULL"
                )
            }

    def _publish(
        self, box: Box, settings: Settings, progress: Callable[[Progress], None]
    ) -> RunResult:
        """Draw every page into the box, bring the master up to date, drop pages nobody needs."""
        before = self._page_files(box)
        incoming = box.caixa_dir / INCOMING

        def filing(done: int, total: int) -> None:
            progress(Progress("filing", done, total, "Filing photos, audio and other files"))

        progress(Progress("filing", message="Filing photos, audio and other files"))
        published = commands.publish(
            settings,
            out=box.root,
            attachments_dirs=[incoming / stage for stage in STAGES],
            pages_list=box.caixa_dir / "pages.json",
            progress=filing,
            before_pages=lambda: progress(Progress("rendering", message="Writing the pages")),
        )
        shutil.rmtree(incoming, ignore_errors=True)  # what is left there is already filed
        with DatabaseManager(commands.central_database(settings)) as db:
            renderer = Renderer(db)
            pages = {mid: spec.path for spec in renderer.pages for mid in spec.message_ids}
            page_count = len(renderer.pages)

        progress(Progress("syncing", message="Updating the box"))
        with box.master() as master:
            synced = sync_chattr(master, commands.central_database(settings), pages)
        self._remove_stale(box, before - self._page_files(box))
        unresolved = [f"{h.service}: {h.identifier}" for h in synced.unresolved]
        progress(Progress("done", synced.inserted + synced.updated + synced.unchanged))
        return RunResult(
            inserted=synced.inserted,
            updated=synced.updated,
            unchanged=synced.unchanged,
            pages=page_count,
            unresolved=unresolved,
            warnings=[
                *list(synced.conflicts),
                *self._audio_notes(published),
                *self._picture_notes(published),
            ],
            moved=list(published.filed.moved) if published else [],
        )

    @staticmethod
    def _audio_notes(published: Optional[commands.Published]) -> list[str]:
        """Say so when recordings could not be filed as `.m4a`, which every browser plays."""
        count = len(published.filed.unplayable) if published else 0
        if not count:
            return []
        these = f"{count} recording{'s are' if count != 1 else ' is'}"
        if published and published.filed.ffmpeg_missing:
            return [
                f"{these} in a format most browsers cannot play, and could not be converted "
                "to .m4a because ffmpeg is not installed. Install ffmpeg, then import again "
                "to convert them. Until then they are in the box in their original format."
            ]
        return [
            f"{these} in a format most browsers cannot play, and ffmpeg could not convert "
            "them to .m4a (the files may be damaged). They are in the box in their original "
            "format and linked from the page."
        ]

    @staticmethod
    def _picture_notes(published: Optional[commands.Published]) -> list[str]:
        """Say so when pictures could not be filed as JPEG."""
        count = len(published.filed.unconverted) if published else 0
        if not count:
            return []
        these = f"{count} picture{'s' if count != 1 else ''}"
        return [
            f"{these} could not be converted to JPEG (the files may be damaged or only "
            "partly downloaded). They are in the box in their original format."
        ]

    @staticmethod
    def _remove_stale(box: Box, stale: set[str]) -> None:
        """Delete pages no item points at any more (a person was renamed or merged), then any
        folder that is left empty. Attachments are never touched: pages still link to them."""
        root = box.root.resolve()
        for relative in stale:
            page = (box.root / relative).resolve()
            if page.suffix != ".html" or not page.is_relative_to(root) or not page.is_file():
                continue
            page.unlink()
            folder = page.parent
            while folder != root and folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
                folder = folder.parent

    def unresolved(self, box: Box) -> list[dict[str, Any]]:
        """Handles Chattr found that no alias, contact or owner setting names yet."""
        database = box.caixa_dir / "work" / "chattr" / "Database" / "chattr.sqlite"
        if not database.is_file():
            return []
        link = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
        link.row_factory = sqlite3.Row
        try:
            rows = link.execute(
                "SELECT h.service, h.identifier, h.display_name, COUNT(m.id) AS messages "
                "FROM handles h LEFT JOIN messages m ON m.sender_handle_id = h.id "
                "WHERE h.person IS NULL GROUP BY h.id "
                "ORDER BY messages DESC, h.service, h.identifier"
            ).fetchall()
        finally:
            link.close()
        return [
            {
                "service": r["service"],
                "identifier": r["identifier"],
                "display_name": r["display_name"],
                "messages": r["messages"],
                "collector": self.info.id,
            }
            for r in rows
        ]

    def refresh(self, box: Box, progress: Callable[[Progress], None]) -> RunResult:
        """Re-match people from the box's aliases and redraw what changed; no new import."""
        root = box.work_dir("chattr")
        if not (root / "Database" / "chattr.sqlite").is_file():
            return RunResult()
        progress(Progress("preparing", message="Reading the box's people"))
        settings = self._settings(root)
        aliases = self._aliases(box, root / "aliases.json")
        progress(Progress("linking", message="Matching people"))
        self._name_people(settings, self._options({}, box), self._owner({}, box), aliases)
        return self._publish(box, settings, progress)


# --- The six sources --------------------------------------------------------------------------


class WhatsApp(_Chattr):
    info = CollectorInfo(
        id="whatsapp",
        name="WhatsApp",
        platform="WhatsApp",
        inputs=("file", "folder", "zip"),
        how_to_export=(
            "In WhatsApp, open a chat, tap the contact or group name, then 'Export chat' and "
            "choose 'Attach Media' to keep photos and voice notes. Save the .zip it makes and "
            "point Caixa at it, or unzip several chats into one folder and choose the folder. "
            "Each chat is exported separately."
        ),
        options_schema=_schema(),
    )
    attachments = MESSAGES

    def locate(self, source: Path, workdir: Path) -> list[Path]:
        def find(folder: Path) -> list[Path]:
            return [
                *folder.rglob("_chat.txt"),
                *(p for p in folder.rglob("WhatsApp Chat*.txt") if p.name != "_chat.txt"),
            ]

        return inputs.resolve(
            source,
            find,
            workdir,
            expects=(
                "a WhatsApp 'Export chat' file (_chat.txt, or a .txt named 'WhatsApp Chat …'), "
                "on its own or in a folder or zip"
            ),
        )

    def convert(
        self,
        settings: Settings,
        item: Path,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
        attachments_dir: Optional[Path],
        final: bool,
    ) -> None:
        commands.convert(
            settings,
            "whatsapp",
            item,
            owner=owner,
            aliases=aliases,
            attachments_dir=attachments_dir,
            contacts=options.get("contacts") or None,
            resolve=False,
        )


class _Meta(_Chattr):
    """Messenger and Instagram: one Meta export can hold threads of both."""

    services: tuple[str, ...] = ()
    attachments = MESSAGES

    def locate(self, source: Path, workdir: Path) -> list[Path]:
        def find(folder: Path) -> list[Path]:
            return [p for p in folder.rglob("message_1.json") if self._service(p) in self.services]

        found = inputs.resolve(
            source,
            find,
            workdir,
            expects=(
                "message_1.json files from a Facebook or Instagram 'Download your information' "
                "export (choose the JSON format, not HTML)"
            ),
        )
        return [p for p in found if self._service(p) in self.services or p == source]

    @staticmethod
    def _service(path: Path) -> str:
        return "instagram" if "instagram" in str(path).lower() else "messenger"

    def convert(
        self,
        settings: Settings,
        item: Path,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
        attachments_dir: Optional[Path],
        final: bool,
    ) -> None:
        service = self._service(item)
        if options.get("service") in ("messenger", "instagram"):
            service = str(options["service"])
        commands.convert(
            settings,
            service,
            item,
            owner=owner,
            aliases=aliases,
            attachments_dir=attachments_dir,
            contacts=options.get("contacts") or None,
            resolve=False,
        )


class Messenger(_Meta):
    services = ("messenger", "instagram")  # a Meta export can hold both; it is imported whole
    info = CollectorInfo(
        id="messenger",
        name="Messenger and Instagram",
        platform="Meta",
        inputs=("file", "folder", "zip"),
        how_to_export=(
            "In Meta's Accounts Center choose 'Your information and permissions', then "
            "'Download your information'. Pick Messenger and/or Instagram messages, set the "
            "format to JSON, and download. Point Caixa at the .zip, at the unzipped folder, or "
            "at one thread's message_1.json. Threads from both services are imported."
        ),
        options_schema=_schema(
            service={
                "type": "string",
                "default": "auto",
                "enum": ["auto", "messenger", "instagram"],
                "title": "Service",
                "description": "Which service the threads belong to; 'auto' decides from the folder names.",
            }
        ),
    )


class Mail(_Chattr):
    info = CollectorInfo(
        id="mail",
        name="Mail (Gmail and other mbox)",
        platform="Mail",
        inputs=("file", "folder", "zip"),
        how_to_export=(
            "For Gmail, go to Google Takeout (takeout.google.com), choose only 'Mail', and "
            "download the export. Point Caixa at the .zip, the unzipped Takeout folder, or the "
            ".mbox file inside it. Any other mail program that exports .mbox files works too."
        ),
        options_schema=_schema(),
    )
    attachments = MAIL_ATTACHMENTS

    def locate(self, source: Path, workdir: Path) -> list[Path]:
        return inputs.resolve(
            source,
            lambda folder: list(folder.rglob("*.mbox")),
            workdir,
            expects="one or more .mbox files (Google Takeout, product 'Mail')",
        )

    def convert(
        self,
        settings: Settings,
        item: Path,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
        attachments_dir: Optional[Path],
        final: bool,
    ) -> None:
        commands.convert(
            settings,
            "mail",
            item,
            owner=owner,
            aliases=aliases,
            attachments_dir=attachments_dir,
            contacts=options.get("contacts") or None,
            resolve=False,
        )


def _common_folder(paths: list[Path]) -> list[Path]:
    return [Path(os.path.commonpath(paths))] if paths else []


class GoogleVoice(_Chattr):
    info = CollectorInfo(
        id="googlevoice",
        name="Google Voice",
        platform="Google Voice",
        inputs=("folder", "zip"),
        how_to_export=(
            "Go to Google Takeout (takeout.google.com), choose only 'Voice', and download the "
            "export. Point Caixa at the .zip or at the unzipped folder; the calls, texts and "
            "voicemail are in Takeout/Voice/Calls."
        ),
        options_schema=_schema(**_SPEECH_OPTIONS),
    )
    attachments = GOOGLE_VOICE_AUDIO

    def locate(self, source: Path, workdir: Path) -> list[Path]:
        return inputs.resolve(
            source,
            lambda folder: _common_folder(list(folder.rglob("*.html"))),
            workdir,
            accept_files=False,
            expects=(
                "the .html files of a Google Takeout 'Voice' export (the Calls folder), in a "
                "folder or zip"
            ),
        )

    def convert(
        self,
        settings: Settings,
        item: Path,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
        attachments_dir: Optional[Path],
        final: bool,
    ) -> None:
        commands.convert(
            settings,
            "googlevoice",
            item,
            owner=owner,
            aliases=aliases,
            attachments_dir=attachments_dir,
            transcriber=_transcriber(settings, options, final),
            contacts=options.get("contacts") or None,
            resolve=False,
        )


VOICEMAIL_EXPECTS = (
    "a folder with voicemail.db, or audio files named like '(2018-12-21) 15 02 31 - Jane Smith.amr'"
)


def _voicemail_hints(files: list[Path]) -> list[str]:
    """Audio is there but no name was readable: say so, since that is the likely cause."""
    audio = [p for p in files if p.suffix.lower() in AUDIO_SUFFIXES]
    if not audio:
        return []
    return [
        f"{len(audio)} audio file{'s were' if len(audio) != 1 else ' was'} found, but none of "
        "their names start with a date and time like '(2018-12-21) 15 02 31 - Jane Smith.amr', "
        "so Caixa cannot tell when each one came in."
    ]


def _voicemail_folders(folder: Path) -> list[Path]:
    """Folders holding a `voicemail.db`; failing that, the folder if it holds named audio files."""
    databases = sorted({p.parent for p in folder.rglob("voicemail.db")})
    if databases:
        return databases
    return [folder] if audio_files(folder) else []


class Voicemail(_Chattr):
    info = CollectorInfo(
        id="voicemail",
        name="iPhone voicemail",
        platform="iPhone",
        inputs=("folder", "zip"),
        how_to_export=(
            "Point Caixa at a folder or a .zip of voicemail in either form. From a Finder or "
            "iTunes backup: the folder holds voicemail.db and the numbered .amr audio files (in a "
            "backup they are under Library/Voicemail). From an export tool: audio files named by "
            "when they came in and who from, like '(2018-12-21) 15 02 31 - Jane Smith.amr' (the "
            "caller can be a name or a number; those times have no time zone, so they are kept "
            "as written)."
        ),
        options_schema=_schema(
            **_SPEECH_OPTIONS,
        ),
    )
    attachments = VOICEMAIL_AUDIO

    def locate(self, source: Path, workdir: Path) -> list[Path]:
        if source.is_file() and source.name == "voicemail.db":
            return [source.parent]
        return inputs.resolve(
            source,
            _voicemail_folders,
            workdir,
            accept_files=False,
            expects=VOICEMAIL_EXPECTS,
            hints=_voicemail_hints,
        )

    def convert(
        self,
        settings: Settings,
        item: Path,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
        attachments_dir: Optional[Path],
        final: bool,
    ) -> None:
        transcriber = _transcriber(settings, options, final)
        commands.convert(
            settings,
            "voicemail",
            item,
            owner=owner,
            aliases=aliases,
            attachments_dir=attachments_dir,
            transcriber=transcriber,
            contacts=options.get("contacts") or None,
            resolve=False,
        )


class IMessage(_Chattr):
    def __init__(self) -> None:
        preferences = _imessage_defaults()
        self.info = CollectorInfo(
            id="imessage",
            name="iMessage",
            platform="Apple",
            inputs=("database", "folder"),
            how_to_export=(
                "iMessage lives in ~/Library/Messages/chat.db on your Mac. macOS only lets an "
                "app read it after you give that app 'Full Disk Access' in System Settings, "
                "Privacy & Security. Caixa opens the database read-only and never changes it. "
                "Point Caixa at chat.db (or a copy of it)."
            ),
            options_schema=_schema(
                mac_contacts={
                    "type": "boolean",
                    "default": True,
                    "title": "Use this Mac's Contacts",
                    "description": (
                        "Name people from the Contacts app on this Mac (read-only; needs Full "
                        "Disk Access, like Messages). A contacts file, if given, is used as well. "
                        "Starts from the choice in Settings, under Contacts."
                    ),
                    "x-setting": "contacts.mac",
                },
                region={
                    "type": "string",
                    "default": "US",
                    "title": "Phone region",
                    "description": "Two-letter country code used to read local phone numbers.",
                    "x-setting": "contacts.region",
                },
                spam_mode={
                    "type": "string",
                    "default": preferences["spam_filtering"]["mode"],
                    "enum": list(preferences["spam_filtering"]["available_modes"]),
                    "title": "Spam filtering",
                    "description": "How much machine-sent noise to tag (nothing is thrown away).",
                },
                workers={
                    "type": "integer",
                    "default": preferences["performance"]["workers"],
                    "minimum": 1,
                    "maximum": preferences["performance"]["max_workers"],
                    "title": "Workers",
                    "description": "How many parts of the database are read at once.",
                },
                limit={
                    "type": "integer",
                    "default": 0,
                    "minimum": 0,
                    "title": "Limit",
                    "description": "Read only this many messages (0 reads everything); for trying it out.",
                },
                attachment_root={
                    "type": "string",
                    "default": "",
                    "title": "Attachments folder",
                    "description": "Where macOS keeps attachments; empty uses the 'Attachments' "
                    "folder next to chat.db when there is one.",
                },
            ),
        )

    def locate(self, source: Path, workdir: Path) -> list[Path]:
        return inputs.resolve(
            source,
            lambda folder: list(folder.rglob("chat.db")),
            workdir,
            expects="a chat.db file (on a Mac: ~/Library/Messages/chat.db), alone or in a folder or zip",
        )

    attachments = IMESSAGE_FILES

    def convert(
        self,
        settings: Settings,
        item: Path,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
        attachments_dir: Optional[Path],
        final: bool,
    ) -> Optional[list[str]]:
        attachment_root: Optional[str] = options.get("attachment_root") or None
        if attachment_root is None and (item.parent / "Attachments").is_dir():
            attachment_root = str(item.parent / "Attachments")
        result = commands.convert_imessage(
            settings,
            db_path=item,
            contacts=options.get("contacts") or None,
            mac_contacts=bool(options.get("mac_contacts", True)),
            region=options.get("region") or None,
            attachment_root=attachment_root,
            attachments_dir=attachments_dir if final else None,
            workers=options.get("workers"),
            spam_mode=options.get("spam_mode"),
            limit=options.get("limit") or None,
            owner=owner,
            aliases=aliases,
        )
        if not result.missing_attachments:
            return None
        if final:
            return [
                f"{result.missing_attachments:,} attachments are not on this Mac, so they were "
                "not copied (their messages say so). Messages fetches a file from iCloud when "
                "its part of the conversation is shown: load them there and run this import "
                "again to add them."
            ]
        report = commands.missing_attachments(item, attachment_root)
        most = ", ".join(entry.name for entry in report.conversations[:5])
        return [
            f"{report.missing:,} of {report.total:,} attachments "
            f"({report.missing_bytes / 1e9:.2f} GB) are not on this Mac yet, in "
            f"{len(report.conversations):,} conversations. Messages fetches a file from iCloud "
            "when its part of the conversation is shown, so scroll back in those conversations "
            f"before importing to bring them in. The most are in: {most}. "
            "For the full list run: chattr-cli missing"
        ]


def collectors() -> list[_Chattr]:
    """The entry point: the six collectors this package provides."""
    return [IMessage(), WhatsApp(), Messenger(), Mail(), GoogleVoice(), Voicemail()]
