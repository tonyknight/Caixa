---
name: bora-review
description: Use when a bora ticket's plan tasks are all checked and before marking the ticket done; when the user asks to review a ticket; or when bora-execute has just finished a ticket's last commit. Do not use for architecture review (that is Requirements / bora-design).
model_tier: premium
---

# bora-review

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

Review **this ticket's commit range**: `git log --grep=<ticket-id>`
from first `T01` commit through `HEAD` (no uncommitted work).

**Spec:** Requirements (matching items) + ticket acceptance criteria +
`## Implementation plan` (files named vs files touched).

**Quality:** YAGNI, TDD evidence (RED then GREEN in history or Notes),
commit messages `{ticket-id} {task-id}: {title}`.

**Verdicts:** Critical / Important / Minor.

- Critical or Important: do **not** mark `done`; do not start the next
  ticket. Fix via `bora-tdd` / `bora-debug` or ask the human.
- Minor: ticket Notes.

If the harness has subagents, dispatch a **fresh** reviewer with the
diff. Otherwise review in-session; still do not skip.

Append a short `## Review` subsection on the ticket (date, verdict,
findings). No `reviews/` folder.

Before marking `done`, fill the ticket's `## Completion report`
(Outcome / Files / Errors / Verify) — `bora dev report build` reads it
later to assemble the project's Completion document.

Human pasted review comments: read the diff, fix Critical/Important.
