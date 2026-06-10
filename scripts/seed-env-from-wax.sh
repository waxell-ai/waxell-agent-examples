#!/usr/bin/env bash
# Seed .env from your local wax profile.
#
# Reads ~/.waxell/config (the file `wax config show` reports), pulls the
# api_key + api_url from the chosen profile, and writes them into the
# repo-root .env. Provider keys (OPENAI_API_KEY etc.) are preserved if
# the .env already exists — only the WAXELL_* lines are overwritten.
#
# Usage:
#   ./scripts/seed-env-from-wax.sh                # uses [default] profile
#   ./scripts/seed-env-from-wax.sh my-profile     # uses [my-profile]
#
# Output: .env at the repo root. The script will NOT overwrite without
# asking if .env already has a non-empty WAXELL_API_KEY.
set -euo pipefail

PROFILE="${1:-default}"
CONFIG_FILE="${WAXELL_CONFIG_FILE:-$HOME/.waxell/config}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
ENV_EXAMPLE="$REPO_ROOT/.env.example"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "error: wax config not found at $CONFIG_FILE" >&2
  echo "run \`wax setup\` first, then re-run this script." >&2
  exit 1
fi

# Walk the INI file by hand — no python/jq dependency.
api_key=""
api_url=""
in_profile=0
while IFS= read -r line; do
  trimmed="${line%%#*}"                          # strip trailing comments
  trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"  # ltrim
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"  # rtrim
  [[ -z "$trimmed" ]] && continue
  if [[ "$trimmed" =~ ^\[(.+)\]$ ]]; then
    [[ "${BASH_REMATCH[1]}" == "$PROFILE" ]] && in_profile=1 || in_profile=0
    continue
  fi
  (( in_profile )) || continue
  if [[ "$trimmed" =~ ^([A-Za-z_]+)[[:space:]]*=[[:space:]]*(.+)$ ]]; then
    key="${BASH_REMATCH[1]}"
    val="${BASH_REMATCH[2]}"
    case "$key" in
      api_key) api_key="$val" ;;
      api_url) api_url="$val" ;;
    esac
  fi
done < "$CONFIG_FILE"

if [[ -z "$api_key" ]]; then
  echo "error: profile [$PROFILE] in $CONFIG_FILE has no api_key" >&2
  echo "available profiles:" >&2
  grep -E '^\[.+\]$' "$CONFIG_FILE" | sed 's/^/  /' >&2
  exit 1
fi
[[ -z "$api_url" ]] && api_url="https://api.waxell.dev"

# Preserve any provider keys in an existing .env — only overwrite WAXELL_*
if [[ -f "$ENV_FILE" ]]; then
  existing_key="$(grep -E '^WAXELL_API_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  if [[ -n "$existing_key" && "$existing_key" != "$api_key" ]]; then
    echo "warning: $ENV_FILE already has a different WAXELL_API_KEY (${existing_key:0:12}…)"
    read -rp "overwrite with profile [$PROFILE] key (${api_key:0:12}…)? [y/N] " yn
    [[ "$yn" =~ ^[Yy]$ ]] || { echo "aborted."; exit 0; }
  fi
  # Replace existing WAXELL_* lines in place, leave everything else alone
  tmp="$(mktemp)"
  awk -v k="$api_key" -v u="$api_url" '
    /^WAXELL_API_KEY=/ { print "WAXELL_API_KEY=" k; next }
    /^WAXELL_API_URL=/ { print "WAXELL_API_URL=" u; next }
    { print }
  ' "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
else
  # Seed from the template, then patch the WAXELL_* lines.
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  awk -v k="$api_key" -v u="$api_url" '
    /^WAXELL_API_KEY=/ { print "WAXELL_API_KEY=" k; next }
    /^WAXELL_API_URL=/ { print "WAXELL_API_URL=" u; next }
    { print }
  ' "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
fi

# Restrict permissions — the file holds a secret
chmod 600 "$ENV_FILE"

echo "wrote $ENV_FILE from wax profile [$PROFILE]"
echo "  WAXELL_API_KEY=${api_key:0:12}…${api_key: -4}"
echo "  WAXELL_API_URL=$api_url"
echo ""
echo "next: add provider keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, …) to $ENV_FILE"
echo "      see each example's README for which keys it needs."
