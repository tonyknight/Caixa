---
name: bora-execute
description: Use when a bora project's Requirements are approved and the user asks to implement, execute, go, or work through the tickets; when resuming a project that still has todo or in-progress tickets; or after a ticket is marked done and other tickets remain.
model_tier: standard
---

# bora-execute

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

Walk the **whole ticket board**. Create missing tickets from the
Requirements Tasks Breakdown. Order: skip done; skip blocked; honor
`depends_on`; then priority; then oldest id. One ticket in-progress
at a time.

## On start

1. Load **`bora-worktree`** (consent once; record `origin_branch` on
   the briefing frontmatter).
2. If the briefing has `routing: true` and the repo catalog is enabled,
   sync this session (`bora dev routing sync` with an injected
   available-model list, or `--probe <url>`) — this writes
   `routing.yaml`, resolved tiers plus the full available inventory.
   Read resolved slugs from it. A tier left unresolved: ask the human,
   or leave it advisory for this session. Pass slugs to subagents when
   the host supports it. Do not hand-edit briefing `routing_cache`
   (0.7.5 compatibility, read-only).

## Per ticket

1. `bora-plan` if `## Implementation plan` is missing or empty.
2. `bora-tdd` for each open `T0n`:
   - unexpected verify/build failure → `bora-debug`, then continue or block
   - each task done → `bora-verify` (task Verify line)
3. After last task: `bora-verify` (ticket scope) → **`bora-review`**
4. Mark `done` only if review is clean or minors-only.
5. `bora dev status` — **show** completed vs remaining → next ticket.

Never ask "should I continue?"

## Board complete

`bora-verify` (project suite from Requirements) → **`bora-finish`**.

## Stop when

Board complete, nothing unblocked remains, debug exhausted on same
hypothesis, plan collides with Requirements, or the human interrupted.

Resume from Status.md, `current_task`, and `git log --grep=<ticket-id>`.

Routine `bora-verify` is economy-class activity. Unexpected failure
loads `bora-debug` (premium). Do not implement automatic model switching.

## Optional subagent mode

If the harness can dispatch subagents and the human did not forbid them:
one implementer **per ticket** (not per `T0n`, not two tickets in
parallel on shared files). Controller keeps board, Status.md, and
`bora-review`. Implementer gets project path, ticket path, Requirements
path, commit contract, TDD iron law — no chat history. On DONE,
controller runs `bora-review`. If subagents unavailable, in-session
execute is correct.
