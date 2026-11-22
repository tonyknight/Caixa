"""A bake-off: Apple Intelligence against an OpenAI-compatible endpoint, on 100 made-up emails.

`caixa benchmark` times the two jobs Caixa gives a model, done exactly as an import does them:

- **summaries**: one per conversation (35 of them), each `summaries.prepare`d (6,000 characters
  for Apple Intelligence, 12,000 for an endpoint) and `summaries.summarize`d (30–50 words, with its
  one retry);
- **translations**: each of the 20 Portuguese emails into English, with Chattr's instruction.

Each side runs at several worker counts (requests at once). Every setting is warmed up first (one
small request per worker, not timed: a model loading, helpers starting), then every item goes
through a pool of that many workers and the whole run is timed. The emails are in
`tools/ai-benchmark/emails.json`: synthetic names only, nothing from a box, so nothing personal is
sent anywhere.

The report (`report.md`, `report.json`) and every summary and translation (`outputs/`) are written
to a folder, so speed and quality can both be compared.
"""

from __future__ import annotations

import json
import os
import platform
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence
from urllib.parse import urlparse

from chattr.translation import OpenAICompatibleTranslator, TranslationError, detect_language

from caixa import apple_intelligence, summaries

#: The made-up emails, beside Chattr in the repository.
EMAILS = Path(__file__).resolve().parents[1] / "tools" / "ai-benchmark" / "emails.json"
TASKS = ("summaries", "translations")
APPLE = "Apple Intelligence"
#: What a warm-up asks (its answer is not used).
WARM_UP = [{"role": "user", "content": "Reply with the single word: ready"}]


def load(path: Optional[Path] = None) -> list[dict[str, Any]]:
    """The conversations, each with its `id`, `language`, `subject` and `mails`."""
    data = json.loads(Path(path or EMAILS).read_text(encoding="utf-8"))
    return list(data["conversations"])


def _items(conversations: list[dict[str, Any]], task: str, budget: int) -> list[dict[str, Any]]:
    """What one task sends: a prepared conversation per summary, a mail's own words per
    translation (Portuguese only, as Caixa translates only what is not in English)."""
    if task == "summaries":
        return [
            {
                "id": c["id"],
                "language": c["language"],
                "title": c["subject"],
                "input": summaries.prepare(
                    [summaries.Mail(m["from"], m["date"], m["text"]) for m in c["mails"]], budget
                ),
            }
            for c in conversations
        ]
    return [
        {
            "id": f"{c['id']}-{n}",
            "language": c["language"],
            "title": c["subject"],
            "input": summaries.own_words(m["text"]),
        }
        for c in conversations
        if c["language"] == "pt"
        for n, m in enumerate(c["mails"], 1)
    ]


def _once(client: Any, task: str, text: str) -> str:
    if task == "summaries":
        return str(summaries.summarize(client, text))
    return str(client.translate(text).text)


def _close(client: Any) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        close()


def _time(
    client: Any, task: str, items: list[dict[str, Any]], workers: int
) -> tuple[float, list[dict[str, Any]]]:
    """Warm up with one request per worker, then run every item through `workers` at once;
    returns the seconds the whole run took and what each item gave."""

    def one(item: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            output, error, declined = _once(client, task, item["input"]), None, False
        except apple_intelligence.Declined as refused:
            output, error, declined = "", str(refused), True
        except (TranslationError, OSError, ValueError) as failed:
            output, error, declined = "", str(failed), False
        return {**item, "output": output, "error": error, "declined": declined,
                "seconds": round(time.perf_counter() - started, 3)}  # fmt: skip

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda _: client.chat(WARM_UP), range(workers)))  # (raises when it is down)
        started = time.perf_counter()
        results = list(pool.map(one, items))
    return time.perf_counter() - started, results


