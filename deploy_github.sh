#!/usr/bin/env bash
# Create a NEW GitHub repo and push this codebase.
# The token is read from $GH_TOKEN (a PAT with 'repo' scope) — never hardcoded,
# never committed. Usage:  GH_TOKEN=ghp_xxx ./deploy_github.sh [repo-name]
set -euo pipefail

REPO="${1:-lyrisee}"
VIS="${GH_VISIBILITY:-public}"   # public | private
: "${GH_TOKEN:?Set GH_TOKEN (GitHub PAT with 'repo' scope) in the environment}"

echo "[1/3] Authenticating gh with provided token ..."
echo "$GH_TOKEN" | gh auth login --with-token
gh auth status

echo "[2/3] Creating repo '$REPO' ($VIS) and pushing ..."
gh repo create "$REPO" --"$VIS" \
  --source=. --remote=origin --push \
  --description "Lyrisee — AI kinetic-typography lyric-video engine + Director pipeline"

echo "[3/3] Done. Repo URL:"
gh repo view --json url -q .url
