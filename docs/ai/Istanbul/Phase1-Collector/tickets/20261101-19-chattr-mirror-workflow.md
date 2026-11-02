---
id: 20261101-19-chattr-mirror-workflow
title: Chattr mirror workflow
type: chore
priority: medium
status: in-progress
created: 2026-11-01
updated: 2026-11-02
closed:
notes: Breakdown item 19.
parent:
depends_on:
- 20261101-03-chattr-import-and-licensing
subtasks: []
current_task: T01
---
## Description

Mirror `tools/chattr` to Chattr's repository.

## Acceptance criteria

- [ ] `.github/workflows/mirror-chattr.yml` pushes `git subtree split --prefix=tools/chattr` as a fast-forward
- [ ] Write token documented as a repository secret (created by the maintainer)
- [ ] 'Developed in Caixa' banner in Chattr's README

## Context

Phase1-Collector Tasks Breakdown item 19. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Components (Mirror workflow); F15.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: in-progress
Current task: T01

**Design:** `tools/chattr/` is developed in Caixa and mirrored to Chattr's own repository. The
mirror is `git subtree split --prefix=tools/chattr` pushed as a fast-forward: the split recreates
Chattr's published commits unchanged (same trees, authors, messages), so Chattr's repository only
ever gains the new commits. Checked on the real history: Chattr's published `main` (`0152912…`) is an
ancestor of today's split. The logic lives in a script (`tools/mirror/mirror-chattr.sh`) that is
tested against local repositories; the workflow only supplies the checkout and the token. **Nothing
here pushes to Chattr's repository from this environment**: that needs the maintainer's token.

**Names to confirm with the maintainer:** the secret `CHATTR_MIRROR_TOKEN`, the target repository
`tonyknight/Chattr` (branch `main`), and Caixa's source branch `main` (production).

### T01: The mirror script

- `tools/mirror/mirror-chattr.sh --remote URL [--branch main] [--prefix tools/chattr] [--dry-run]`:
  fetch the remote branch, split, push `split → branch` with no force.
- Outcomes: first push (empty remote), fast-forward, already up to date, and a refusal when the
  remote has commits Caixa's split doesn't (never forced). Credentials in a URL are never printed.
- Tests: local bare repositories: a first push equals the subtree's tree and holds only the commits
  that touched it; later commits fast-forward; commits elsewhere change nothing; a dry run pushes
  nothing; a diverged remote is refused and left alone; the real history descends from Chattr's
  published `main`.
- Verify: `python -m pytest -q tests/test_mirror.py`
- [ ] done

### T02: The workflow, the token documentation and the README banner

- `.github/workflows/mirror-chattr.yml`: on push to `main` (and by hand), full-history checkout,
  one run at a time, a clear failure when the secret is missing, then the script.
- The write token documented (what to create, where to store it, what it needs), in the root
  README and `tools/mirror/README.md`; Chattr's README gets a "Developed in Caixa" banner.
- Tests: the workflow file's essentials (trigger, full history, secret, no force); the banner.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [ ] done

## Completion report

- **Outcome:**
- **Files:**
- **Errors:**
- **Verify:**

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
NEEDS MAINTAINER CONFIRMATION: secret name CHATTR_MIRROR_TOKEN; target repository tonyknight/Chattr branch main; the mirror triggers on pushes to Caixa's main (production). No push to Chattr's repository is made from this environment.
