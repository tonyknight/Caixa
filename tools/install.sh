#!/usr/bin/env bash
# Install what Caixa needs, from a checkout of this repository.
#
#   ./tools/install.sh                 Caixa, Chattr and the tools they use
#   ./tools/install.sh --dev           also the test tools and the window's Node packages
#   ./tools/install.sh --help          every option
#
# It:
#   1. installs the programs Caixa runs: ExifTool, FFmpeg, and for scanned PDFs OCRmyPDF,
#      Tesseract (with its languages) and Ghostscript (Homebrew on a Mac, apt on Debian or Ubuntu;
#      elsewhere it says what to install);
#   2. makes a Python virtual environment (.venv) if there is none;
#   3. installs Chattr and then Caixa into it, from this checkout (Chattr must come from
#      tools/chattr: an unrelated project of that name is on PyPI);
#   4. with --dev, the test tools and the window's Node packages (pnpm);
#   5. checks the result: `caixa --version` and `caixa doctor`.
#
# Running it again is safe: what is there already is kept or brought up to date. Nothing is
# downloaded but packages; no model is ever downloaded.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PYTHON=""
LANGUAGES="eng"
DEV=0
SYSTEM=1
DRY=0
ASSUME_YES=0

usage() {
  cat <<'EOF'
Usage: tools/install.sh [options]

  --dev                 also install the test tools (pytest, black, mypy) and the window's
                        Node packages (needs Node.js; pnpm is enabled through corepack)
  --languages "eng por" Tesseract languages to install for scanned PDFs (default: eng).
                        Use Tesseract's codes: por, spa, fra, deu, ita, …
  --venv PATH           where the virtual environment goes (default: .venv in the checkout)
  --python PROGRAM      the Python to make it with (default: python3; 3.10 or newer)
  --no-system           leave the system programs alone (no Homebrew, no apt)
  --yes                 do not ask before installing system packages
  --dry-run             say what would be done, and do nothing
  -h, --help            this text
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dev) DEV=1 ;;
    --languages) shift; LANGUAGES="${1:?--languages needs a list, such as \"eng por\"}" ;;
    --languages=*) LANGUAGES="${1#*=}" ;;
    --venv) shift; VENV="${1:?--venv needs a path}" ;;
    --venv=*) VENV="${1#*=}" ;;
    --python) shift; PYTHON="${1:?--python needs a program}" ;;
    --python=*) PYTHON="${1#*=}" ;;
    --no-system) SYSTEM=0 ;;
    --yes|-y) ASSUME_YES=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "install.sh: unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done
LANGUAGES="$(echo "$LANGUAGES" | tr '+,' '  ')"

say() { printf '\n==> %s\n' "$*"; }
note() { printf '    %s\n' "$*"; }
run() {
  printf '    $ %s\n' "$*"
  if [ "$DRY" -eq 0 ]; then "$@"; fi
}
have() { command -v "$1" >/dev/null 2>&1; }

# --- 1. The system programs ---------------------------------------------------------------------

system_mac() {
  if ! have brew; then
    note "Homebrew is not installed, so the programs below are left for you to install."
    note "Get it from https://brew.sh, then run this script again; or install by hand:"
    note "  exiftool, ffmpeg, ocrmypdf (brings Tesseract and Ghostscript), tesseract-lang"
    return
  fi
  local packages="exiftool ffmpeg ocrmypdf"
  local lang
  for lang in $LANGUAGES; do
    if [ "$lang" != "eng" ]; then packages="$packages tesseract-lang"; break; fi
  done
  # shellcheck disable=SC2086  # (a list of package names)
  run brew install $packages
}

