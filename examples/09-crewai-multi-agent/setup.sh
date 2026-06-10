#!/usr/bin/env bash
# Setup for 09-crewai-multi-agent — installs deps. No policies needed.
#
# Idempotent: re-running is safe.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/../.." && pwd)"

# 1. Verify repo-root .env has Waxell creds + the keys this example needs
if [[ ! -f "$REPO_ROOT/.env" ]]; then
  echo "error: $REPO_ROOT/.env missing." >&2
  echo "       run $REPO_ROOT/scripts/seed-env-from-wax.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1091
set -a; source "$REPO_ROOT/.env"; set +a
[[ -n "${WAXELL_API_KEY:-}" ]] || { echo "error: WAXELL_API_KEY empty in .env" >&2; exit 1; }
[[ -n "${OPENAI_API_KEY:-}" ]] || { echo "error: OPENAI_API_KEY empty in .env — add it and re-run" >&2; exit 1; }

# 2. Per-example venv
cd "$DIR"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# 3. No policies for this example.

echo ""
echo "ready. run with:"
echo "  source $DIR/.venv/bin/activate"
echo "  python $DIR/agent.py"
echo ""
echo "after a few turns, see the runs land:"
echo "  wax runs list --limit 5"
