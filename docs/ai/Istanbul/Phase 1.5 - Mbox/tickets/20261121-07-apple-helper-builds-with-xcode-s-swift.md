---
id: 20261121-07-apple-helper-builds-with-xcode-s-swift
title: Apple helper builds with Xcode's Swift
type: bug
priority: high
status: done
created: 2026-11-21
updated: 2026-11-21
closed: 2026-11-21
notes: 'Done: build with Xcode''s Swift; old Swift and Intel Macs told plainly.'
parent:
depends_on: []
subtasks: []
plan_status: done
---
## Description

On the maintainer's Mac the helper did not build: `swift` on the PATH was an old swift.org toolchain (Swift 5.0.3 in ~/Library/Developer/Toolchains), which cannot read the package (Apple Intelligence needs Swift 6.2, from Xcode 26) and clashes with macOS's own Swift libraries. Caixa's own build ran the same `swift`.

## Acceptance criteria

- [x] Caixa builds the helper with Xcode's Swift (`xcrun swift`, without a `TOOLCHAINS` choice), not whatever `swift` comes first on the PATH
- [x] A Swift older than 6.2 is refused before building, saying which version was found and what to install or select
- [x] A Mac without Apple silicon is told at once that Apple Intelligence cannot run on it (not_eligible), without building
- [x] The README says how to build with Xcode's Swift and how to see which Swift is used

## Context

Bug found on the maintainer's first try of ticket 19 (`20261121-04`). Requirements: *Hot fixes*, Apple Intelligence; M19.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

**Design:** `helper()` builds with `xcrun swift` when `xcrun` is there (else `swift`), with
`TOOLCHAINS` removed from the environment, so Xcode's selected toolchain is used rather than a
swift.org toolchain on the PATH. Before building it asks that Swift for its version and refuses
anything older than 6.2, naming the version found and what to do (install or select Xcode 26:
`sudo xcode-select -s /Applications/Xcode.app`). `check()` and `helper()` first ask the Mac whether
it has Apple silicon (`sysctl -n hw.optional.arm64`, true also under Rosetta) and say
`not_eligible` without building when it has not.

### T01: Xcode's Swift, its version, and Apple silicon first

- `caixa/apple_intelligence.py`, `tools/apple-intelligence/README.md`.
- Tests (`tests/test_apple_intelligence.py`, with the system calls faked): an old Swift is refused
  with its version named; the build runs `xcrun swift build …` without `TOOLCHAINS`; a Mac without
  Apple silicon is `not_eligible` and nothing is built.
- Verify: `python -m pytest -q tests/test_apple_intelligence.py && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** Caixa builds the Apple Intelligence helper with Xcode's own Swift (`xcrun swift`, ignoring `TOOLCHAINS`), refuses a Swift older than 6.2 saying which one it found and how to select Xcode 26, and tells a Mac without Apple silicon at once that it cannot run Apple Intelligence.
- **Files:** `caixa/apple_intelligence.py`, `tools/apple-intelligence/README.md`, `docs/Documentation/Collector.md`, the completion document's testing guide; tests `tests/test_apple_intelligence.py`.
- **Errors:** my first edit script had a syntax error and changed nothing (redone); the first message gave "5.0" for 5.0.3 (it now quotes the version as Swift prints it).
- **Verify:** `python -m pytest -q tests/test_apple_intelligence.py tests/test_summaries.py tests/test_translation.py` 57 passed; black and mypy clean.

## Review

2026-11-21, in-session. **Verdict: clean.** The Swift helper itself is still unbuilt until the maintainer's Mac has Xcode 26 selected.

## Notes

Append-only running log. Each entry dated.

### 2026-11-21
T01: builds with xcrun swift (plain swift without xcrun) and TOOLCHAINS removed from the build's environment; asks that Swift for its version first and refuses anything older than 6.2, naming what it found and how to select Xcode 26; asks sysctl hw.optional.arm64 first and answers not_eligible without building on a Mac without Apple silicon (an unknown answer is taken as yes). README explains xcrun swift --version, xcode-select -s, and the old-toolchain messages. RED: 3 tests, then GREEN (13).
