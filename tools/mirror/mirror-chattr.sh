#!/usr/bin/env bash
# Mirror tools/chattr/ to Chattr's own repository as a fast-forward.
#
#   mirror-chattr.sh --remote URL [--branch main] [--prefix tools/chattr] [--dry-run]
#
# `git subtree split` recreates the history of the folder as if it had always been its own
# repository (same trees, authors, dates and messages), so Chattr's repository only gains the new
# commits. The script pushes that history to the remote branch and nothing else:
#   - it never forces; if the remote branch has commits the split doesn't, it stops (exit 3);
#   - it says "up to date" and does nothing when there is nothing new;
#   - it never prints credentials that are part of the remote URL.
# Run it from a full clone of Caixa (the whole history is needed).
set -euo pipefail

remote=""
branch="main"
prefix="tools/chattr"
dry_run=0

usage() {
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --remote) remote="${2:-}"; shift 2 ;;
    --branch) branch="${2:-}"; shift 2 ;;
    --prefix) prefix="${2:-}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h | --help) usage; exit 0 ;;
    *) echo "mirror-chattr: unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$remote" ]; then
  echo "mirror-chattr: --remote URL is required" >&2
  exit 2
fi

# Hide user:password@ in anything we print.
mask() { sed -E 's#(://)[^/@[:space:]]*@#\1***@#g'; }
shown="$(printf '%s' "$remote" | mask)"

split="$(git subtree split --prefix="$prefix" 2>/dev/null | tail -n 1)"
if [ -z "$split" ]; then
  echo "mirror-chattr: nothing to mirror: no history under $prefix" >&2
  exit 1
fi

set +e
listing="$(git ls-remote --exit-code --heads "$remote" "refs/heads/$branch" 2>&1)"
status=$?
set -e
case "$status" in
  0) remote_sha="${listing%%[[:space:]]*}" ;;
  2) remote_sha="" ;; # the remote has no such branch yet: the first push
  *)
    printf 'mirror-chattr: cannot read %s:\n%s\n' "$shown" "$listing" | mask >&2
    exit 1
    ;;
esac

if [ -n "$remote_sha" ]; then
  if [ "$remote_sha" = "$split" ]; then
    echo "mirror-chattr: $shown $branch is already up to date ($split)."
    exit 0
  fi
  tmp_ref="refs/mirror/remote-$branch"
  if ! fetched="$(git fetch --quiet --no-tags "$remote" "refs/heads/$branch:$tmp_ref" 2>&1)"; then
    printf 'mirror-chattr: cannot fetch %s:\n%s\n' "$shown" "$fetched" | mask >&2
    exit 1
  fi
  if ! git merge-base --is-ancestor "$remote_sha" "$split"; then
    git update-ref -d "$tmp_ref" 2>/dev/null || true
    {
      echo "mirror-chattr: not a fast-forward: $shown $branch has commits that Caixa's $prefix"
      echo "history does not. Nothing was pushed. Bring those commits into Caixa (for example with"
      echo "'git subtree pull --prefix=$prefix <remote> $branch'), then run the mirror again."
      echo "The mirror never forces."
    } >&2
    exit 3
  fi
  new="$(git rev-list --count "$remote_sha..$split")"
  git update-ref -d "$tmp_ref" 2>/dev/null || true
else
  new="$(git rev-list --count "$split")"
fi

if [ "$dry_run" -eq 1 ]; then
  echo "mirror-chattr: would push $new commit(s) ($split) to $shown $branch."
  exit 0
fi

if ! pushed="$(git push --quiet "$remote" "$split:refs/heads/$branch" 2>&1)"; then
  printf 'mirror-chattr: the push to %s failed:\n%s\n' "$shown" "$pushed" | mask >&2
  exit 1
fi
echo "mirror-chattr: pushed $new commit(s) ($split) to $shown $branch."
