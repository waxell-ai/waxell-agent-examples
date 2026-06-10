#!/usr/bin/env bash
# Helper: create a .venv in the calling directory using a Python the
# Waxell SDK has a published wheel for. waxell-observe is Cython-compiled
# and only ships cp312 / cp313 wheels today — newer Pythons (3.14+) get
# "No matching distribution found".
#
# Usage from a per-example setup.sh:
#   source "$REPO_ROOT/scripts/_make-venv.sh"
#   make_venv                       # creates .venv/ in cwd if missing
set -euo pipefail

make_venv() {
  if [[ -d .venv ]]; then
    return 0
  fi
  local py
  for py in python3.13 python3.12; do
    if command -v "$py" >/dev/null 2>&1; then
      "$py" -m venv .venv
      return 0
    fi
  done
  echo "error: need python3.13 or python3.12 in PATH." >&2
  echo "       your default python3 is $(python3 --version 2>&1 | awk '{print $2}')." >&2
  echo "       waxell-observe has no pypi wheel for python 3.14+ yet." >&2
  echo "       install via:  brew install python@3.13" >&2
  exit 1
}