def _row(provider: str, label: str, workers: int, task: str, items: list[dict[str, Any]],
         seconds: float, results: list[dict[str, Any]], error: Optional[str] = None) -> dict[str, Any]:  # fmt: skip
    done = [r for r in results if not r["error"]]
    declined = sum(1 for r in results if r["declined"])
    row: dict[str, Any] = {
        "provider": provider,
        "label": label,
        "workers": workers,
        "task": task,
        "items": len(items),
        "done": len(done),
        "failed": len(items) - len(done) - declined,
        "declined": declined,
        "seconds": round(seconds, 4),
        "per_item": round(seconds / len(done), 4) if done else None,
        "per_second": round(len(done) / seconds, 3) if done and seconds else None,
        "slowest": max((r["seconds"] for r in done), default=None),
        "errors": sorted(
            {r["error"] for r in results if r["error"]} | ({error} if error else set())
        )[:3],
    }
    if task == "summaries":
        words = [len(r["output"].split()) for r in done]
        row["words"] = round(sum(words) / len(words)) if words else None
        portuguese = [r for r in done if r["language"] == "pt"]
        row["portuguese_kept"] = sum(1 for r in portuguese if detect_language(r["output"]) == "pt")
        row["portuguese"] = sum(1 for i in items if i["language"] == "pt")
    return row


def _line(row: dict[str, Any]) -> str:
    head = f"{row['label'][:28]:<28} {row['workers']:>2} at once  {row['task']:<12}"
    if not row["done"]:
        return f"{head} nothing done: {row['errors'][0] if row['errors'] else 'failed'}"
    tail = f" ({row['per_item']:.2f} s each, {row['per_second']:.2f} a second)"
    extra = f", {row['declined']} declined" if row["declined"] else ""
    extra += f", {row['failed']} failed" if row["failed"] else ""
    return f"{head} {row['done']}/{row['items']} in {row['seconds']:.1f} s{tail}{extra}"


