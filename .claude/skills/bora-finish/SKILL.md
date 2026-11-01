---
name: bora-finish
description: Use when a bora project has no remaining unblocked tickets (all done, or only blocked the human accepted as out of scope), verification of the project suite has passed, and the user needs to decide how to integrate. Use also when the user says the work is done, merge, or PR. Do not use after a single ticket if others remain.
model_tier: economy
---

# bora-finish

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

1. Run **`bora-verify`** on the project suite. Failures: no menu.
2. Run `bora dev report build <project_path>`. Complete the generated
   testing-guide prose and any "(not recorded)" fields the ticket
   fragments left blank. Required before the menu below — not
   optional polish.
3. Read `origin_branch` from the briefing (set by `bora-worktree`).
   Do not default to `main`. Ask if missing or ambiguous.

```
Board complete for <project_path>. What would you like to do?

1. Merge back to <origin_branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
```

**Option 1:** checkout `<origin_branch>`, merge `bora/<slug>` into it
only. Run post-merge verify if Requirements name one.

**After option 1, if Bora created a worktree this run**, offer cleanup:

```
Merge complete on <origin_branch>. Remove the bora worktree and execute
branch to restore the repo?

1. Yes — remove worktree + delete bora/<slug> (only what this session created)
2. No — leave worktree/branch in place
```

Yes: remove worktree dir, delete merged `bora/<slug>`, leave checkout on
`origin_branch`. Never remove human-created worktrees/branches.

Detached HEAD / external worktree: options 2 and 3 only.

Options 2–3: no auto-clean; offer cleanup only if the human asks.

Do not mark tickets `done` here. Note merge/PR URL on a ticket if useful.
Agent runs `git` / `gh` — no `bora dev finish` command.
