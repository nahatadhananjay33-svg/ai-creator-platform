#!/usr/bin/env bash
# =============================================================================
# dev — the standard command to run after (re)connecting VS Code.
#
# Opens a persistent tmux session named "dev" and starts Claude Code in it.
# If the session already exists (e.g. after a disconnect), it just re-attaches
# — your Claude session and any long jobs are exactly where you left them.
# When Claude exits, the pane drops to a shell so the session stays alive.
#
# Usage:  dev
# =============================================================================
set -uo pipefail

SESSION="${DEV_SESSION:-dev}"
REPO="${CHECKPOINT_REPO:-/content/ai-creator-platform}"

# Start the session in the repo dir if it exists (tmux inherits this cwd).
cd "$REPO" 2>/dev/null || true

# -A: attach if the session exists, else create it and run the command.
# The command only runs on creation; on re-attach it is ignored.
exec tmux new-session -A -s "$SESSION" 'claude || true; exec bash'
