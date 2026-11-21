---
id: 20261121-04-the-apple-intelligence-helper-and-provider
title: "The Apple Intelligence helper and provider"
type: feature
priority: medium
status: todo
created: 2026-11-21
updated: 2026-11-21
closed:
notes: ""
parent:
depends_on: []
subtasks: []
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

Status: draft
Current task:

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.
