---
name: bora-plan
description: Use when a ticket in a bora project needs an implementation plan before code (Requirements already approved); when the user asks to plan a ticket; or when bora-execute has selected a ticket that has no ## Implementation plan yet.
model_tier: premium
---

# bora-plan

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

Write `## Implementation plan` **on that ticket**. Do not create a
`plans/` file. Do not append the commit script to Requirements.

Each task is one commit (`T01`, `T02`, …), with exact files and a
**Verify:** command copied from Requirements Testing requirements.
No placeholders. During `bora-execute`, do not stop for per-ticket
plan approval. If the human is planning a single ticket before "go",
wait for their yes.

Commands: `bora dev plan show|set|task <project_path> <id> …`.
