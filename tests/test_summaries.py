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


# --- The stage after an import, the job, and the page (T02) ---------------------------------------

import re  # noqa: E402
import shutil  # noqa: E402

from fixtures import family  # noqa: E402
from fixtures.builders.noisy_mbox import MAILBOX_NAME, NoisyMail  # noqa: E402

from caixa.service import Service  # noqa: E402


def _summary_for(request: dict[str, Any]) -> dict[str, Any]:
    """A stand-in model: 35 words naming the conversation's first sender."""
    conversation = request["messages"][1]["content"].split("\n\n", 1)[1]
    sender = conversation.split(",", 1)[0]
    return _answer(f"A conversation begun by {sender}. " + _words(35 - 4 - len(sender.split())))


@pytest.fixture
def service(tmp_path: Path, noisy_mail: NoisyMail) -> Iterator[Service]:
    made = Service(roots=[tmp_path])
    made.box_create(str(tmp_path / "Box"), name="Our box", owner=family.OWNER.name)
    with Box.open(tmp_path / "Box").master() as master:
        for person in (family.JOAO, family.RUI):
            master.add_alias(master.add_person(person.name), person.emails[0], "email")
        master.commit()
    yield made
    made.close()


def _source(service: Service, tmp_path: Path, noisy_mail: NoisyMail) -> int:
    folder = tmp_path / "exports"
    folder.mkdir(exist_ok=True)
    mbox = shutil.copy(noisy_mail.gmail, folder / MAILBOX_NAME)
    read = service.wait(
        service.call("mail.read", {"source": str(mbox), "account": "Gmail"})["id"], timeout=60
    )
    source = int(read["result"]["sources"][0]["source_id"])
    service.call("mail.choose", {"source": source, "addresses": ["beatriz.lima@example.net"]})
    return source


def _import(service: Service, source: int) -> dict[str, Any]:
    done = service.wait(service.call("mail.import", {"source": source})["id"], timeout=120)
    assert done["status"] == "done", done["error"]
    return done


def _threads(service: Service) -> list[tuple[Any, ...]]:
    box = Box.open(service.call("box.status")["root"])
    with box.master() as master:
        return master.connection.execute(
            "SELECT subject, summary, summary_model, summary_at, summary_hash FROM mail_threads "
            "ORDER BY subject"
        ).fetchall()


def _beatriz(service: Service) -> str:
    root = Path(service.call("box.status")["root"])
    return (root / "People" / "Beatriz Lima" / "Beatriz Lima.html").read_text(encoding="utf-8")


def _turn_on(service: Service, server: StubServer) -> None:
    service.call("settings.set", {"values": {"summaries.enabled": True,
                                             "summaries.endpoint": server.endpoint,
                                             "summaries.model": "test-model"}})  # fmt: skip


