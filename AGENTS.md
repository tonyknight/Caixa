# Agent Instructions

<!-- bora-managed:start version="0.8.0" -->
## Philosophy

This project uses a structured collaboration framework. Documentation in
`docs/ai/<Codebase>/<Target>/<Project>/` is your per-project shared
workspace. Multiple projects may coexist under `docs/ai/`. You read the
referenced project to get oriented, you propose updates as work
progresses, and you treat that project's files as the source of truth
about its state.

The project briefing and Requirements files are dated and named after
the project: `(YYYY-MM-DD) {ProjectName}.md` and
`(YYYY-MM-DD) {ProjectName} Requirements.md`. `Status.md` is
auto-generated — never hand-edit it.

Three principles:

1. **`Status.md` is auto-generated.** Never edit it directly. Update
   tickets instead, then run `bora dev status <project_path>` to
   regenerate.
2. **The project briefing and Requirements file are collaborative.**
   Discuss architecture with the human before writing Requirements.
   Propose changes in conversation; don't edit silently.
3. **Tickets are where work happens.** Create them from the Requirements
   Tasks Breakdown only after architecture is agreed. The implementation
   plan lives **on the ticket** (`## Implementation plan`), never in
   Requirements and never in a `plans/` folder.

Before proposing architecture, writing Requirements, creating tickets,
writing a plan, executing the board, or writing code, load the matching
skill (`bora-design`, `bora-plan`, `bora-tdd`, `bora-execute`,
`bora-worktree`, `bora-verify`, `bora-review`, `bora-debug`,
`bora-finish`). After a project-level "go", load `bora-execute` and walk
remaining tickets. Never ask "should I continue?" between tickets. Show
completed vs remaining after each ticket.

The human runs `bora dev` for setup (`init`, `skill install`, `upgrade`)
and conversational approval. You run ticket, plan, status, and lint
commands. Do not ask the human to type those.

## Briefing sequence

When you join a session with no prior context, read in this order:

1. AGENTS.md (root — this file)
2. The human-referenced project briefing:
   `docs/ai/<path>/(YYYY-MM-DD) {ProjectName}.md`
3. Load `bora-design`. Discuss architecture with the human before
   writing Requirements. Do not skip this conversation. Do not fill in
   the Requirements file from the briefing alone.
4. After agreement, author/update:
   `docs/ai/<path>/(YYYY-MM-DD) {ProjectName} Requirements.md`
5. `docs/ai/<path>/Status.md`  (read only — never hand-edit)
6. When implementing: create tickets from the Requirements
   Tasks Breakdown. After the human says go, load `bora-execute`
   (worktree consent, plan, tdd, verify, review, finish). Write
   `## Implementation plan` on each ticket (`bora-plan`) before code.
   Use `bora-tdd` per plan task.
7. `docs/ai/<path>/tickets/<id>.md` as the active work demands
8. If budget-constrained, run `bora dev context <path> --budget N`

Hard gates: no tickets until Requirements are approved; no production
code until the current ticket has an implementation plan; no `done`
without Commit criteria. Commit message:
`{ticket-id} {task-id}: {title}`.

## Scope guardrail

**Scope guardrail:** The human will reference the correct `docs/ai/<path>/(YYYY-MM-DD) {ProjectName}.md` when starting the session. Only read and write files inside that project's directory (`docs/ai/<path>/` and its `tickets/`). Do not operate on other `docs/ai/<other>/` projects, the legacy flat `docs/ai/Project.md`, or the repo root unless the human explicitly references them. `Status.md` is per-project only — do not expect or create a root `docs/ai/Status.md` or `docs/ai/Tasks.md` aggregation. All `bora dev` commands require the explicit `<project_path>` argument to enforce this.

## Layout

```
docs/
  ai/
    <Codebase>/
      <Target>/
        <Project>/
          (YYYY-MM-DD) {ProjectName}.md
          (YYYY-MM-DD) {ProjectName} Requirements.md
          Status.md
          tickets/
            .gitkeep
            <id>.md
```

Example (`bora dev init "QromaCore/Hamburg/Gallery Refactor"` on 2026-08-14):

```
docs/
  ai/
    QromaCore/
      Hamburg/
        Gallery Refactor/
          (2026-08-14) Gallery Refactor.md
          (2026-08-14) Gallery Refactor Requirements.md
          Status.md
          tickets/
            .gitkeep
```

## Workflows

### Orient, then Requirements, then tickets

1. Read the referenced project briefing and confirm scope with the human.
2. Discuss architecture: components, data model, key flows, constraints,
   non-goals. Propose options; wait for agreement.
3. Write or update `(YYYY-MM-DD) {ProjectName} Requirements.md`:
   architecture, requirements, acceptance criteria, testing
   requirements, commit criteria, Tasks Breakdown, risks, and open
   questions. Bump `last_reviewed`.
4. Only then create tickets from the Tasks Breakdown:
   `bora dev ticket new <project_path> "<title>"`.
   `<project_path>` is the same value passed to `bora dev init`.
   Use `--parent` when a breakdown item splits.
5. Tickets may be assigned in conversation to one or more agents; each
   agent still stays inside this project directory and updates only the
   tickets it is working.
6. After ticket changes, run `bora dev status <project_path>` so
   `Status.md` reflects current work.
