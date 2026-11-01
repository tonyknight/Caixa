---
name: bora-verify
description: Use when marking a bora plan task complete, before marking a ticket done, before claiming tests pass, or before bora-finish. Do not use as a substitute for TDD's RED step.
model_tier: economy
---

# bora-verify

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

Iron law: no completion claim without a **fresh** run of the named
command in this turn.

| Gate | Command |
| --- | --- |
| Plan task complete | That task's **Verify:** line |
| Ticket `done` | Task verifies + acceptance criteria + any extra "ticket done" command in Requirements Commit criteria |
| Board complete / finish | Project suite from Requirements **Testing requirements** |

Paste or quote enough output to show pass/fail. "Should pass" is a
failure of this skill.

`bora-tdd` and `bora-finish` both require this skill.

Routine verification is economy-class activity.
