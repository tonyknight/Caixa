---
id: 20261121-04-the-apple-intelligence-helper-and-provider
title: The Apple Intelligence helper and provider
type: feature
priority: medium
status: done
created: 2026-11-21
updated: 2026-11-21
closed: 2026-11-21
notes: 'Done: Swift helper (unbuilt here) and the provider, tested with a stand-in.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

A small Swift helper that reaches Apple's on-device model, and the Python provider that runs several of them, so summaries and translation can use Apple Intelligence.

## Acceptance criteria

- [x] `tools/apple-intelligence/` is a Swift package building `caixa-apple-intelligence`: `--check` prints whether the model is ready (or why not); otherwise one JSON request per input line, one answer per output line
- [x] Caixa builds it on first use with `swift build -c release`; when that fails it says which command to run
- [x] The provider runs as many helpers as the Workers setting, sends requests to whichever is free, and speaks the same `chat` call as the OpenAI-compatible client
- [x] Tested with a stand-in helper (a Python script speaking the protocol); the Swift build and check are in the testing guide for the maintainer's Mac

## Context

Phase 1.5 - Mbox hot fixes (approved 2026-11-21). See `(2026-11-19) Phase 1.5 - Mbox Requirements.md`: *Hot fixes from the first real mbox*; M19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

## Completion report

- **Outcome:** `tools/apple-intelligence/` holds the Swift helper (`--check`, and one request and answer per line, with the safety filter's refusals marked). `caixa/apple_intelligence.py` finds or builds it (naming the command when it cannot), says whether the Mac's model is ready and why not, and runs several helpers at once behind the same `chat` and `translate` calls as the endpoint client.
- **Files:** `caixa/apple_intelligence.py`, `tools/apple-intelligence/{Package.swift,Sources/caixa-apple-intelligence/main.swift,README.md,.gitignore}`; tests `tests/test_apple_intelligence.py`, `tests/stand_in_apple.py`.
- **Errors:** none here. The Swift code has not been compiled (no macOS in the container).
- **Verify:** `python -m pytest -q tests/test_apple_intelligence.py` 10 passed; black clean; `mypy caixa tools/chattr/src` clean.

## Review

2026-11-21, in-session. **Verdict: clean (minors only), with the accepted risk.**

- Accepted risk (Requirements): the Swift helper is written from Apple's documentation and first built on the maintainer's Mac; a compile error there is fixed then. Testing guide: `swift build -c release --package-path tools/apple-intelligence`, `--check`, then Settings → Test.
- Minor: building on first use can take a minute or two while Settings waits; it happens once.

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: caixa/apple_intelligence.py: helper() (CAIXA_APPLE_INTELLIGENCE override; off macOS AppleUnavailable; builds with swift build -c release when missing or older than its sources, else names the command), check() {ready, reason, message} with reasons in words, AppleIntelligence(workers) lending requests to free helpers (started on demand; a helper that stops is dropped), chat() like the OpenAI client (system → instructions; a retry's turns labelled in the prompt), translate() with Chattr's instruction, Declined for the safety filter. tests/stand_in_apple.py speaks the protocol. RED (module missing), then 9 GREEN; 4 helpers answer 4 slow requests in parallel. mypy is clean with the project command (mypy caixa alone sees Chattr as Any).

### 2026-11-21
T02: tools/apple-intelligence/ (Package.swift: tools 6.0, macOS 26, Swift 5 language mode; main.swift: --check from SystemLanguageModel.default.availability, the line protocol with a fresh LanguageModelSession per request, GenerationOptions(temperature:), guardrailViolation → refused; README.md; .gitignore for .build). Written from Apple's documentation; not built here (Linux). A static test checks the program's name, platform and protocol keys (RED, then GREEN).
