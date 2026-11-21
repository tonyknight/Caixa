---
id: 20261121-04-the-apple-intelligence-helper-and-provider
title: The Apple Intelligence helper and provider
type: feature
priority: medium
status: in-progress
created: 2026-11-21
updated: 2026-11-21
closed:
notes: ''
parent:
depends_on: []
subtasks: []
plan_status: in-progress
current_task: T02
---
## Description

A small Swift helper that reaches Apple's on-device model, and the Python provider that runs several of them, so summaries and translation can use Apple Intelligence.

## Acceptance criteria

- [ ] `tools/apple-intelligence/` is a Swift package building `caixa-apple-intelligence`: `--check` prints whether the model is ready (or why not); otherwise one JSON request per input line, one answer per output line
- [ ] Caixa builds it on first use with `swift build -c release`; when that fails it says which command to run
- [ ] The provider runs as many helpers as the Workers setting, sends requests to whichever is free, and speaks the same `chat` call as the OpenAI-compatible client
- [ ] Tested with a stand-in helper (a Python script speaking the protocol); the Swift build and check are in the testing guide for the maintainer's Mac

## Context

Phase 1.5 - Mbox hot fixes (approved 2026-11-21). See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`: *Hot fixes from the first real mbox*; M19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T02

**Design:**

- **The helper** (`tools/apple-intelligence/`, a Swift package building `caixa-apple-intelligence`,
  macOS 26 or later): `--check` prints `{"ready": true}` or `{"ready": false, "reason": …,
  "message": …}` from `SystemLanguageModel.default.availability` (`not_eligible`, `not_enabled`,
  `not_ready`, `unavailable`). Without arguments it reads one JSON request per line on its input,
  `{"id", "instructions", "prompt", "temperature"}`, answers each with a fresh
  `LanguageModelSession(instructions:)`, and writes one line per answer: `{"id", "text"}`, or
  `{"id", "error", "refused"}` (`refused` when the model's safety filter declined).
- **Caixa** (`caixa/apple_intelligence.py`): `helper()` finds the built program, building it with
  `swift build -c release --package-path tools/apple-intelligence` the first time (or when its
  sources are newer); when that cannot be done it raises saying which command to run. `check()`
  answers ready or why not (`not_a_mac` on anything but macOS). `AppleIntelligence(workers)` starts
  that many helpers and lends each request to a free one; it speaks the OpenAI-compatible client's
  `chat(messages)` (system messages become the instructions, the rest the prompt) and `translate`
  (Chattr's translation instruction), so summaries and translation can use it unchanged (ticket 20
  wires it into Settings). A declined request raises `Declined` (a `TranslationError`).
  `CAIXA_APPLE_INTELLIGENCE` names another program to run instead (the tests' stand-in).

### T01: The provider, tested with a stand-in helper

- `caixa/apple_intelligence.py`; `tests/stand_in_apple.py` (a Python program speaking the protocol).
- Tests (`tests/test_apple_intelligence.py`): check says ready or why not, and `not_a_mac` off
  macOS; requests come back in order; four helpers answer four slow requests about as fast as one
  request; a declined request raises `Declined`; system messages become instructions; `translate`
  returns Chattr's `Translation`; without Swift the build error names the command.
- Verify: `python -m pytest -q tests/test_apple_intelligence.py && python -m mypy caixa`
- [x] done

### T02: The Swift helper

- `tools/apple-intelligence/{Package.swift,Sources/caixa-apple-intelligence/main.swift,README.md}`.
- Tests: a static test that the package names the program, the platform and the protocol's keys
  (it cannot be built here); on the maintainer's Mac `swift build -c release --package-path
  tools/apple-intelligence` and `--check` (testing guide).
- Verify: `python -m pytest -q tests/test_apple_intelligence.py && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: caixa/apple_intelligence.py: helper() (CAIXA_APPLE_INTELLIGENCE override; off macOS AppleUnavailable; builds with swift build -c release when missing or older than its sources, else names the command), check() {ready, reason, message} with reasons in words, AppleIntelligence(workers) lending requests to free helpers (started on demand; a helper that stops is dropped), chat() like the OpenAI client (system → instructions; a retry's turns labelled in the prompt), translate() with Chattr's instruction, Declined for the safety filter. tests/stand_in_apple.py speaks the protocol. RED (module missing), then 9 GREEN; 4 helpers answer 4 slow requests in parallel. mypy is clean with the project command (mypy caixa alone sees Chattr as Any).
