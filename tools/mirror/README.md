# Mirroring Chattr to its own repository

Chattr is developed in this repository, under `tools/chattr/`. A GitHub Actions workflow
(`.github/workflows/mirror-chattr.yml`) publishes its history to Chattr's own repository, so people
can use and install Chattr without Caixa.

## How it works

On every push to `main` (and when started by hand from the Actions tab) the workflow runs
`tools/mirror/mirror-chattr.sh`, which:

1. runs `git subtree split --prefix=tools/chattr`, which recreates the folder's history as if it
   had always been its own repository: the same trees, authors, dates and messages, so commits that
   Chattr's repository already has keep their identity;
2. checks that Chattr's branch is an ancestor of the result;
3. pushes it as a **fast-forward**. The script never forces: if Chattr's repository has commits that
   Caixa's history lacks, it stops with an explanation (exit 3) and pushes nothing. Bring those
   commits into Caixa (`git subtree pull --prefix=tools/chattr <chattr remote> main`) and run again.

Commits that don't touch `tools/chattr/` change nothing there ("already up to date"). Preview a run
without pushing: `bash tools/mirror/mirror-chattr.sh --remote <url> --dry-run`.

## The write token (set up once, by the maintainer)

The workflow needs permission to push to Chattr's repository. That permission is a token you create
and store as a **repository secret** named `CHATTR_MIRROR_TOKEN`. Nothing in this repository or in
the workflow's logs contains it.

1. On GitHub, open *Settings → Developer settings → Personal access tokens → Fine-grained tokens* and
   generate a new fine-grained token.
2. **Repository access:** *Only select repositories*, and choose the Chattr repository
   (`tonyknight/Chattr`). Nothing else.
3. **Permissions → Repository permissions → Contents:** *Read and write*. No other permission.
4. Choose an expiry you will remember to renew (the workflow fails with a clear message when the
   token has expired or is missing).
5. In the Caixa repository open *Settings → Secrets and variables → Actions → New repository
   secret*, name it `CHATTR_MIRROR_TOKEN`, and paste the token.
6. If Chattr's `main` has branch protection, allow this token's owner to push to it (or exclude the
   branch from the rule that requires pull requests), since the mirror pushes directly.

Names used here (`CHATTR_MIRROR_TOKEN`, the repository `tonyknight/Chattr`, the branch `main`) are
set at the top of the workflow file and can be changed there.

## Chattr's repository is read-only in practice

Changes to Chattr are made in Caixa and flow out through this mirror. A commit made directly in
Chattr's repository blocks the mirror (it is no longer a fast-forward) until it is brought into
Caixa, so Chattr's README says where to send changes.