def test_an_import_summarizes_each_conversation_and_the_page_shows_it(
    service: Service, server: StubServer, tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    server.respond = _summary_for
    _turn_on(service, server)
    done = _import(service, _source(service, tmp_path, noisy_mail))
    threads = _threads(service)
    assert len(threads) == 6 and len(server.requests) == 6
    assert all(t[1] and t[2] == "test-model" and t[3] and t[4] for t in threads)
    assert done["result"]["summaries"]["written"] == 6
    page = _beatriz(service)
    assert "A conversation begun by Beatriz Lima." in page
    assert "Summary written by test-model" in page


def test_a_stopped_run_resumes_and_only_changed_conversations_are_redone(
    service: Service, server: StubServer, tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    from caixa.collectors.base import Progress

    _import(service, _source(service, tmp_path, noisy_mail))  # summaries off: none yet
    assert all(t[1] is None for t in _threads(service))
    server.respond = _summary_for
    values = {"summaries.enabled": True, "summaries.endpoint": server.endpoint,
              "summaries.model": "test-model"}  # fmt: skip
    box = Box.open(service.call("box.status")["root"])

    class Stop(Exception):
        pass

    def stop_after_two(step: Progress) -> None:
        if step.stage == "summarizing" and step.current >= 2:
            raise Stop()

    with pytest.raises(Stop):
        summaries.run(box, values, stop_after_two, summaries.Keys(tmp_path))
    written = sum(1 for t in _threads(service) if t[1])
    assert 2 <= written < 6
    asked = len(server.requests)
    result = summaries.run(box, values, lambda step: None, summaries.Keys(tmp_path))
    assert result["written"] == 6 - written and len(server.requests) - asked == 6 - written
    # a conversation that gains a mail is summarized again; the others are not
    with box.master() as master:
        master.connection.execute(
            "UPDATE mail_threads SET summary_hash = 'before' WHERE subject = 'Book club in March'"
        )
        master.commit()
    asked = len(server.requests)
    assert summaries.run(box, values, lambda step: None, summaries.Keys(tmp_path))["written"] == 1
    assert len(server.requests) - asked == 1


def test_a_conversations_hash_changes_when_it_gains_a_mail() -> None:
    assert summaries.mails_hash(["mail:a", "mail:b"]) == summaries.mails_hash(["mail:b", "mail:a"])
    assert summaries.mails_hash(["mail:a", "mail:b"]) != summaries.mails_hash(
        ["mail:a", "mail:b", "mail:c"]
    )


def test_without_a_model_the_import_completes_and_summaries_come_later(
    service: Service, server: StubServer, tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    _import(service, _source(service, tmp_path, noisy_mail))
    page = _beatriz(service)
    assert "Summary written by" not in page
    assert "Hi Maria, we meet on the 9th. Beatriz" in page  # the opening words
    server.respond = _summary_for
    _turn_on(service, server)
    job = service.call("mail.summarize", {})
    assert job["kind"] == "mail-summarize"
    done = service.wait(job["id"], timeout=120)
    assert done["status"] == "done", done["error"]
    assert done["result"]["written"] == 6
    assert "Summary written by test-model" in _beatriz(service)


def test_an_endpoint_that_fails_does_not_fail_the_import(
    service: Service, server: StubServer, tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    server.status = 500
    _turn_on(service, server)
    done = _import(service, _source(service, tmp_path, noisy_mail))
    assert done["result"]["summaries"]["written"] == 0
    assert any("ummar" in w for w in done["result"]["warnings"])
    assert all(t[1] is None for t in _threads(service))
    assert re.search(r"Hi Maria, we meet on the 9th", _beatriz(service))


# --- Summarize, or not, for each import, and why none were written (hot fix 18) -------------------


def _import_with(service: Service, source: int, **switches: bool) -> dict[str, Any]:
    done = service.wait(
        service.call("mail.import", {"source": source, **switches})["id"], timeout=120
    )
    assert done["status"] == "done", done["error"]
    return done


def test_an_import_with_summarize_off_writes_none_and_says_so(
    service: Service, server: StubServer, tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    server.respond = _summary_for
    _turn_on(service, server)
    done = _import_with(service, _source(service, tmp_path, noisy_mail), summarize=False)
    assert server.requests == [] and done["result"]["summaries"]["reason"] == "off_for_job"
    assert done["options"]["summarize"] is False


def test_an_import_says_summaries_are_off_in_settings(
    service: Service, tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    done = _import_with(service, _source(service, tmp_path, noisy_mail))
    assert done["result"]["summaries"]["written"] == 0
    assert done["result"]["summaries"]["reason"] == "off"


def test_a_failing_endpoint_is_the_reason(
    service: Service, server: StubServer, tmp_path: Path, noisy_mail: NoisyMail
) -> None:
    server.status = 500
    _turn_on(service, server)
    done = _import_with(service, _source(service, tmp_path, noisy_mail))
    assert done["result"]["summaries"]["reason"] == "failed"


# --- Apple Intelligence (hot fix 20) --------------------------------------------------------------

import shlex  # noqa: E402
import sys  # noqa: E402

from caixa import apple_intelligence  # noqa: E402

STAND_IN = Path(__file__).with_name("stand_in_apple.py")


@pytest.fixture
def apple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        apple_intelligence.OVERRIDE, f"{shlex.quote(sys.executable)} {shlex.quote(str(STAND_IN))}"
    )


def test_apple_intelligence_needs_no_endpoint(box: Box, apple: None) -> None:
    settings.save(box, {"summaries.enabled": True, "summaries.provider": "apple"})
    values = settings.load(box)
    assert summaries.ready(values) and summaries.model(values) == "Apple Intelligence"


def test_an_import_is_summarized_by_apple_intelligence(
    service: Service,
    apple: None,
    tmp_path: Path,
    noisy_mail: NoisyMail,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "STAND_IN_APPLE_DECLINE", "Lovely, thank you"
    )  # Beatriz's second book club mail
    service.call(
        "settings.set", {"values": {"summaries.enabled": True, "summaries.provider": "apple"}}
    )
    done = _import(service, _source(service, tmp_path, noisy_mail))
    said = done["result"]["summaries"]
    assert said["declined"] == 1 and said["written"] == 5 and said["model"] == "Apple Intelligence"
    threads = {t[0]: t for t in _threads(service)}
    assert threads["Book club in March"][1] is None  # declined: its entry keeps the opening words
    assert threads["Book club in April"][2] == "Apple Intelligence"
    assert any("declined" in w for w in done["result"]["warnings"])


def test_apple_intelligence_is_sent_at_most_6000_characters() -> None:
    mails = [
        Mail("Ana", f"2025-01-{n + 1:02d}", f"Mail number {n}. " + "x" * 2000) for n in range(30)
    ]
    text = summaries.prepare(mails, budget=summaries.APPLE_BUDGET)
    assert len(text) <= 6000 and "Mail number 0." in text and "Mail number 29." in text


def test_the_test_works_with_apple_intelligence(tmp_path: Path, apple: None) -> None:
    result = summaries.check(
        {"summaries.provider": "apple", "workers": 2}, summaries.Keys(tmp_path)
    )
    assert result["ok"] and result["words"] <= 50


def test_settings_say_when_apple_intelligence_cannot_be_chosen(
    service: Service, apple: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = service.call("settings.get")
    assert "x-unavailable" not in ready["schema"]["properties"]["summaries.provider"]
    assert service.call("apple.check")["ready"] is True
    monkeypatch.setenv("STAND_IN_APPLE", "not_enabled")
    blocked = service.call("settings.get")["schema"]["properties"]
    for name in ("summaries.provider", "translation.provider"):
        assert "turned off" in blocked[name]["x-unavailable"]["apple"]
