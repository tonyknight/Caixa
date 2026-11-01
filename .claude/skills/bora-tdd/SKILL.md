---
name: bora-tdd
description: Use when implementing a feature, bugfix, or plan task in a bora project; before writing production code; or before marking a plan task or ticket done.
model_tier: premium
---

# bora-tdd

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

No production code without a failing test first. Cycle: RED (write
test, confirm the failure is the right one) → GREEN (minimal code) →
load **`bora-verify`** (run the task's Verify command in this turn) →
commit `{ticket-id} {task-id}: {title}` → next task.

Do not invent `npm test` if the plan names `pytest` or `xcodebuild`.
Expected RED on a new test is **not** `bora-debug`. On unexpected
failure, load `bora-debug` before a second rewrite.

After the ticket is complete, return to `bora-execute` (do not ask what
next). Exceptions (ask the human): spike tickets, generated code,
pure config/docs.