def _verdict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per task: each side's best setting (the most items a second, everything done), and how
    much faster the faster side was."""
    found: dict[str, Any] = {}
    for task in TASKS:
        best: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row["task"] != task or not row["per_second"]:
                continue
            key = row["provider"]
            mine = (row["done"] == row["items"], row["per_second"])
            if key not in best or mine > (
                best[key]["done"] == best[key]["items"],
                best[key]["per_second"],
            ):
                best[key] = row
        if not best:
            continue
        ranked = sorted(best.values(), key=lambda r: r["per_second"], reverse=True)
        top = ranked[0]
        entry: dict[str, Any] = {"fastest": f"{top['label']} ({top['workers']} at once)",
                                 "per_second": top["per_second"]}  # fmt: skip
        if len(ranked) > 1:
            other = ranked[1]
            entry["slower"] = f"{other['label']} ({other['workers']} at once)"
            entry["times_faster"] = round(top["per_second"] / other["per_second"], 2)
        found[task] = entry
    return found


def _report(settings: dict[str, Any], rows: list[dict[str, Any]], verdict: dict[str, Any]) -> str:
    lines = [
        "# AI benchmark: Apple Intelligence against an endpoint",
        "",
        f"Run {settings['when']} on {settings['machine']} ({settings['processors']} processors).",
        f"Emails: {settings['emails']} ({settings['conversations']} conversations; "
        f"{settings['portuguese']} emails in Portuguese).",
        "",
    ]
    for task in TASKS:
        mine = [r for r in rows if r["task"] == task]
        if not mine:
            continue
        lines += [f"## {task.capitalize()}", ""]
        if task == "summaries":
            lines.append(
                "| Who | At once | Done | Seconds | Each (s) | A second | Slowest (s) | Words | Portuguese kept | Problems |"
            )
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
        else:
            lines.append(
                "| Who | At once | Done | Seconds | Each (s) | A second | Slowest (s) | Problems |"
            )
            lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
        for r in mine:
            problems = "; ".join(
                [*([f"{r['declined']} declined"] if r["declined"] else []),
                 *([f"{r['failed']} failed"] if r["failed"] else []),
                 *r["errors"][:1]]
            ) or "none"  # fmt: skip
            cells = [r["label"], str(r["workers"]), f"{r['done']}/{r['items']}", f"{r['seconds']:.1f}",
                     "–" if r["per_item"] is None else f"{r['per_item']:.2f}",
                     "–" if r["per_second"] is None else f"{r['per_second']:.2f}",
                     "–" if r["slowest"] is None else f"{r['slowest']:.2f}"]  # fmt: skip
            if task == "summaries":
                cells += ["–" if r["words"] is None else str(r["words"]),
                          f"{r['portuguese_kept']} of {r['portuguese']}"]  # fmt: skip
            lines.append("| " + " | ".join(cells + [problems.replace("|", "/")]) + " |")
        said = verdict.get(task)
        if said:
            line = f"**Faster:** {said['fastest']}"
            if "slower" in said:
                line += f", {said['times_faster']}× as many {task} a second as {said['slower']}."
            lines += ["", line]
        lines.append("")
    lines += [
        "## Reading it",
        "",
        "- *A second*: items finished per second over the whole run (higher is faster). *Each*: the",
        "  run's time divided by the items done. *Slowest*: the longest single item.",
        "- Summaries should be 30–50 words; *Portuguese kept* counts the Portuguese conversations",
        "  whose summary is in Portuguese, as it should be.",
        "- Every summary and translation is in `outputs/`, to compare their quality as well.",
        "",
    ]
    return "\n".join(lines)


def run(
    *,
    endpoint: Optional[str],
    model: Optional[str],
    api_key: Optional[str],
    apple_workers: Sequence[int] = (1, 2, 4, 8),
    endpoint_workers: Sequence[int] = (1, 2, 4),
    only: Optional[str] = None,
    tasks: Iterable[str] = TASKS,
    emails: Optional[Path] = None,
    out: Path,
    say: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run the bake-off and write its report to `out`; returns the report as data."""
    conversations = load(emails)
    chosen = [t for t in TASKS if t in set(tasks)]
    out = Path(out)
    (out / "outputs").mkdir(parents=True, exist_ok=True)
    sides: list[tuple[str, str, Sequence[int]]] = []
    if only in (None, "apple"):
        sides.append(("apple", APPLE, apple_workers))
    if only in (None, "endpoint"):
        if not endpoint or not model:
            raise ValueError("Give the endpoint's address and the model's name (or only apple).")
        sides.append(("endpoint", f"{model} ({urlparse(endpoint).netloc})", endpoint_workers))
    rows: list[dict[str, Any]] = []
    for provider, label, counts in sides:
        if provider == "apple":
            ready = apple_intelligence.check()
            if not ready["ready"]:
                say(f"{APPLE}: left out. {ready['message']}")
                continue
        for workers in counts:
            for task in chosen:
                budget = summaries.APPLE_BUDGET if provider == "apple" else summaries.BUDGET
                items = _items(conversations, task, budget)
                if provider == "apple":
                    client: Any = apple_intelligence.AppleIntelligence(workers)
                else:
                    client = OpenAICompatibleTranslator(endpoint or "", model or "", api_key=api_key or None, timeout=300)  # fmt: skip
                    client.retries = 0
                    client.server_name = "endpoint"
                try:
                    seconds, results = _time(client, task, items, workers)
                    row = _row(provider, label, workers, task, items, seconds, results)
                except (TranslationError, OSError) as down:  # the warm-up failed: nothing to time
                    results = [{**i, "output": "", "error": str(down), "declined": False, "seconds": 0.0} for i in items]  # fmt: skip
                    row = _row(provider, label, workers, task, items, 0.0, results, str(down))
                finally:
                    _close(client)
                rows.append(row)
                say(_line(row))
                (out / "outputs" / f"{provider}-{workers}-{task}.json").write_text(
                    json.dumps([{k: r[k] for k in ("id", "language", "title", "output", "seconds", "error")} for r in results],
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                )  # fmt: skip
    verdict = _verdict(rows)
    settings = {
        "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "machine": f"{platform.system()} {platform.release()} {platform.machine()}",
        "processors": os.cpu_count(),
        "emails": sum(len(c["mails"]) for c in conversations),
        "conversations": len(conversations),
        "portuguese": sum(len(c["mails"]) for c in conversations if c["language"] == "pt"),
        "endpoint": endpoint if only != "apple" else None,
        "model": model if only != "apple" else None,
        "apple_workers": list(apple_workers),
        "endpoint_workers": list(endpoint_workers),
        "tasks": chosen,
    }
    report = {"settings": settings, "results": rows, "verdict": verdict}
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "report.md").write_text(_report(settings, rows, verdict), encoding="utf-8")
    for task, said in verdict.items():
        line = f"Faster at {task}: {said['fastest']}"
        if "slower" in said:
            line += f", {said['times_faster']}× {said['slower']}"
        say(line)
    return report
