---
id: 20261122-05-ai-benchmark
title: AI benchmark
type: feature
priority: medium
status: done
created: 2026-11-22
updated: 2026-11-22
closed: 2026-11-22
notes: 'Done: caixa benchmark and 100 made-up emails in tools/ai-benchmark.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

The maintainer wants to know whether Apple Intelligence is worth using: a bake-off against their own local model (oMLX, an OpenAI-compatible endpoint with an API key), timing summaries and translations on 100 made-up emails, run on their Mac with a `caixa` command.

## Acceptance criteria

- [x] `tools/ai-benchmark/` holds 100 made-up emails (synthetic family names only) in about 35 conversations of 1 to 6 mails; 20 emails (7 conversations) in Portuguese, the rest in English; and a README
- [x] `caixa benchmark` times summaries (one per conversation, as an import makes them) and translations (the 20 Portuguese emails into English) through Apple Intelligence at 1, 2, 4 and 8 helpers and through an endpoint (`--endpoint`, `--model`, a key by `--api-key`, `CAIXA_BENCHMARK_API_KEY` or `--ask-key`) at 1, 2 and 4 requests at once; both lists can be changed, and either side left out
- [x] Each setting is warmed up before it is timed; the report gives the time, per item and per second, failures and refusals, summary length and whether Portuguese conversations were summarized in Portuguese, and says which is faster and by how much
- [x] The report (Markdown and JSON) and every summary and translation are written to a folder, so quality can be compared too

## Context

Asked for on 2026-11-22; questions answered: about 35 conversations; translate the 20 Portuguese; sweep both sides' workers; name `ai-benchmark` / `caixa benchmark`. Uses `caixa.summaries` (prepare, summarize, budgets) and `caixa.apple_intelligence`, and Chattr's endpoint client, exactly as an import does. Requirements: *Hot fixes*, Apple Intelligence; M19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:**

- **The emails** (`tools/ai-benchmark/emails.json`): 35 conversations, each with an id, its
  language, subject and mails (sender, date, text); 100 mails, 20 of them in 7 Portuguese
  conversations. Synthetic family names and `example.*` addresses only. Some mails quote earlier
  ones and carry signatures, and a few conversations are long, so `prepare` does its real work.
- **`caixa/benchmark.py`:** for each provider and worker count: warm up (one request per worker,
  not timed), then run every item through a pool of that many workers and time the whole run and
  each item. Summaries: `summaries.prepare(mails, budget)` (6,000 characters for Apple, 12,000 for
  an endpoint) then `summaries.summarize` (with its one retry), as an import does. Translations:
  each Portuguese email's own words through `translate` (Chattr's instruction). Results: seconds,
  per item, items per second, failures, refusals, average words, and Portuguese conversations
  summarized in Portuguese (`detect_language`).
- **`caixa benchmark`:** `--endpoint URL --model NAME` (key: `--api-key`, else
  `CAIXA_BENCHMARK_API_KEY`, else `--ask-key` asks without echoing, else none);
  `--apple-workers 1,2,4,8`, `--endpoint-workers 1,2,4`; `--only apple|endpoint`;
  `--tasks summaries,translations`; `--emails FILE` (default: the tool's own); `--out FOLDER`
  (default `ai-benchmark-<date-time>` in the current folder). Prints the table as it goes and the
  verdict at the end; writes `report.md`, `report.json` and `outputs/<provider>-<workers>-<task>.json`.
- **README** (`tools/ai-benchmark/README.md`): what it measures, how to run it on the Mac with
  oMLX, how to read the report.

### T01: The emails, the benchmark and the command

- `tools/ai-benchmark/{emails.json,README.md}`, `caixa/benchmark.py`, `caixa/cli.py`.
- Tests (`tests/test_benchmark.py`, a stand-in helper and a stand-in endpoint only): the emails
  are 100 in about 35 conversations, 20 Portuguese in 7; a run over both sides with two worker
  counts times every item, writes the report and the outputs, and names the faster; the key goes
  to the endpoint as a bearer token; `--only` leaves a side out; a failing endpoint is reported,
  not fatal.
- Verify: `python -m pytest -q tests/test_benchmark.py && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `caixa benchmark` times summaries (35 conversations) and translations (20 Portuguese emails) of 100 made-up emails through Apple Intelligence (1, 2, 4, 8 helpers) and through an OpenAI-compatible endpoint with a key (1, 2, 4 requests at once), warming each setting up first, and writes a report with speed, failures and refusals, summary length and language, the faster side and by how much, plus every output for judging quality.
- **Files:** `caixa/benchmark.py`, `caixa/cli.py`, `tools/ai-benchmark/{emails.json,README.md}`, the Requirements; tests `tests/test_benchmark.py`.
- **Errors:** seconds rounded to two decimals read as 0 for the stand-in's fast runs (now four).
- **Verify:** `python -m pytest -q` 1474 passed, 1 skipped; black and mypy clean.

## Review

2026-11-22, in-session. **Verdict: clean (minors only).**

- Minor: run only against stand-ins here; the real numbers come from the maintainer's Mac.
- Minor: the default sweep is 14 runs and can take a long time with a slow local model; the README says how to narrow it.

## Notes

Append-only running log. Each entry dated.

### 2026-11-22
T01: tools/ai-benchmark/emails.json (100 made-up emails, 35 conversations of 1-6; 7 Portuguese conversations with 20 emails; quotes and signatures in some), README.md. caixa/benchmark.py: per provider and worker count, a warm-up (one request per worker, untimed), then every item through a pool; summaries via summaries.prepare (6,000 / 12,000) and summarize; translations of the Portuguese emails' own words via translate; rows with seconds, per item, a second, slowest, words, Portuguese kept, declined/failed and errors; a failing warm-up marks the run failed rather than timing out item by item; verdict per task (each side's best, times faster); report.md, report.json, outputs/. caixa benchmark (--endpoint, --model, --api-key / CAIXA_BENCHMARK_API_KEY / --ask-key, --apple-workers, --endpoint-workers, --only, --tasks, --emails, --out). RED (module missing), then 5 GREEN; full pytest 1474 passed.
