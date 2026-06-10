#!/usr/bin/env bash
# Setup for 10-judge-evaluation — installs deps, pushes the LLM-judge policy,
# and verifies it landed in the controlplane.
#
# Follows the canonical policy-example setup pattern from 04-policy-block-pii.
#
# Idempotent: re-running is safe.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/../.." && pwd)"

# 1. Verify repo-root .env has both required keys
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
  source "$REPO_ROOT/scripts/_make-venv.sh"
  make_venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet --pre -r requirements.txt

# 3. Push the policy — hard-fail on error (never silently skip)
echo ""
echo "pushing policies.py to Waxell controlplane..."
if ! wax policies push "$DIR/policies.py"; then
  echo "" >&2
  echo "error: 'wax policies push' failed — the policy was NOT seeded." >&2
  echo "       Check that WAXELL_API_KEY is valid and the controlplane is reachable." >&2
  exit 1
fi

# 4. Confirm the policy landed
echo ""
echo "verifying example-tone-judge is registered..."
if ! wax policies list --format=json | grep -q "example-tone-judge"; then
  echo "" >&2
  echo "error: 'example-tone-judge' not found after push." >&2
  echo "       Run 'wax policies list' manually to inspect." >&2
  exit 1
fi
echo "  confirmed: example-tone-judge is active."

# 5. Run instructions
echo ""
echo "ready. run with:"
echo "  source $DIR/.venv/bin/activate"
echo "  python $DIR/agent.py"
echo ""
echo "to see the judge in action, try:"
echo "  you> I want a refund for my broken laptop that arrived damaged."
echo ""
echo "after a run, inspect it with:"
echo "  wax runs list --limit 5"
echo "  wax runs show <run-id>"
echo ""
echo "open the Governance panel in the Waxell UI to read the judge's score"
echo "and reasoning for each turn."
