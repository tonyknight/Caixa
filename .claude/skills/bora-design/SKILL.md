---
name: bora-design
description: Use when a bora project briefing exists and architecture is not yet agreed; when the Requirements file is still a placeholder; or when the user wants to discuss design before tickets. Do not use after Requirements are approved and execution has started, unless the user explicitly reopens design.
model_tier: premium
---

# bora-design

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

Brainstorming with **output = the dated Requirements file**, not a
separate spec directory.

1. Read the briefing first.
2. Ask questions (prefer one at a time). Propose 2–3 approaches with a
   recommendation.
3. Present design in sections scaled to complexity; wait for agreement
   on contested sections (architecture, testing/commit criteria, Tasks
   Breakdown).
4. Only then fill Requirements: architecture, requirements, acceptance,
   **Testing requirements** (name real commands: `xcodebuild`, `pytest`, …),
   commit criteria, Tasks Breakdown, risks, open questions. Bump
   `last_reviewed`.

Hard gate: no tickets, no code, no `bora-execute` until the human
approves Requirements. YAGNI: do not invent tickets for non-goals.

If the project is too large for one Requirements file, split into
another `bora dev init` path — do not create a spec subdirectory.

If execution finds a Requirements hole, stop execute and reopen design
with the human — do not invent architecture on the ticket.
