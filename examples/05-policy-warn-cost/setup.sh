#!/usr/bin/env bash
# Setup for 05-policy-warn-cost — venv, deps, and policy push.
#
# Idempotent: re-running is safe.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/../.." && pwd)"

# 1. Verify repo-root .env has Waxell creds + OpenAI key
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

# 3. Push the cost-warn policy
echo "pushing policies..."
wax policies push policies.py

# 4. Verify the policy landed
echo "verifying policy..."
wax policies list | grep "example-cost-warn" \
  && echo "  policy 'example-cost-warn' is active." \
  || { echo "warning: policy not found after push — check 'wax policies list'" >&2; }

echo ""
echo "ready. run with:"
echo "  source $DIR/.venv/bin/activate"
echo "  python $DIR/agent.py"
echo ""
echo "to trigger the cost warning, try a verbose prompt like:"
echo "  you> write me a 500-word gothic horror story set in a lighthouse"
echo ""
echo "after each turn you can inspect runs:"
echo "  wax runs list --limit 3"
echo "  wax runs show <id>    # Governance panel shows warning incident"
