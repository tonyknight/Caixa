"""A box's own settings, kept in `.caixa/box.yaml` beside its name.

Everything here is a plain value with a default, described by a JSON Schema so the Settings page
can render a form without knowing any of it. Nothing is ever sent anywhere unless a person turns it
on and names the place; and a place on the internet needs a second, explicit yes
(`translation.allow_remote`, `summaries.allow_remote`). The key a paid service needs is not a setting and is not
kept in the box: see `caixa.translation.Keys`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from caixa.box import Box
from caixa import summaries, translation
from caixa.collectors.options import OptionsError, defaults, validate

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "privacy.default": {
            "type": "string",
            "default": "private",
            "enum": ["private", "family", "public"],
            "title": "Who can see new items",
            "description": "Privacy given to items when they are first imported.",
        },
        "contacts.mac": {
            "type": "boolean",
            "default": True,
            "title": "Use this Mac's Contacts",
            "description": (
                "Name people in every import from the Contacts app on this Mac. Caixa only "
                "reads it. macOS allows that once the program you start Caixa from (Terminal) "
                "has Full Disk Access in System Settings, Privacy & Security; the web browser "
                "needs no permission. On other computers this does nothing."
            ),
        },
        "contacts.file": {
            "type": "string",
            "default": "",
            "title": "Contacts file (.vcf)",
            "description": (
                "A vCard export of your address book, for when this Mac's Contacts cannot be "
                "used or do not have everyone. Set it once here and every import uses it. "
                "Where both know a number, the file wins."
            ),
            "x-picker": "file",
        },
        "contacts.region": {
            "type": "string",
            "default": "US",
            "title": "Phone region",
            "description": (
                "Two-letter country code used to read phone numbers written without a "
                "country code, such as US, BR or PT."
            ),
        },
        "translation.enabled": {
            "type": "boolean",
            "default": False,
            "title": "Translate messages that are not in English",
            "description": (
                "Off by default. When on, each import translates the messages that need it "
                "(not English, and not already translated by their author) and shows the "
                "translation under the original. Text is sent only to the endpoint below."
            ),
        },
        "translation.provider": {
            "type": "string",
            "default": "auto",
            "enum": ["auto", "apple", "endpoint"],
            "title": "Translations are written by",
            "description": (
                "An OpenAI-compatible endpoint (below), or Apple Intelligence: the Mac's own model "
                "(macOS 26 or later, Apple silicon, Apple Intelligence on). Apple Intelligence keeps "
                "every message on this Mac and runs as many at once as Workers says."
            ),
            "x-labels": {
                "auto": "Automatic: Apple Intelligence when this Mac has it, else the endpoint",
                "apple": "Apple Intelligence (on this Mac)",
                "endpoint": "An endpoint (the address and model below)",
            },
        },
        "translation.endpoint": {
            "type": "string",
            "default": "",
            "title": "Translation endpoint",
            "description": (
                "An OpenAI-compatible address. A model on this computer: "
                "http://localhost:11434/v1 (Ollama) or http://localhost:1234/v1 (LM Studio). "
                "A paid service: https://openrouter.ai/api/v1 or https://api.deepseek.com/v1."
            ),
        },
        "translation.model": {
            "type": "string",
            "default": "",
            "title": "Translation model",
            "description": (
                "The model's name as the endpoint knows it, such as llama3.1, deepseek-chat "
                "or anthropic/claude-haiku-4.5."
            ),
        },
        "translation.allow_remote": {
            "type": "boolean",
            "default": False,
            "title": "Allow a service on the internet",
            "description": (
                "Needed for any endpoint that is not on this computer. The text of the "
                "messages being translated is sent to that service, and the service may "
                "charge for it. Leave off to keep translation on this computer."
            ),
        },
        "summaries.enabled": {
            "type": "boolean",
            "default": False,
            "title": "Summarize mail conversations",
            "description": (
                "Off by default. When on, each mail import asks the model below for a summary of "
                "30 to 50 words of every conversation it brought in, in the conversation's own "
                "language, shown on the person pages and marked as written by a model. Mail text "
                "is sent only to the endpoint below."
            ),
        },
        "summaries.provider": {
            "type": "string",
            "default": "auto",
            "enum": ["auto", "apple", "endpoint"],
            "title": "Summaries are written by",
            "description": (
                "An OpenAI-compatible endpoint (below; translation's when left empty), or Apple "
                "Intelligence: the Mac's own model, which keeps every mail on this Mac. It reads "
                "less at a time, so long conversations are summarized from their first and last "
                "mails."
            ),
            "x-labels": {
                "auto": "Automatic: Apple Intelligence when this Mac has it, else the endpoint",
                "apple": "Apple Intelligence (on this Mac)",
                "endpoint": "An endpoint (the address and model below)",
            },
        },
        "summaries.endpoint": {
            "type": "string",
            "default": "",
            "title": "Summaries endpoint",
            "description": (
                "An OpenAI-compatible address, as for translation. Leave empty to use the "
                "translation endpoint."
            ),
        },
        "summaries.model": {
            "type": "string",
            "default": "",
            "title": "Summaries model",
            "description": (
                "The model's name as the endpoint knows it. Leave empty to use the translation "
                "model."
            ),
        },
        "summaries.allow_remote": {
            "type": "boolean",
            "default": False,
            "title": "Allow a service on the internet for summaries",
            "description": (
                "Needed for a summaries endpoint that is not on this computer: the text of the "
                "mails being summarized is sent to that service, and it may charge for it. "
                "When summaries use the translation endpoint, translation's yes is enough."
            ),
        },
        "workers": {
            "type": "integer",
            "default": min(os.cpu_count() or 1, 12),
            "minimum": 1,
            "maximum": 12,
            "title": "Workers",
            "description": (
                "How many processes work at once where work can be shared out: reading, cleaning "
                "and importing mail, and writing the pages. Starts at this computer's number of "
                "processors (at most 12). "
                "Fewer leaves the computer freer for other things."
            ),
        },
        "speech.model": {
            "type": "string",
            "default": "",
            "title": "Speech-to-text model",
            "description": (
                "Path to a speech model file stored on this computer (never downloaded). "
                "The import wizard starts from it; transcription itself is switched on there."
            ),
            "x-picker": "file",
        },
        "speech.language": {
            "type": "string",
            "default": "",
            "title": "Speech language",
            "description": (
                "A language code such as 'en' or 'pt'; empty detects it. "
                "The import wizard starts from it."
            ),
        },
    },
}


#: The settings' own version in `box.yaml`. 2: summaries and translation choose Automatic (Apple
#: Intelligence when the Mac has it) by default; "An endpoint" saved before was only the old default.
VERSION = 2


def load(box: Box) -> dict[str, Any]:
    """Every setting, with defaults for the ones nobody has changed."""
    document = _read(box)
    saved = dict(document.get("settings", {}))
    if int(document.get("settings_version") or 1) < 2:  # (the old default becomes the new one)
        for name in ("summaries.provider", "translation.provider"):
            if saved.get(name) == "endpoint":
                saved[name] = "auto"
    return {**defaults(SCHEMA), **{k: v for k, v in saved.items() if k in SCHEMA["properties"]}}


def save(box: Box, values: Mapping[str, Any]) -> dict[str, Any]:
    """Change settings (raises `OptionsError` listing every problem, saving nothing)."""
    merged = validate(SCHEMA, {**load(box), **values}, subject="the settings")
    wrong = translation.problems(merged) + summaries.problems(merged)
    contacts_file = str(merged.get("contacts.file") or "").strip()
    if contacts_file and not Path(contacts_file).expanduser().is_file():
        wrong.append(f"Contacts file: there is no file at {contacts_file}.")
    if wrong:
        raise OptionsError(wrong)
    box.update_state(lambda document: document.update(settings=merged, settings_version=VERSION))
    return merged


def _read(box: Box) -> dict[str, Any]:
    document = json.loads((box.caixa_dir / "box.yaml").read_text(encoding="utf-8"))
    return document if isinstance(document, dict) else {}
