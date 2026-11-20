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
from typing import Any, Callable, Mapping, Optional, Union

import chattr.commands as commands
import chattr.preflight as preflight
from chattr.config import Settings
from chattr.database_manager import DatabaseManager, unresolved_rows
from chattr.filing import playable_copy
from chattr.meta_friends import Friends, find_friend_files, find_profile_name, load_friends
from chattr.parsers.voicemail_parser import AUDIO_SUFFIXES, audio_files
from chattr.render import Renderer
from chattr.transcription import TranscriptionUnavailable, make_transcriber
from chattr.translation import TranslationError, translate_archive

from caixa import owner as owner_file
from caixa import settings as box_settings
from caixa import translation
from caixa.box import Box
from caixa.collectors import inputs
from caixa.collectors.base import CollectorInfo, Preview, Progress, RunResult
from caixa.collectors.inputs import InputError
from caixa.collectors.messages import alias_kind, sync_chattr
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


#: Services that show a sender by the name the owner saved for them (in their phone, in Google
#: Contacts; iPhone voicemail exported as files named after the caller), so a sender shown by a name
#: is that person.
SHOWN_BY_OWN_NAME = ("WhatsApp", "Google Voice", "Voicemail")


def own_name(value: Optional[str]) -> Optional[str]:
    """`value` when it is a name a person was saved under; None for a phone number, an email
    address, a name someone gave themselves (WhatsApp writes those after `~`) or a placeholder."""
    text = " ".join((value or "").split())
    if not text or "@" in text or text.startswith("~") or not any(c.isalpha() for c in text):
        return None
    if text.casefold() in ("unknown", "me", "you"):
        return None
    if alias_kind("", text)[0] == "phone":
        return None
    return text


#: Keys, in the options, for what the owner removed from the box and where the box is.
REMOVED, BOX_ROOT = "_removed", "_box_root"