7. Before marking a ticket or subtask `done`, and before any git
   commit, satisfy **Commit criteria** in the Requirements file: the
   subtask's completion tests pass, the change meets the requirement,
   and build/tests pass (including platform builds such as macOS/iOS
   when that is the target). Commit message format:
   `{ticket-id} {task-id}: {title}`.

### After Requirements are approved ("go")

1. Create tickets from the Tasks Breakdown if they do not exist.
2. Load `bora-execute`. Do not stop after the first ticket.
3. On execute start: `bora-worktree` (consent once; record
   `origin_branch` and `worktree` on the briefing frontmatter).
4. For each unblocked ticket: `bora-plan` if needed, then `bora-tdd`
   (with `bora-debug` on unexpected failure, `bora-verify` on each task).
5. After last task: `bora-verify` (ticket) → `bora-review` → mark
   `done` only if review is clean or minors-only.
6. Show completed vs remaining (`bora dev status`) and start the next
   ticket. Never ask whether to continue.
7. Board complete: `bora-verify` (project suite) → `bora-finish`
   (merge to `origin_branch`, PR, or keep; optional worktree cleanup).

Stop when the board is complete, blocked with no other runnable work,
debug exhausted on the same hypothesis, or the human interrupted.

### Briefing frontmatter (execute metadata)

Optional keys on the project briefing, set during execute:

- `worktree: true|false` — isolation consent
- `origin_branch: <name>` — branch when the human said "go"; merge target
  for `bora-finish` option 1 (never assume `main`)

### Resuming work on an existing ticket

1. Run `bora dev ticket show <project_path> <id>` (or read the file
   directly). Example:
   `bora dev ticket show QromaCore/Hamburg/Gallery\ Refactor 20260811-01`
2. Check the latest entry in the body Notes section.
3. Check subtask checkboxes for what's already done.
4. If status is `todo`, set it to `in-progress`:
   `bora dev ticket set <project_path> <id> status in-progress`.
5. Append a dated Notes entry when you make meaningful progress:
   `bora dev ticket note <project_path> <id> "<text>"`.
6. After ticket changes, run `bora dev status <project_path>`.
   Example: `bora dev status QromaCore/Hamburg/Gallery\ Refactor`.

### Marking a ticket complete

1. Before `bora dev ticket set <project_path> <id> status done` (or
   setting a subtask to `done`), run **`bora-verify`** and satisfy
   Commit criteria in the Requirements file.
2. Verify all acceptance criteria are met and all body checkboxes are
   checked.
3. Then set status: `bora dev ticket set <project_path> <id> status done`.
   The `closed` date populates automatically.
4. If the human wants a commit, use message
   `{ticket-id} {task-id}: {title}`. Do not commit if build or
   completion tests failed.

### Recording an architectural decision

There is no decision command. After agreeing with the human, edit the
project's Requirements file directly (typically under Architecture or
Open questions).

## Validation

After any write to a ticket file, run `bora dev lint <project_path>`,
then `bora dev status <project_path>`. Don't trust your own YAML output
without verification — lint catches frontmatter errors before they
corrupt project state.

## Frontmatter reference

Tickets live at `docs/ai/<path>/tickets/<id>.md`. Ticket IDs are unique
per-project, not repo-global.

Ticket frontmatter fields:

- `id` — `YYYYMMDD-NN-slug` format. Set by
  `bora dev ticket new <project_path> "<title>"`; don't change.
- `title` — short human-readable title.
- `type` — `feature` | `bug` | `chore` | `spike`.
- `priority` — `high` | `medium` | `low`.
- `status` — `todo` | `in-progress` | `blocked` | `done`.
- `created`, `updated`, `closed` — ISO dates. Managed by the CLI.
- `notes` — one-line current state, shown in `Status.md`.
- `parent` — single ticket id, or empty.
- `depends_on` — list of ticket ids that must be `done` first.
- `subtasks` — list of `{id, title, status}` for major subtasks.
- `plan_status` — optional. `draft` | `approved` | `in-progress` | `done` | `blocked`.
- `current_task` — optional. A `Tnn` id from this ticket's implementation plan.
<!-- bora-managed:end -->

## Project-specific instructions

Add local rules below this heading. `bora dev upgrade` never overwrites
this section.

These rules apply to every contributor, human or AI.

### Branches

- `main` is production only. Never commit to it directly.
- `working` is the integration branch. Release-train and project
  branches feed into it.
- Project branches are named `<year>-<Release Train>/<Project>`, for
  example `2026-Istanbul/Phase1-Collector`. Commit completed tickets on
  the project branch, then merge it into `working` when the project is
  done.

### Naming

- Never name things arbitrarily: release trains, projects, branches,
  top-level folders, files meant for people. If a name isn't already
  defined in the project's briefing or Requirements, ask the maintainer.
- Bora project paths follow `<Release Train>/<Project>`, for example
  `docs/ai/Istanbul/Phase1-Collector/`.

### Authorship

- Commits are authored and committed by a real, reachable person.
  Collaborators must be able to contact the author. Never commit under a
  fictitious or agent identity.
- Credit AI assistance with a `Co-Authored-By:` trailer in the commit
  message.

### Documentation

- Important documentation lives in the repository's own docs (the root
  `README.md`, the Bora project files under `docs/ai/`), never only in an
  agent-specific location such as `.claude/` or a tool's private plan
  folder.

### Data

- Never commit real personal data. Tests use the synthetic fixture
  family only.
