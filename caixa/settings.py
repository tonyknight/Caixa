"""A box's own settings, kept in `.caixa/box.yaml` beside its name.

Everything here is a plain value with a default, described by a JSON Schema so the Settings page
can render a form without knowing any of it. Local services only: nothing is ever sent anywhere
unless a person turns it on and names the place.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping

from caixa.box import Box
from caixa.collectors.options import defaults, validate

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
        "translation.enabled": {
            "type": "boolean",
            "default": False,
            "title": "Translate with a local model",
            "description": "Off by default. When on, text is sent only to the endpoint below.",
        },
        "translation.endpoint": {
            "type": "string",
            "default": "",
            "title": "Translation endpoint",
            "description": "An OpenAI-compatible address on this computer, such as "
            "http://localhost:11434/v1.",
        },
        "translation.model": {
            "type": "string",
            "default": "",
            "title": "Translation model",
            "description": "The model name the endpoint serves.",
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


def load(box: Box) -> dict[str, Any]:
    """Every setting, with defaults for the ones nobody has changed."""
    saved = _read(box).get("settings", {})
    return {**defaults(SCHEMA), **{k: v for k, v in saved.items() if k in SCHEMA["properties"]}}


def save(box: Box, values: Mapping[str, Any]) -> dict[str, Any]:
    """Change settings (raises `OptionsError` listing every problem, saving nothing)."""
    merged = validate(SCHEMA, {**load(box), **values}, subject="the settings")
    document = _read(box)
    document["settings"] = merged
    path = box.caixa_dir / "box.yaml"
    temporary = path.with_name("box.yaml.part")
    temporary.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", "utf-8")
    os.replace(temporary, path)
    return merged


def _read(box: Box) -> dict[str, Any]:
    document = json.loads((box.caixa_dir / "box.yaml").read_text(encoding="utf-8"))
    return document if isinstance(document, dict) else {}
