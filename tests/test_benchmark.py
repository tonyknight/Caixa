"""`caixa benchmark`: Apple Intelligence against an endpoint, on 100 made-up emails.

Only stand-ins are asked here: `stand_in_apple.py` for the helper, `stub_server` for the endpoint.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import Any, Iterator

import pytest
from stub_server import StubServer

from caixa import apple_intelligence, benchmark, cli

STAND_IN = Path(__file__).with_name("stand_in_apple.py")


@pytest.fixture
def apple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        apple_intelligence.OVERRIDE, f"{shlex.quote(sys.executable)} {shlex.quote(str(STAND_IN))}"
    )


@pytest.fixture
def server() -> Iterator[StubServer]:
    made = StubServer()

    def answer(request: dict[str, Any]) -> dict[str, Any]:
        system = request["messages"][0]["content"]
        if "summarize" in system.lower():
            words = (
                "Ana and Maria plan the family weekend and agree on dates, food and who pays." * 3
            )
            return {"choices": [{"message": {"content": " ".join(words.split()[:40])}}]}
        return {"choices": [{"message": {"content": "This is the translation of the message."}}]}

    made.respond = answer
    yield made
    made.close()


def test_the_emails_are_100_in_about_35_conversations_20_in_portuguese() -> None:
    conversations = benchmark.load()
    mails = [m for c in conversations for m in c["mails"]]
    portuguese = [c for c in conversations if c["language"] == "pt"]
    assert len(mails) == 100 and len(conversations) == 35
    assert len(portuguese) == 7 and sum(len(c["mails"]) for c in portuguese) == 20
    assert {len(c["mails"]) for c in conversations} == {1, 2, 3, 4, 5, 6}


def test_a_run_times_both_sides_and_writes_the_report(
    apple: None, server: StubServer, tmp_path: Path
) -> None:
    said: list[str] = []
    report = benchmark.run(
        endpoint=server.endpoint, model="local-model", api_key="sk-local",
        apple_workers=[1, 2], endpoint_workers=[1, 2], out=tmp_path / "out", say=said.append,
    )  # fmt: skip
    rows = report["results"]
    assert {(r["provider"], r["workers"], r["task"]) for r in rows} == {
        (p, w, t)
        for p in ("apple", "endpoint")
        for w in (1, 2)
        for t in ("summaries", "translations")
    }
    for row in rows:
        expected = 35 if row["task"] == "summaries" else 20
        assert row["items"] == expected and row["done"] == expected and row["failed"] == 0
        assert row["seconds"] > 0 and row["per_item"] > 0 and row["per_second"] > 0
    endpoint_summaries = [
        r for r in rows if r["provider"] == "endpoint" and r["task"] == "summaries"
    ]
    assert all(r["words"] == 40 for r in endpoint_summaries)
    # the key went to the endpoint as a bearer token
    assert all(q["headers"].get("Authorization") == "Bearer sk-local" for q in server.requests)
    out = tmp_path / "out"
    assert "Faster" in (out / "report.md").read_text(encoding="utf-8")
    assert json.loads((out / "report.json").read_text())["verdict"]["summaries"]["fastest"]
    outputs = json.loads((out / "outputs" / "endpoint-2-translations.json").read_text())
    assert len(outputs) == 20 and outputs[0]["output"] == "This is the translation of the message."
    assert any("summaries" in line for line in said)


def test_one_side_can_be_left_out(server: StubServer, tmp_path: Path) -> None:
    report = benchmark.run(
        endpoint=server.endpoint, model="m", api_key=None, apple_workers=[4], endpoint_workers=[1],
        only="endpoint", tasks=("translations",), out=tmp_path / "out", say=lambda line: None,
    )  # fmt: skip
    assert [(r["provider"], r["task"]) for r in report["results"]] == [("endpoint", "translations")]
    assert all("Authorization" not in q["headers"] for q in server.requests)


def test_a_failing_endpoint_is_reported_not_fatal(apple: None, tmp_path: Path) -> None:
    report = benchmark.run(
        endpoint="http://127.0.0.1:9/v1", model="m", api_key=None, apple_workers=[2],
        endpoint_workers=[1], tasks=("translations",), out=tmp_path / "out", say=lambda line: None,
    )  # fmt: skip
    (endpoint,) = [r for r in report["results"] if r["provider"] == "endpoint"]
    assert endpoint["failed"] == 20 and endpoint["errors"]
    (mac,) = [r for r in report["results"] if r["provider"] == "apple"]
    assert mac["done"] == 20
    assert report["verdict"]["translations"]["fastest"].startswith("Apple Intelligence")


def test_the_command_line(
    apple: None,
    server: StubServer,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAIXA_BENCHMARK_API_KEY", "sk-env")
    code = cli.main([
        "benchmark", "--endpoint", server.endpoint, "--model", "local-model",
        "--apple-workers", "2", "--endpoint-workers", "1", "--tasks", "translations",
        "--out", str(tmp_path / "out"),
    ])  # fmt: skip
    assert code == 0
    printed = capsys.readouterr().out
    assert "Apple Intelligence" in printed and "local-model" in printed and "report.md" in printed
    assert server.requests and server.requests[0]["headers"]["Authorization"] == "Bearer sk-env"
