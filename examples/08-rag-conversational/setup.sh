#!/usr/bin/env bash
# Setup for 08-rag-conversational — installs deps. No policies needed.
#
# What this installs:
#   waxell-observe  — instrumentation SDK
#   openai          — LLM + embeddings (text-embedding-3-small)
#   numpy           — cosine similarity for in-memory retrieval
#   python-dotenv   — .env loading
#
# Idempotent: re-running is safe.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DIR/../.." && pwd)"

# 1. Verify repo-root .env has required keys
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

# 3. No policies for this example — retrieval data is recorded so a policy
#    COULD be added later (e.g. require relevance_score >= 0.70), but the
#    example ships without one to keep the focus on retrieval recording.

echo ""
echo "ready. run with:"
echo "  source $DIR/.venv/bin/activate"
echo "  python $DIR/agent.py"
echo ""
echo "after a few turns, see the runs land:"
echo "  wax runs list --limit 5"
