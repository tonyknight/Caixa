"""Translation for a box: which service translates, the key it needs, and a way to try it.

Chattr does the translating (`chattr.translation`): it decides which messages need it, asks an
OpenAI-compatible endpoint, and holds the model to a translation and nothing else. This module is
what Caixa adds around that:

- the box's settings say whether translation is on, and name the endpoint and the model. The
  endpoint can be a model on this computer (Ollama, LM Studio, llama.cpp) or a paid service
  (OpenRouter, DeepSeek, OpenAI); a service on the internet is used only when the person has also
  ticked "allow", because it means message text leaves the computer;
- the API key a paid service needs is kept in Caixa's own per-user folder, in a file only its owner
  can read. It is never written into a box (a box is copied, shared and backed up), never sent to
  the interface, and it is remembered for one host: change the endpoint to another host and the key
  is not sent there;
- `check` sends one fixed sentence (never anything from the archive) so a person can see that the
  endpoint, the model and the key work before any import relies on them.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from chattr.translation import (
    OpenAICompatibleTranslator,
    TranslationError,
    TranslationUnavailable,
    is_local_endpoint,
)

from caixa.state import caixa_home

#: The sentence `check` sends. Portuguese, the language of the project's first archive.
SAMPLE = "Bom dia! Chegamos bem e vamos jantar com a família amanhã."
#: Requests sent at once: a model on this computer answers one at a time, a service many.
LOCAL_WORKERS, REMOTE_WORKERS = 1, 4


def _host(endpoint: str) -> str:
    parsed = urlparse(endpoint.strip())
    return (parsed.hostname or "").lower() + (f":{parsed.port}" if parsed.port else "")


class Keys:
    """The translation key, in `<Caixa home>/keys.json`, readable only by its owner."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self.path = Path(home or caixa_home()) / "keys.json"

    def _read(self) -> dict[str, Any]:
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        saved = document.get("translation") if isinstance(document, dict) else None
        return saved if isinstance(saved, dict) else {}

    def get(self, endpoint: str) -> Optional[str]:
        """The saved key, when it was saved for this endpoint's host; otherwise None."""
        saved = self._read()
        host = _host(endpoint)
        key = saved.get("key")
        return str(key) if key and host and saved.get("host") == host else None

    def set(self, endpoint: str, key: str) -> None:
        """Save `key` for this endpoint's host; an empty key forgets the saved one."""
        if not key.strip():
            self.path.unlink(missing_ok=True)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        part = self.path.with_name(self.path.name + ".part")
        handle = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump({"translation": {"host": _host(endpoint), "key": key.strip()}}, out)
        os.replace(part, self.path)


def problems(values: Mapping[str, Any]) -> list[str]:
    """What is wrong with the translation settings, in words; empty when they can be saved."""
    endpoint = str(values.get("translation.endpoint") or "").strip()
    model = str(values.get("translation.model") or "").strip()
    found: list[str] = []
    if endpoint:
        parsed = urlparse(endpoint)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            found.append(
                f"Translation endpoint: '{endpoint}' is not a web address. It should look like "
                "http://localhost:11434/v1 or https://openrouter.ai/api/v1."
            )
        elif not is_local_endpoint(endpoint) and not values.get("translation.allow_remote"):
            if values.get("translation.enabled"):
                found.append(
                    f"Translation endpoint: {parsed.hostname} is on the internet, so message "
                    "text would leave this computer. Tick 'Allow a service on the internet' "
                    "to agree to that, or use an address on this computer."
                )
    if values.get("translation.enabled") and not endpoint:
        found.append("Translation is on but has no endpoint. Give one, or turn translation off.")
    if values.get("translation.enabled") and not model:
        found.append("Translation is on but has no model. Give one, or turn translation off.")
    return found


def translator(
    values: Mapping[str, Any],
    keys: Optional[Keys] = None,
    key: Optional[str] = None,
    timeout: float = 60,
) -> OpenAICompatibleTranslator:
    """The translator these settings describe (raises `TranslationUnavailable` saying why not).

    `key`, when given, is used instead of the saved one (the Settings page trying a key before
    saving it).
    """
    endpoint = str(values.get("translation.endpoint") or "").strip()
    model = str(values.get("translation.model") or "").strip()
    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise TranslationUnavailable("Give the endpoint's address first, such as http://…/v1.")
    if not model:
        raise TranslationUnavailable("Give the model's name first.")
    chosen = (key or "").strip() or (keys or Keys()).get(endpoint)
    return OpenAICompatibleTranslator(endpoint, model, api_key=chosen or None, timeout=timeout)


def workers(values: Mapping[str, Any]) -> int:
    local = is_local_endpoint(str(values.get("translation.endpoint") or ""))
    return LOCAL_WORKERS if local else REMOTE_WORKERS


def check(
    values: Mapping[str, Any], keys: Optional[Keys] = None, key: Optional[str] = None
) -> dict[str, Any]:
    """Send the sample sentence and say what came back: `{ok, sample, translation, seconds}` or
    `{ok: False, message}`. Nothing from the archive is sent."""
    try:
        chosen = translator(values, keys, key, timeout=45)
        chosen.retries = 0  # a person is waiting for the answer
        started = time.monotonic()
        result = chosen.translate(SAMPLE)
    except TranslationError as error:
        return {"ok": False, "message": str(error)}
    endpoint = str(values.get("translation.endpoint") or "")
    return {
        "ok": True,
        "sample": SAMPLE,
        "translation": result.text,
        "seconds": round(time.monotonic() - started, 1),
        "local": is_local_endpoint(endpoint),
        "used_key": bool(chosen.api_key),
    }
