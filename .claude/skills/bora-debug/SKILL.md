---
name: bora-debug
description: Use when a plan-task verify command fails, a build fails, or behavior is unexpected during bora execute or TDD; before proposing a second implementation attempt. Do not use for the expected RED failure of a newly written test.
model_tier: premium
---

# bora-debug

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

Four phases: investigate → pattern analysis → hypothesis → fix.
No fix without root cause.

Expected RED (new test failed as designed) is **`bora-tdd`**, not this
skill.

Record root cause in ticket Notes. If the plan task is wrong, amend the
plan (add `Tnn`; do not renumber committed ids).

After a fix, `bora-verify` that task's command, then continue execute.

If root cause is a Requirements hole, **stop execute**, reopen
`bora-design` with the human.

A second failure on the same hypothesis still stops and blocks the ticket.

Unexpected failure diagnosis is premium-class activity.
