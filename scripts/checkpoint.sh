#!/usr/bin/env bash
# =============================================================================
# checkpoint.sh — lightweight "save my work" for Colab dev sessions.
#
# Commits ONLY if the working tree changed, with a timestamped message, then
# pushes to origin so the work survives a Colab runtime reclaim (which wipes
# /content, taking local-only commits with it).
#
# Usage:   checkpoint "LatentSync installer progress"
#          checkpoint                       # uses a default message
#
# Exit codes: 0 = clean or committed+pushed, 2 = committed but push failed.
# Safe to run repeatedly. Respects .gitignore (never stages .venvs/, logs, etc).
# =============================================================================
set -uo pipefail

# Resolve repo root: prefer the current git repo, else the Colab default.
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  REPO="$(git rev-parse --show-toplevel)"
else
  REPO="${CHECKPOINT_REPO:-/content/ai-creator-platform}"
fi
cd "$REPO" 2>/dev/null || { echo "checkpoint: cannot cd to repo '$REPO'"; exit 1; }

MSG="${*:-checkpoint}"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"

# Nothing to do if the tree is clean.
if [ -z "$(git status --porcelain)" ]; then
  echo "checkpoint: working tree clean — nothing to commit ($REPO)"
  exit 0
fi

# Ensure a commit identity exists (fallback if the bootstrap didn't set one).
git config user.name  >/dev/null 2>&1 || git config user.name  "${GIT_USER_NAME:-Colab Dev}"
git config user.email >/dev/null 2>&1 || git config user.email "${GIT_USER_EMAIL:-colab-dev@users.noreply.github.com}"

git add -A
if ! git commit -q -m "checkpoint: ${MSG} (${STAMP})"; then
  echo "checkpoint: commit failed"; exit 1
fi
HASH="$(git rev-parse --short HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "checkpoint: committed ${HASH} on ${BRANCH} — ${MSG}"

# Push (best-effort). Needs a credential; see docs/COLAB_DEVELOPMENT.md.
if git push -q origin "HEAD:${BRANCH}" 2>/tmp/checkpoint_push_err; then
  echo "checkpoint: pushed ${HASH} -> origin/${BRANCH}  ✓ work is safe off-runtime"
  exit 0
else
  echo "checkpoint: ⚠ PUSH FAILED — commit ${HASH} is LOCAL ONLY and will be lost"
  echo "checkpoint:   if this Colab runtime is reclaimed. Fix auth, then re-run 'checkpoint'."
  sed 's/^/checkpoint:   /' /tmp/checkpoint_push_err 2>/dev/null
  echo "checkpoint:   see docs/COLAB_DEVELOPMENT.md > 'GitHub push auth'."
  exit 2
fi
