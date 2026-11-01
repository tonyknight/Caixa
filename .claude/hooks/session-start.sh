#!/bin/bash
# Installs the Bora CLI (https://github.com/tonyknight/Bora) in Claude Code
# cloud sessions so the bora-* skills in .claude/skills/ can run `bora dev …`.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Skip if already installed (cached container, resume, clear, compact).
if command -v bora >/dev/null 2>&1; then
  exit 0
fi

pip install --quiet --disable-pip-version-check --root-user-action=ignore \
  "git+https://github.com/tonyknight/Bora.git" >&2

bora --version >&2
