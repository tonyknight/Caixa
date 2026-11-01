---
name: bora-worktree
description: Use when starting or resuming bora-execute on a bora project; when the user asks for an isolated branch or worktree; or before the first production commit of a project-level go. Do not create a nested worktree if already isolated.
model_tier: economy
---

# bora-worktree

The `model_tier` field is an advisory hint for the host. Bora does not choose models.

Detect existing isolation → native harness tool → `git worktree` fallback.
Never fight the harness.

## Record origin branch

Before creating isolation, record the checked-out branch (or detached
HEAD + short SHA) on the project briefing frontmatter:

```yaml
origin_branch: feature/share-extension
```

`bora-finish` option 1 merges **only** to `origin_branch` — never
assume `main`/`master`.

## Consent (once per project)

If no stored preference, ask: isolate this project's work?

- Yes → create isolation; set `worktree: true` on briefing frontmatter
- No → work in place; set `worktree: false`

Do not re-ask later tickets in the same execute run.

## Execute branch

`bora/<project_path-as-slug>` (e.g. `bora/photoapp-ios-share-extension`).
Reuse if it exists (resume). Ticket commits land here; integration
lands on `origin_branch`.

Worktree directory: prefer `.worktrees/` at repo root if gitignored;
else harness default. Do not commit the worktree.

Do not start execute on `main`/`master` without explicit consent.

Cleanup is **`bora-finish`** (human-approved), not this skill.
