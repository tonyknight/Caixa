---
id: 20261120-12-local-summaries
title: Local summaries
type: feature
priority: medium
status: done
created: 2026-11-20
updated: 2026-11-21
closed: 2026-11-21
notes: 'Done: summaries after import and on demand, 30-50 words, shown on entries
  with the model''s name.'
parent:
depends_on:
- 20261120-09-import-the-chosen-conversations
- 20261120-11-the-person-page-s-entry-and-the-overlay
subtasks: []
plan_status: done
---
## Description

Local summaries of each conversation (30–50 words, in its own language), written after the
import by an OpenAI-compatible endpoint.

## Acceptance criteria

- [x] Settings → Summaries: on/off, endpoint (translation's by default), model, allow a service on the internet, Test with a fixed synthetic conversation
- [x] Quoted history and signatures removed; long conversations within a size budget
- [x] Answers checked for 30–50 words (one retry, then cut at a sentence); stored in `mail_threads` with model and date; the entry says it was written by a model
- [x] A job stage with progress that resumes after a cancel and redoes only conversations that gained mails
- [x] Without an endpoint the import completes and entries show the opening words; summaries are added later
- [x] Tests use a stand-in endpoint only

## Context

Phase 1.5 - Mbox Tasks Breakdown item 12. See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`. Requirements: *Key flows* (Summaries), *Components* (Summaries); M12, N1. Reuse `caixa/translation.py` and `chattr/translation.py` client code and the allow-remote rule.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `caixa/summaries.py` does for summaries what `caixa/translation.py` does for
translation, through the same client (Chattr's OpenAI-compatible client gains a plain `chat`
call, which `translate` now uses) and the same "a service on the internet needs a second yes" rule.

- **Settings → Summaries:** `summaries.enabled` (off by default), `summaries.endpoint` and
  `summaries.model` (empty: translation's), `summaries.allow_remote`. The key is translation's,
  sent only to the host it was saved for. Test sends a fixed synthetic conversation (nothing from
  the box) and shows the summary.
- **What is sent:** the conversation's mails in date order, each as "sender, date: text", with
  quoted history (from a `>` line or "On … wrote:") and signatures (from a `-- ` line) removed,
  within 12,000 characters (when longer: the first mails and the last, with a line saying how many
  were left out). Asked for 30–50 words in the conversation's own language, using only what the
  mails say.
- **The answer:** words counted; outside 30–50 one retry saying so; still too long, cut at the
  last sentence end within 50 words (or at 50 words); too short is kept.
- **Stored** in `mail_threads` (`summary`, `summary_model`, `summary_at`, `summary_hash`: a hash of
  the conversation's mail ids). A conversation is summarized when it has no summary or its hash
  changed (it gained mails); each summary is committed as it is made, so a cancelled run resumes
  where it stopped.
- **The stage:** the mail import runs it after recording the mail when summaries are on and
  configured (progress "Summarizing conversations", n of N), then redraws the pages; an endpoint
  that fails or is missing never fails the import (a warning says so). `mail.summarize` starts the
  same work later as a job of its own (`mail-summarize`).
- **The page:** Chattr's publish takes `summaries` (thread → summary and model) from the master, so
  every redraw has them; the entry shows the summary and "Summary written by <model>", or the
  opening words when there is none.

### T01: The client, the settings and the summarizer

- `tools/chattr/src/chattr/translation.py` (`chat`), `caixa/summaries.py`, `caixa/settings.py`,
  `caixa/service.py` (`summaries.test`), `tools/chattr/tests/stub_server.py` (an answer per request).
- Tests (`tests/test_summaries.py`, stand-in endpoint only): off by default; a service on the
  internet needs the second yes; empty endpoint and model fall back to translation's; quotes and
  signatures removed, long conversations within the budget (first and last); 30–50 words kept, one
  retry, then cut at a sentence; Test sends only the fixed conversation.
- Verify: `python -m pytest -q tests/test_summaries.py tests/test_translation.py tools/chattr/tests/test_translation_client.py`
- [x] done

### T02: The stage, the job and the page

- `caixa/summaries.py` (`run`), `caixa/service.py` (the import's stage, `mail.summarize`,
  `mail-summarize`), `caixa/collectors/chattr.py` (summaries to publish),
  `tools/chattr/src/chattr/{commands.py,pages.py}`, `templates/page.html`.
- Tests: an import with summaries on stores each conversation's summary, model and date, and the
  person page shows it marked as written by the model; a cancelled run resumes without redoing what
  was done; a conversation that gains mails is redone, the others not; with no endpoint or a
  failing one the import completes, entries show the opening words, and `mail.summarize` adds them
  later.
- Verify: `python -m pytest -q tests/test_summaries.py tests/test_mail_pages.py tests/test_mail_service.py`
- [x] done

### T03: Settings page and job names

- `web/src/client/pages/SettingsPage.tsx` (the Summaries group and its Test), `api.ts`,
  `locales.ts` (en, zh), the Jobs page and toasts (`mail-summarize`), the built window.
- Tests (`web/tests`): the Summaries group renders, Test shows the summary or the error; the job
  is named.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src && (cd web && pnpm exec tsc --noEmit && pnpm exec vitest run)`
- [x] done

## Completion report

- **Outcome:** Each imported mail conversation gets a 30–50-word summary in its own language from the endpoint and model in Settings → Summaries (translation's when left empty; a service on the internet needs its own yes). What is sent leaves out quoted earlier mail and signatures and stays within 12,000 characters (the first and last mails when longer). The answer is held to 30–50 words (one retry, then cut at a sentence) and stored in `mail_threads` with its model, date and the hash of its mails. The mail import summarizes after recording (progress shown; a failure or a cancel is a warning, never a failed import) and redraws the pages; `mail.summarize` (Summarize mail now) does it later, resuming where a run stopped and redoing only conversations that gained mails. The person page's entry shows the summary with "Summary written by <model>", or the opening words until there is one.
- **Files:** `caixa/summaries.py` (new), `caixa/settings.py`, `caixa/service.py`, `caixa/collectors/chattr.py`, `tools/chattr/src/chattr/{translation.py,commands.py,pages.py}`, `tools/chattr/src/chattr/templates/{page.html,base.html}`, `web/src/client/{api.ts,locales.ts,Toasts.tsx}`, `web/src/client/pages/{SettingsPage,JobsPage}.tsx`, `caixa/data/web/*`; tests `tests/test_summaries.py` (new), `tests/test_worker_protocol.py`, `tools/chattr/tests/stub_server.py`, `web/tests/{settings-page,jobs-page}.test.tsx`, `web/tests/fake-api.ts`, `web/tests/e2e-translation.test.ts`.
- **Errors:** black could not format a `# fmt: skip` inside a split string (rewritten plainly); mypy: `Collector` has no `refresh` (the pages are redrawn through `_refresh_all`); the translation e2e test's label lookup became ambiguous (made exact).
- **Verify:** `python -m pytest -q` 1428 passed, 1 skipped; black and mypy clean (77 files); web `tsc` clean, vitest 253 passed (after the e2e fix).

## Review

2026-11-21, in-session. **Verdict: clean (minors only).**

- Minor: the API key is translation's and is sent only to the host it was saved for, so a summaries endpoint on another paid host has no key (a model on this computer, or the translation service, needs none extra).
- Minor: redrawing the pages after summarizing records itself as an import that changed nothing, as every redraw does.
- Minor: whether a summary is in the conversation's language rests on the model; the stand-in endpoint cannot show it. Check on the first real mbox.
- Minor: the Jobs page and toast tests were written after their code.
- Spec: files touched match the plan; all acceptance criteria met.

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: Chattr's client gains chat(messages) (translate uses it) and a server_name for its errors. caixa/summaries.py: settings (summaries.enabled/endpoint/model/allow_remote; empty endpoint and model are translation's, whose yes covers its own endpoint), problems() joined to settings.save, prepare() (a line per mail 'sender, date: text', quotes from '>' / 'On … wrote:' / forwarded headers and signatures from '-- ' removed, 12,000-character budget keeping the first and last mails with '[n mails left out]'), summarize() (30–50 words; one retry saying the count; still long → cut at the last sentence end within 50 words, else 50 words; short kept), check() with a made-up Portuguese conversation; service summaries.test. stub_server gains respond(). RED: tests/test_summaries.py failed on the missing module, then 12 GREEN.

### 2026-11-21
T02: summaries.pending() finds conversations with no summary or whose mails' hash (sha256 of the sorted item ids) changed; run() asks a few at a time (1 local, 4 remote; one retry per request), commits each summary with model, time and hash as it is written (a stopped run resumes), and stops at the first endpoint error. The mail import runs it after recording when summaries are ready, then redraws the pages; a failure or a cancel there is a warning, never a failed import. mail.summarize (write) enqueues mail-summarize for later. Chattr publish/render_pages take summaries {thread: (text, model)} (Caixa reads them from mail_threads on every publish); the entry shows the summary and 'Summary written by <model>', else the opening words. RED: 5 failing tests, then GREEN (17).

### 2026-11-21
T03: Settings → Summaries group (fields from the schema), Test summaries (summaries.test with what is typed; empty endpoint/model fall back to translation's on the worker) showing the summary and its word count, and Summarize mail now (mail.summarize; enabled once summaries are on and saved). Locales en/zh; Jobs page names mail-summarize and says written/left; a failed one has its own toast. e2e-translation's 'Allow a service on the internet' lookup made exact (summaries have a checkbox of their own). Settings tests RED then GREEN; the Jobs/toast tests were written after the code and passed at once. Built window rebuilt.
