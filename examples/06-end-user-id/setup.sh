#!/usr/bin/env bash
# Setup for 06-end-user-id — installs deps, seeds two demo end-users with
# wildly different per-user budgets, and pushes the end-user-budget policy
# that enforces them. Idempotent: re-running is safe.
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
  source "$REPO_ROOT/scripts/_make-venv.sh"
  make_venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet --pre -r requirements.txt

# 3. Seed two demo end-users with very different monthly budget caps.
#    The cap value lives on the WaxellUser row; the policy below just
#    turns enforcement on. --budget is monthly_budget_cap_cents (an
#    integer in CENTS). Idempotent — skip when the user already exists.
ensure_end_user() {
  local id="$1"
  local budget_cents="$2"
  local display="$3"
  # `wax end-users lookup <id> --format=json` always returns
  # `{"results": {"<id>": <uuid-or-null>}}` — null means the user
  # doesn't exist yet. Probe via python so the parse is unambiguous.
  if wax end-users lookup "$id" --format=json 2>/dev/null \
      | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('results',{}).get('$id') else 1)" \
      2>/dev/null; then
    echo "  end-user '$id' already exists — leaving budget as-is."
  else
    echo "  creating end-user '$id' with budget=${budget_cents}¢..."
    wax end-users create \
      --tenant-sub-user-id "$id" \
      --email "$id" \
      --display-name "$display" \
      --budget "$budget_cents" \
      --format=json > /dev/null
  fi
}
echo "seeding demo end-users..."
ensure_end_user "alice@example.com"  100000 "Alice (unlimited)"   # $1000/mo
ensure_end_user "bob@example.com"    1      "Bob (tiny budget)"    # 1¢/mo

# 4. Push the end-user-budget policy.
echo "pushing policies.py to Waxell controlplane..."
wax policies push policies.py

# 5. Verify both end-users + the policy are live.
echo "verifying end-users..."
wax end-users list --format=json | grep -qE "alice@example.com" \
  && echo "  alice@example.com OK" \
  || { echo "warning: alice not found after create" >&2; }
wax end-users list --format=json | grep -qE "bob@example.com" \
  && echo "  bob@example.com OK" \
  || { echo "warning: bob not found after create" >&2; }

echo "verifying policy..."
wax policies list --format=json | grep -q "example-end-user-budget" \
  && echo "  policy 'example-end-user-budget' is active." \
  || { echo "warning: policy not found after push — check 'wax policies list --format=json'" >&2; }

echo ""
echo "ready. run with:"
echo "  source $DIR/.venv/bin/activate"
echo "  python $DIR/agent.py"
echo ""
echo "demo sequence to try in the REPL:"
echo "  /switch alice@example.com   → ask a few questions (unlimited budget)"
echo "  /switch bob@example.com     → ask one question (still under 1¢)"
echo "                               → ask another  → BLOCKED (cap exhausted)"
echo "  /switch alice@example.com   → still works (her budget is separate)"
echo ""
echo "see each user's runs separately:"
echo "  wax end-users runs --tenant-sub-user-id alice@example.com --limit 5"
echo "  wax end-users runs --tenant-sub-user-id bob@example.com --limit 5"
