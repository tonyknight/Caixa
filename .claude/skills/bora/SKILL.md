---
name: bora
description: Use when the repo has an AGENTS.md referring to bora, a docs/ai hierarchical project, or when the user points at a project briefing. Use at the start of a session in a bora project before reading or editing those files.
model_tier: standard
---

# bora

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

bora is a small CLI that maintains a structured set of Markdown + YAML
files for human-AI coding collaboration. The files live in version control
and are designed so any AI agent can read them to get oriented before
writing code.

Each software project lives under `docs/ai/<Codebase>/<Target>/<Project>/`.
Multiple projects may coexist. The human references one project's dated
briefing when starting a session; that directory is the only scope.

## When to use this skill

Load this skill when you see any of:

- An `AGENTS.md` at the repo root mentioning bora.
- A `docs/ai/<Codebase>/<Target>/<Project>/` directory with a dated
  briefing, a dated Requirements file, or `Status.md`.
- A `docs/ai/<path>/tickets/` directory containing `*.md` ticket files.
- The user asks you to create a ticket, update task status, or brief
  yourself on the project.

If `bora` is not on `PATH`, suggest the user install it
(`pipx install bora` or `pip install --user bora`) and fall back to
reading and editing the files directly using their conventions.

## Skill check (load before acting)

Before architecture, Requirements, tickets, a plan, execute, or code,
load the matching skill when it applies:

| Skill | When |
| --- | --- |
| `bora-design` | Briefing exists; Requirements still placeholder or architecture not agreed |
| `bora-plan` | Ticket needs `## Implementation plan` before code |
| `bora-tdd` | Implementing a plan task; expected RED on a new test |
| `bora-execute` | Requirements approved; "go"; or resuming the board |
| `bora-worktree` | Start of execute; isolation consent (via execute) |
| `bora-verify` | Before claiming task/ticket/board complete or finish |
| `bora-review` | After last plan task on a ticket; before `done` |
| `bora-debug` | Unexpected verify/build failure (not expected RED) |
| `bora-finish` | Board complete; project suite verified |

## Briefing sequence (do this first in any new session)

Read in this order:

1. `AGENTS.md` (root — operating instructions)
2. The human-referenced project briefing:
   `docs/ai/<path>/(YYYY-MM-DD) {ProjectName}.md`
3. Load `bora-design`. Discuss architecture before writing Requirements.
   Do not skip this conversation. Do not fill Requirements from the
   briefing alone.
4. After agreement, author/update:
   `docs/ai/<path>/(YYYY-MM-DD) {ProjectName} Requirements.md`
5. `docs/ai/<path>/Status.md`  (read only — never hand-edit)
6. When implementing: create tickets from Requirements Tasks Breakdown.
   After "go", load `bora-execute` (worktree, plan, tdd, verify, review,
   finish). Write `## Implementation plan` on each ticket (`bora-plan`).
7. `docs/ai/<path>/tickets/<id>.md` as active work demands
8. If budget-constrained, run `bora dev context <path> --budget N`

## Core conventions (do not violate)

- **`Status.md` is auto-generated.** Never hand-edit it.
- **Ticket IDs** via `bora dev ticket new <project_path> "<title>"`.
- **Plan on the ticket.** Never a `plans/` folder.
- **After "go", load `bora-execute`.** Walk the whole board. Never ask
  "should I continue?" Show completed vs remaining after each ticket.
- **Commit criteria** before `done` or commit:
  `{ticket-id} {task-id}: {title}`.
- **After any ticket write:** `bora dev lint` then `bora dev status`.

See `AGENTS.md` for full command surface and frontmatter reference.

## Session routing (opt-in)

If the current project's briefing has `routing: true` and the repo
catalog (`.bora/models.yaml`) is enabled, sync and resolve **this
session** before spawning subagents:

1. Collect the model ids this host can actually run (from the harness,
   not from the `bora` CLI), or use `--probe <url>` for an endpoint
   that exposes its own model list (the only network I/O in Bora, and
   only when you pass this flag).
2. Write available ids to a temp file, one per line, then run
   `bora dev routing sync <project_path> --host <cursor|claude|opencode> (--available <file> | --probe <url>)`.
   This writes the project's `routing.yaml`: resolved tiers plus every
   model the host offered. A tier that fails to match becomes an
   editable entry in that file instead of a question asked every
   session.
3. Read resolved slugs from `bora dev routing show <project_path>`
   (or `routing.yaml` directly; `routing resolve` still works as a
   read-only check). A tier left unresolved: ask the human, or leave
   it advisory for this session — do not invent a model id.
4. Pass matched host slugs into subagent starts when the host API
   accepts a model id.
5. `routing.yaml` persists; re-run `sync` when the host's available
   models change. Hand-edited tier values are pinned and survive a
   re-sync. Briefing `routing_cache` is 0.7.5 compatibility — read
   only, never hand-edited.
