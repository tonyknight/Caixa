---
id: 20261101-19-chattr-mirror-workflow
title: Chattr mirror workflow
type: chore
priority: medium
status: done
created: 2026-11-01
updated: 2026-11-02
closed: 2026-11-02
notes: 'Done: mirror script and workflow, token documented (maintainer creates it),
  README banner.'
parent:
depends_on:
- 20261101-03-chattr-import-and-licensing
subtasks: []
plan_status: done
---
## Description

Mirror `tools/chattr` to Chattr's repository.

## Acceptance criteria

- [x] `.github/workflows/mirror-chattr.yml` pushes `git subtree split --prefix=tools/chattr` as a fast-forward
- [x] Write token documented as a repository secret (created by the maintainer)
- [x] 'Developed in Caixa' banner in Chattr's README

## Context

Phase1-Collector Tasks Breakdown item 19. See `(2026-11-01) Phase1-Collector Requirements.md`: Requirements: Components (Mirror workflow); F15.

## Subtasks

Detailed checklist. Major subtasks should also appear in the frontmatter
`subtasks` field so they show up in `Status.md`.

## Implementation plan

Status: done
Current task: 

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
- [x] done

### T02: The workflow, the token documentation and the README banner

- `.github/workflows/mirror-chattr.yml`: on push to `main` (and by hand), full-history checkout,
  one run at a time, a clear failure when the secret is missing, then the script.
- The write token documented (what to create, where to store it, what it needs), in the root
  README and `tools/mirror/README.md`; Chattr's README gets a "Developed in Caixa" banner.
- Tests: the workflow file's essentials (trigger, full history, secret, no force); the banner.
- Verify: `python -m pytest -q && python -m black --check . && python -m mypy caixa tools/chattr/src`
- [x] done

## Completion report

- **Outcome:** `.github/workflows/mirror-chattr.yml` mirrors `tools/chattr/` to Chattr's repository on
  every push to `main` (or by hand): a full-history checkout, one run at a time, a clear failure
  message when the secret is missing, then `tools/mirror/mirror-chattr.sh`, which pushes
  `git subtree split --prefix=tools/chattr` as a fast-forward and never forces. Verified on the real
  history: Chattr's published `main` (`0152912…`) is an ancestor of today's split, so the first real
  run will fast-forward. The write token is documented for the maintainer (a fine-grained token with
  Contents read and write on the Chattr repository only, stored as the secret `CHATTR_MIRROR_TOKEN`),
  and Chattr's README carries a "Developed in Caixa" banner. **Nothing was pushed to Chattr's
  repository**: that needs the token, which only the maintainer can create.
- **Files:**
  - New: `.github/workflows/mirror-chattr.yml`, `tools/mirror/mirror-chattr.sh`,
    `tools/mirror/README.md`, `tests/test_mirror.py`.
  - Changed: `README.md` (a mirror section), `tools/chattr/README.md` (banner).
- **Errors:** none. Not verified: the workflow itself has not run on GitHub (no token, and Actions
  cannot be run from here); the script it calls is tested against local repositories and the real
  history.
- **Verify:** `python -m pytest -q` → 670 passed; `python -m black --check .` clean;
  `python -m mypy caixa tools/chattr/src` clean.

## Review

### 2026-11-02: 60169df..HEAD (T01–T02), reviewed in-session

**Verdict:** clean; Minor items only; actions for the maintainer.

- **Maintainer to do:** create the token and the secret (steps in `tools/mirror/README.md`); confirm
  the names (`CHATTR_MIRROR_TOKEN`, `tonyknight/Chattr`, branch `main`); if Chattr's `main` is
  protected, allow the token's pushes. Until then the workflow fails with a message saying so.
- **Minor:** the workflow triggers on pushes to Caixa's `main` (production); the project branch and
  `working` don't mirror. Change `branches:` if the maintainer wants the mirror to follow `working`.
- **Minor:** `actions/checkout@v4` is pinned by tag, not by commit hash.
- **Minor:** the mirror pushes only a branch (no tags); Chattr releases would need tag handling.
- **Minor:** anything committed straight to Chattr's repository blocks the mirror until it is pulled
  into Caixa (by design: no forced pushes); the banner tells contributors where to send changes.
- **Minor:** Chattr's package metadata (`tools/chattr/pyproject.toml`) mirrors as-is; its repository
  URL fields, if any, should point at the mirror, not Caixa.
- **Spec:** all three acceptance criteria are met. Files match the plan.
- **TDD:** RED then GREEN for both tasks (9 failing, then passing; 5 failing, then passing).
- **Commits:** all follow `{ticket-id} {task-id}: {title}` and are authored by Tony Knight.

## Notes

Append-only running log. Each entry dated.

### 2026-11-02
NEEDS MAINTAINER CONFIRMATION: secret name CHATTR_MIRROR_TOKEN; target repository tonyknight/Chattr branch main; the mirror triggers on pushes to Caixa's main (production). No push to Chattr's repository is made from this environment.

### 2026-11-02
T01: tools/mirror/mirror-chattr.sh: split, ls-remote (exit 2 = no such branch = first push; other failures stop), fast-forward check via merge-base --is-ancestor, push 'split:refs/heads/<branch>' with no force; exits: 0 pushed / up to date / dry run, 1 cannot reach or push, 2 usage, 3 not a fast-forward. Credentials in the URL are masked in everything printed (git's own error text is captured and masked). Verified on the real repository: Chattr's published main 0152912 is an ancestor of today's split, so the first real run will be a fast-forward.

### 2026-11-02
T02: workflow (push to main + manual; fetch-depth 0; persist-credentials false; concurrency group; contents: read; missing secret -> ::error:: with the instructions; ::add-mask:: on the token), tools/mirror/README.md (token steps, behaviour, what blocks the mirror), root README section, 'Developed in Caixa' banner in tools/chattr/README.md. The workflow file is checked by text assertions (no YAML parser dependency).