def _delete_files(root: Path, relative_paths: list[str]) -> int:
    """Delete files of the box by their path inside it (never outside it, never in `.caixa`),
    with a playable copy an older version made beside one, and folders that leave empty."""
    base = root.resolve()
    gone = 0
    for relative in relative_paths:
        file = (base / relative).resolve()
        inside = file.is_relative_to(base) and ".caixa" not in file.relative_to(base).parts
        if not inside:
            continue
        for candidate in (file, playable_copy(file)):
            if candidate is not None and candidate.is_file():
                candidate.unlink()
                gone += 1
        folder = file.parent
        while folder != base and folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
            folder = folder.parent
    return gone


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
        # What the owner removed from the box stays out (see caixa.owner), and its files go.
        merged[REMOVED] = owner_file.load(box)["removed"] if box is not None else []
        merged[BOX_ROOT] = str(box.root) if box is not None else ""
        return merged

    @staticmethod
    def _name_people(
        settings: Settings,
        options: Mapping[str, Any],
        owner: Optional[str],
        aliases: Optional[Path],
    ) -> list[str]:
        """Link every handle to a person: the box's aliases, the contacts file, this Mac's Contacts.
        Returns what a person should know (groups left out)."""
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
        # Group conversations: only those the owner wrote in (but every mail conversation, which
        # the owner chose in Sort mail), and of their members only those who wrote (see
        # DatabaseManager.tidy_groups). Then what is left unnamed on WhatsApp,
        # Google Voice and voicemail and is shown by a name (not a number) is a name from the
        # owner's own phone or Google contacts: take it as the person. The same name as a contact
        # (or anyone else) is the same person.
        notes: list[str] = []
        database = commands.central_database(settings)
        if database.exists():
            match = owner_file.removed_matcher(
                options.get(REMOVED) or [], str(options.get("region") or "US")
            )
            with DatabaseManager(database) as db:
                tidy = db.tidy_groups(keep=("Mail",))  # mail comes in as the owner chose it
                for service in SHOWN_BY_OWN_NAME:
                    db.name_handles(service, own_name)
                taken = db.remove_people(match) if match else None
                region = str(options.get("region") or "US")
                forwarded = db.drop_forwarded_copies(region)  # Google Voice's, kept by Messages
            if forwarded.messages:
                count = forwarded.messages
                notes.append(
                    f"{count:,} text{'s' if count != 1 else ''} that Google Voice forwarded to "
                    f"your phone {'were' if count != 1 else 'was'} also in Messages; the Google "
                    "Voice record, with both sides of the conversation, is kept."
                )
            if forwarded.files and options.get(BOX_ROOT):
                _delete_files(Path(str(options[BOX_ROOT])), forwarded.files)
            if taken and taken.conversations:
                count = taken.conversations
                notes.append(
                    f"{count:,} conversation{'s' if count != 1 else ''} with people you removed "
                    f"from this box {'were' if count != 1 else 'was'} left out."
                )
            if taken and options.get(BOX_ROOT):
                _delete_files(Path(str(options[BOX_ROOT])), taken.files)
            count = len(tidy.groups_removed)
            if count:
                notes.append(
                    f"{count:,} group conversation{'s' if count != 1 else ''} you never wrote "
                    f"in {'were' if count != 1 else 'was'} left out."
                )
                print(f"Left out, groups you never wrote in ({count}):")
                for name in sorted(tidy.groups_removed, key=str.casefold):
                    print(f"  {name}")
            for service in sorted(tidy.unchecked):
                notes.append(
                    f"Your own messages could not be recognised in {service}, so its group "
                    "conversations were all kept. Check 'Your name' in the import's options."
                )
        return notes

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
            owner_file.apply(box, master)  # names in the owner's preference file come first
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
        said = self._name_people(settings, options, owner, aliases)
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
            warnings=said,
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
        notes += self._name_people(settings, opts, owner, aliases)
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
        with box.master() as master:
            categories = master.categories()
        published = commands.publish(
            settings,
            out=box.root,
            attachments_dirs=[incoming / stage for stage in STAGES],
            pages_list=box.caixa_dir / "pages.json",
            progress=filing,
            before_pages=lambda: progress(Progress("rendering", message="Writing the pages")),
            categories=categories,
            title=box.name,
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
        try:
            rows = unresolved_rows(link)
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
            "choose 'Attach Media' to keep photos and voice notes. Each chat is exported "
            "separately, as a .zip: choose one, or put them all in one folder and choose the "
            "folder to import every chat at once."
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


#: Private keys in the options a Meta import passes to `convert`: the friends to keep threads
#: with (None: keep every thread), and the list the threads left out are added to.
FRIENDS, OWNERS, LEFT_OUT = "_friends", "_owners", "_left_out"


def _folded(name: Optional[str]) -> str:
    return " ".join((name or "").split()).casefold()


class _Meta(_Chattr):
    """Messenger and Instagram: one Meta export can hold threads of both.

    Every thread in the export is a candidate: each folder holding a `message_1.json`, in
    `messages/inbox`, `archived_threads`, `e2ee_cutover`, `message_requests` and `filtered_threads`.
    What is kept, unless the options say otherwise:

    - not `message_requests` (people who wrote and were never answered) or `filtered_threads`
      (what Facebook set aside as spam);
    - Messenger threads with someone on the owner's friends lists (friends and removed friends, read
      from the same export) or a deactivated account; Marketplace buyers and sellers, pages and
      strangers are left out, and friends are named by the name Facebook gives them;
    - group threads the owner wrote in at least once (known by the box's owner name and the
      export's own profile name), which leaves out groups someone added them to and they left
      (this is the rule for every group, see `DatabaseManager.tidy_groups`; here it also says
      which groups they were in the log).

    Instagram threads are only subject to the first rule: Instagram has follows, not friends.
    """

    services: tuple[str, ...] = ()
    attachments = MESSAGES

    #: Folders of threads the owner never took part in, left out unless asked for.
    REQUESTS = ("message_requests", "filtered_threads")

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
        notes: list[str] = []
        left_out: dict[str, list[str]] = {"requests": [], "friends": [], "groups": []}
        if not options.get("include_requests", False):
            requests = [i for i in items if any(part in self.REQUESTS for part in i.parts)]
            left_out["requests"] = [i.parent.name for i in requests]
            items = [i for i in items if i not in requests]
            if not items:
                raise InputError(
                    "Every conversation in this export is a message request or filtered "
                    "message, which are left out. Tick 'Include message requests and filtered "
                    "messages' to import them."
                )
        friends: Optional[Friends] = None
        messenger = [item for item in items if self._service(item) == "messenger"]
        if messenger:
            given = str(options.get("friends_list") or "").strip()
            start = Path(given).expanduser() if given else messenger[0]
            files = find_friend_files(start)
            friends = load_friends(files) if files else None
            if given and not friends:
                raise InputError(
                    f"No Facebook friends list could be read at {given}. Point it at the "
                    "export's friends folder (connections/friends) or at your_friends.json."
                )
        only = bool(options.get("only_friends", True)) and bool(messenger)
        if only and not friends:
            notes.append(
                "No Facebook friends list was found with these messages, so every Messenger "
                "conversation was kept, Marketplace and strangers included. To keep only "
                "friends, include 'Friends' (Connections) when downloading your information, "
                "or point 'Facebook friends list' at the export's connections/friends folder."
            )
        profile = find_profile_name(items[0]) if items else None
        mine = {name for name in (owner, profile) if name}
        chosen = {
            **options,
            FRIENDS: friends if only else None,
            OWNERS: {_folded(name) for name in mine},
            LEFT_OUT: left_out,
        }
        notes += super()._import_all(
            settings, items, chosen, owner, aliases, attachments_dir, final, progress
        )
        with DatabaseManager(commands.central_database(settings)) as db:
            if profile and owner and _folded(profile) != _folded(owner):
                # the owner's own Facebook name is the owner, not someone else
                for service in ("Messenger", "Instagram"):
                    db.mark_owner(service, profile, owner)
            if friends:
                db.name_handles("Messenger", friends.name_of)
        notes += self._left_out_notes(left_out, final)
        return notes

    @staticmethod
    def _left_out_notes(left_out: dict[str, list[str]], final: bool) -> list[str]:
        """What was left out and why, in words; with `final`, who it was with goes to the log."""
        said = {
            "requests": (
                "conversation{s} from message requests and filtered (spam) messages "
                "{was} left out (people who wrote and were never answered)."
            ),
            "friends": (
                "Messenger conversation{s} with nobody from your Facebook friends list "
                "(Marketplace, pages, strangers) {was} left out."
            ),
            "groups": "group conversation{s} you never wrote in {was} left out.",
        }
        heading = {
            "requests": "message requests and filtered messages",
            "friends": "nobody on the friends lists",
            "groups": "groups you never wrote in",
        }
        notes = []
        for reason, entries in left_out.items():
            if not entries:
                continue
            count = len(entries)
            words = said[reason].format(
                s="" if count == 1 else "s", was="was" if count == 1 else "were"
            )
            tail = " Who they were with is in the job's log." if final else ""
            notes.append(f"{count:,} {words}{tail}")
            if final:
                print(f"Left out, {heading[reason]} ({count}):")
                for entry in sorted(entries, key=str.casefold):
                    print(f"  {entry}")
        return notes

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
        friends = options.get(FRIENDS) if service == "messenger" else None
        owners = options.get(OWNERS) if service == "messenger" else None

        def keep(conversation: Any, messages: list[dict[str, Any]]) -> Union[bool, str]:
            if friends is not None and not friends.in_conversation(conversation):
                return "friends"
            if owners and conversation.type == "group":
                if not any(_folded(m.get("author")) in owners for m in messages):
                    return "groups"
            return True

        try:
            commands.convert(
                settings,
                service,
                item,
                owner=owner,
                aliases=aliases,
                attachments_dir=attachments_dir,
                contacts=options.get("contacts") or None,
                resolve=False,
                keep=keep if friends is not None or owners else None,
            )
        except commands.LeftOut as left:
            conversation = left.conversation
            mine = owners or set()
            others = [p for p in conversation.participants if p and _folded(p) not in mine]
            label = ", ".join(others) or conversation.name or conversation.source_id
            if left.reason == "groups":
                label = f"{conversation.name or conversation.source_id}: {label}"
            options[LEFT_OUT][left.reason or "friends"].append(label)


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
            },
            include_requests={
                "type": "boolean",
                "default": False,
                "title": "Include message requests and filtered messages",
                "description": (
                    "Message requests are from people who wrote to you and were never "
                    "answered; filtered messages are what Facebook set aside as spam. Both are "
                    "left out unless this is ticked."
                ),
            },
            only_friends={
                "type": "boolean",
                "default": True,
                "title": "Only conversations with Facebook friends",
                "description": (
                    "Leave out Messenger conversations in which nobody is on your Facebook "
                    "friends list or removed-friends list: Marketplace buyers and sellers, "
                    "pages and strangers. The lists are read from the same export. "
                    "Instagram conversations are not affected."
                ),
            },
            friends_list={
                "type": "string",
                "default": "",
                "title": "Facebook friends list",
                "description": (
                    "Only needed when Caixa cannot find the list beside the messages (it was "
                    "downloaded separately): the export's connections/friends folder, or "
                    "your_friends.json."
                ),
                "x-picker": "file",
            },
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
        # The mail workflow (caixa.mail) passes the account the mail comes from and the workers.
        parser_options = {k: options[k] for k in ("account", "workers") if options.get(k)}
        commands.convert(
            settings,
            "mail",
            item,
            owner=owner,
            aliases=aliases,
            attachments_dir=attachments_dir,
            contacts=options.get("contacts") or None,
            resolve=False,
            parser_options=parser_options or None,
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
        if final and result.dropped_files and options.get(BOX_ROOT):
            # files of the conversation an earlier version mixed everyone into
            _delete_files(Path(str(options[BOX_ROOT])), result.dropped_files)
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
