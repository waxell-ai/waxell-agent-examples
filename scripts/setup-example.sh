#!/usr/bin/env bash
# Set up a single example: create a venv, install its requirements.txt,
# and verify the .env at repo root has WAXELL_API_KEY.
#
# Usage:
#   ./scripts/setup-example.sh 01-hello-waxell
#   ./scripts/setup-example.sh examples/01-hello-waxell  # also fine
#
# After this finishes, activate the venv and run the example:
#   source examples/01-hello-waxell/.venv/bin/activate
#   python examples/01-hello-waxell/agent.py
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <example-name>" >&2
  echo "available examples:" >&2
  ls -1 "$(dirname "${BASH_SOURCE[0]}")/../examples" 2>/dev/null | sed 's/^/  /' >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="${1#examples/}"
DIR="$REPO_ROOT/examples/$NAME"

if [[ ! -d "$DIR" ]]; then
  echo "error: example not found at $DIR" >&2
  exit 1
fi
if [[ ! -f "$DIR/requirements.txt" ]]; then
  echo "error: $DIR has no requirements.txt" >&2
  exit 1
fi
if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "error: $REPO_ROOT/.env missing. Run ./scripts/seed-env-from-wax.sh first." >&2
  exit 1
fi
if ! grep -qE '^WAXELL_API_KEY=.+' "$REPO_ROOT/.env"; then
  echo "error: WAXELL_API_KEY is empty in $REPO_ROOT/.env" >&2
  echo "run ./scripts/seed-env-from-wax.sh to populate it" >&2
  exit 1
fi

cd "$DIR"
if [[ ! -d .venv ]]; then
  echo "creating venv at $DIR/.venv"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo ""
echo "ready. to run:"
echo "  source $DIR/.venv/bin/activate"
echo "  python $DIR/agent.py"
echo ""
echo "see $DIR/README.md for what to look for in the Waxell UI."
