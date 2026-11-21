"""Summaries of mail conversations: the settings, what is sent, and what is kept of the answer.

Only a stand-in endpoint on this computer is ever asked (`stub_server`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest
from stub_server import StubServer

from caixa import settings, summaries
from caixa.box import Box
from caixa.collectors.options import OptionsError
from caixa.summaries import Mail

REMOTE = "https://openrouter.ai/api/v1"


@pytest.fixture
def server() -> Iterator[StubServer]:
    srv = StubServer()
    yield srv
    srv.close()


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box.create(tmp_path / "Box", "Test box")


def _answer(text: str) -> dict[str, Any]:
    return {"choices": [{"message": {"content": text}}]}


def _words(count: int, end: str = ".") -> str:
    return " ".join(f"word{n}" for n in range(count)) + end


# --- Settings -------------------------------------------------------------------------------------


def test_summaries_are_off_until_someone_turns_them_on(box: Box) -> None:
    values = settings.load(box)
    assert values["summaries.enabled"] is False
    assert not summaries.ready(values)


def test_an_empty_endpoint_and_model_are_translations(box: Box, server: StubServer) -> None:
    settings.save(box, {"translation.endpoint": server.endpoint, "translation.model": "llama",
                        "summaries.enabled": True})  # fmt: skip
    values = settings.load(box)
    assert summaries.endpoint(values) == server.endpoint and summaries.model(values) == "llama"
    assert summaries.ready(values)
    settings.save(box, {"summaries.model": "qwen"})
    assert summaries.model(settings.load(box)) == "qwen"


def test_a_service_on_the_internet_needs_an_explicit_yes(box: Box) -> None:
    with pytest.raises(OptionsError) as refused:
        settings.save(box, {"summaries.enabled": True, "summaries.endpoint": REMOTE,
                            "summaries.model": "m"})  # fmt: skip
    assert any("Summaries" in e and "internet" in e for e in refused.value.errors)
    settings.save(box, {"summaries.enabled": True, "summaries.endpoint": REMOTE,
                        "summaries.model": "m", "summaries.allow_remote": True})  # fmt: skip


def test_summaries_on_without_an_endpoint_are_refused_in_words(box: Box) -> None:
    with pytest.raises(OptionsError) as refused:
        settings.save(box, {"summaries.enabled": True})
    assert any("Summaries are on but have no endpoint" in e for e in refused.value.errors)


# --- What is sent ---------------------------------------------------------------------------------


def test_quoted_history_and_signatures_are_left_out() -> None:
    text = summaries.prepare(
        [
            Mail("Ana Costa", "2025-01-15", "Lunch on Thursday?\n\n-- \nAna\nSent from my phone"),
            Mail("Maria Costa", "2025-01-16",
                 "Yes, Thursday works.\n\nOn Wed, 15 Jan 2025, Ana wrote:\n> Lunch on Thursday?"),
        ]  # fmt: skip
    )
    assert "Ana Costa, 2025-01-15: Lunch on Thursday?" in text
    assert "Maria Costa, 2025-01-16: Yes, Thursday works." in text
    assert "Sent from my phone" not in text and text.count("Lunch on Thursday?") == 1


def test_a_long_conversation_keeps_its_first_and_last_mails_within_the_budget() -> None:
    mails = [
        Mail("Ana", f"2025-01-{n + 1:02d}", f"Mail number {n}. " + "x" * 2000) for n in range(30)
    ]
    text = summaries.prepare(mails)
    assert len(text) <= summaries.BUDGET
    assert "Mail number 0." in text and "Mail number 29." in text
    assert "Mail number 15." not in text and "mails left out" in text


# --- The answer -----------------------------------------------------------------------------------


def _client(server: StubServer) -> Any:
    values = {"summaries.endpoint": server.endpoint, "summaries.model": "test-model"}
    return summaries.client(values)


def test_an_answer_of_30_to_50_words_is_kept_as_it_is(server: StubServer) -> None:
    server.reply = _answer("  " + _words(40) + "  ")
    assert summaries.summarize(_client(server), "Ana, 2025-01-15: Lunch?") == _words(40)
    (request,) = server.requests
    system = request["json"]["messages"][0]["content"]
    assert "30" in system and "50" in system and "language" in system
    assert request["json"]["messages"][1]["content"].endswith("Ana, 2025-01-15: Lunch?")


def test_an_answer_too_long_is_asked_once_more_then_cut_at_a_sentence(server: StubServer) -> None:
    long = _words(30) + " " + _words(15) + " " + _words(20)  # sentences of 30, 15 and 20 words
    server.reply = _answer(long)
    summary = summaries.summarize(_client(server), "Ana: Lunch?")
    assert len(server.requests) == 2  # one retry
    assert "between 30 and 50" in server.requests[1]["json"]["messages"][-1]["content"]
    assert summary == _words(30) + " " + _words(15) and len(summary.split()) == 45


def test_a_retry_that_fits_is_kept(server: StubServer) -> None:
    answers = iter([_answer(_words(80)), _answer(_words(35))])
    server.respond = lambda request: next(answers)
    assert summaries.summarize(_client(server), "Ana: Lunch?") == _words(35)


def test_an_answer_without_a_sentence_end_is_cut_at_50_words(server: StubServer) -> None:
    server.reply = _answer(_words(90, end=""))
    assert len(summaries.summarize(_client(server), "x").split()) == 50


def test_the_test_sends_only_the_fixed_conversation(tmp_path: Path, server: StubServer) -> None:
    server.reply = _answer(_words(36))
    values = {"summaries.endpoint": server.endpoint, "summaries.model": "test-model"}
    result = summaries.check(values, summaries.Keys(tmp_path))
    assert result["ok"] and result["summary"] == _words(36) and result["words"] == 36
    sent = server.requests[0]["json"]["messages"][1]["content"]
    assert sent.endswith(summaries.prepare(summaries.SAMPLE))


def test_a_failing_test_says_why(tmp_path: Path, server: StubServer) -> None:
    server.status = 404
    values = {"summaries.endpoint": server.endpoint, "summaries.model": "nope"}
    result = summaries.check(values, summaries.Keys(tmp_path))
    assert result["ok"] is False and "404" in result["message"]