system_apt() {
  local sudo=""
  if [ "$(id -u)" -ne 0 ]; then
    if have sudo; then sudo="sudo"; else
      note "Installing system packages needs root, and sudo is not here; skipping them."
      return
    fi
  fi
  local packages="libimage-exiftool-perl ffmpeg tesseract-ocr ghostscript python3-venv"
  local lang
  for lang in $LANGUAGES; do
    [ "$lang" = "eng" ] || packages="$packages tesseract-ocr-$lang"
  done
  if [ "$ASSUME_YES" -eq 0 ] && [ "$DRY" -eq 0 ] && [ -t 0 ]; then
    printf '    Install with apt: %s? [Y/n] ' "$packages"
    local answer
    read -r answer || answer=""
    case "$answer" in [nN]*) note "Skipped."; return ;; esac
  fi
  run $sudo apt-get update
  # shellcheck disable=SC2086
  run $sudo apt-get install -y $packages
}

if [ "$SYSTEM" -eq 1 ]; then
  say "System programs (ExifTool, FFmpeg, OCRmyPDF's Tesseract and Ghostscript; languages: $LANGUAGES)"
  case "$(uname -s)" in
    Darwin) system_mac ;;
    Linux)
      if have apt-get; then system_apt; else
        note "No apt here: install exiftool, ffmpeg, tesseract (with: $LANGUAGES) and"
        note "ghostscript with your package manager. Caixa works without them, with less."
      fi ;;
    *) note "$(uname -s) is not tried; install exiftool, ffmpeg, tesseract and ghostscript by hand." ;;
  esac
else
  say "System programs: left alone (--no-system)"
fi

# --- 2. Python and its virtual environment ------------------------------------------------------

say "Python"
if [ -z "$PYTHON" ]; then
  if [ -x "$VENV/bin/python" ]; then PYTHON="$VENV/bin/python"; else PYTHON="python3"; fi
fi
if ! have "$PYTHON"; then
  echo "install.sh: $PYTHON was not found; install Python 3.10 or newer (on a Mac: brew install python)." >&2
  exit 1
fi
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "install.sh: Caixa needs Python 3.10 or newer; $PYTHON is $("$PYTHON" --version 2>&1)." >&2
  exit 1
fi
note "$("$PYTHON" --version 2>&1) ($(command -v "$PYTHON"))"

if [ -x "$VENV/bin/python" ]; then
  note "Using the virtual environment at $VENV"
else
  run "$PYTHON" -m venv "$VENV"
fi
PIP="$VENV/bin/python -m pip"

# --- 3. Chattr, then Caixa ----------------------------------------------------------------------

say "Chattr and Caixa"
EXTRAS="ocr"
[ "$DEV" -eq 1 ] && EXTRAS="ocr,dev"
# shellcheck disable=SC2086  # ($PIP is a command and its argument)
run $PIP install --upgrade pip
# shellcheck disable=SC2086
run $PIP install -e "$ROOT/tools/chattr" -e "$ROOT[$EXTRAS]"

# --- 4. For development: the window's packages --------------------------------------------------

if [ "$DEV" -eq 1 ]; then
  say "The window's Node packages (for its tests and builds)"
  if ! have node; then
    note "Node.js is not installed: the window's tests need it (https://nodejs.org, or brew install node)."
    note "Caixa itself runs without it: the window comes ready-built with Caixa."
  else
    if ! have pnpm && have corepack; then run corepack enable; fi
    if have pnpm || [ "$DRY" -eq 1 ]; then
      run pnpm --dir "$ROOT/web" install
      note "For the end-to-end tests, Playwright's Chromium: pnpm --dir web exec playwright install chromium"
    else
      note "pnpm is not available; install it (npm install -g pnpm), then: pnpm --dir web install"
    fi
  fi
fi

# --- 5. Check ------------------------------------------------------------------------------------

say "Checking"
if [ "$DRY" -eq 1 ]; then
  note "(dry run: nothing was installed)"
  exit 0
fi
"$VENV/bin/caixa" --version
"$VENV/bin/caixa" doctor || true

if [ "$(uname -s)" = "Darwin" ]; then
  note ""
  note "Apple Intelligence: Caixa builds its helper the first time you choose it in Settings."
  note "That needs Xcode 26 or its command-line tools (xcode-select --install)."
fi

cat <<EOF

Done. Start using Caixa with:

    source "$VENV/bin/activate"
    caixa serve --box ~/Our\\ Box

EOF
