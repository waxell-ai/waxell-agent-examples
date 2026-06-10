#!/usr/bin/env bash
# Setup for 04-policy-block-pii — installs deps, pushes the PII block policy,
# and verifies it landed in the controlplane.
#
# This is the CANONICAL policy-example setup pattern — 05, 08, and 10 copy it.
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
echo "verifying example-pii-block is registered..."
if ! wax policies list --format=json | grep -q "example-pii-block"; then
  echo "" >&2
  echo "error: 'example-pii-block' not found after push." >&2
  echo "       Run 'wax policies list' manually to inspect." >&2
  exit 1
fi
echo "  confirmed: example-pii-block is active."

# 5. Run instructions
echo ""
echo "ready. run with:"
echo "  source $DIR/.venv/bin/activate"
echo "  python $DIR/agent.py"
echo ""
echo "to trigger the PII block, type something like:"
echo "  you> Hi, my SSN is 123-45-6789, can you look up my account?"
echo ""
echo "after a run, inspect it with:"
echo "  wax runs list --limit 5"
echo "  wax runs show <run-id>"
