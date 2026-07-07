#!/usr/bin/env bash
# =============================================================================
# recover.sh — crash / reconnect diagnostics for the Colab dev environment.
#
# READ-ONLY: inspects state and prints a report. Changes nothing.
# Run this first thing after a disconnect to see what survived and what to do.
#
# Usage:  recover
# =============================================================================
set -uo pipefail

REPO="${CHECKPOINT_REPO:-/content/ai-creator-platform}"
SSH_PORT="${SSH_PORT:-2222}"

g="\033[32m"; r="\033[31m"; y="\033[33m"; n="\033[0m"
ok()   { printf "%-14s ${g}OK${n}   %s\n"   "$1" "${2:-}"; }
bad()  { printf "%-14s ${r}FAIL${n} %s\n"   "$1" "${2:-}"; }
note() { printf "%-14s ${y}·${n}    %s\n"   "$1" "${2:-}"; }

echo "======== Colab dev recovery check ========"

# --- SSH ---------------------------------------------------------------------
if pgrep -x sshd >/dev/null 2>&1 && ss -ltnH "sport = :$SSH_PORT" 2>/dev/null | grep -q ":$SSH_PORT"; then
  ok "SSH" "sshd listening on $SSH_PORT"
else
  bad "SSH" "sshd not listening on $SSH_PORT — re-run the bootstrap cell"
fi

# --- Tunnel ------------------------------------------------------------------
if pgrep -f 'cloudflared tunnel' >/dev/null 2>&1; then
  H="$(cat /content/tunnel_hostname.txt 2>/dev/null)"
  [ -z "$H" ] && H="$(grep -oE '[a-z0-9-]+\.trycloudflare\.com' /content/cloudflared.log 2>/dev/null | tail -1)"
  ok "Tunnel" "${H:-running (hostname unknown — check /content/cloudflared.log)}"
  [ -n "$H" ] && echo "               → if VS Code can't connect, set ~/.ssh/config HostName to: $H"
else
  bad "Tunnel" "cloudflared not running — re-run the bootstrap cell"
fi

# --- Repo / branch / git -----------------------------------------------------
if [ -d "$REPO/.git" ]; then
  cd "$REPO"
  ok   "Repo" "$REPO"
  note "Branch" "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
  note "Commit" "$(git rev-parse --short HEAD 2>/dev/null) $(git log -1 --pretty=%s 2>/dev/null)"
  if [ -n "$(git status --porcelain)" ]; then
    note "Uncommitted" "YES — save it now:  checkpoint \"wip\""
    git status -s | sed 's/^/               /'
  else
    note "Uncommitted" "none (working tree clean)"
  fi
  git fetch -q origin >/dev/null 2>&1 || true
  AHEAD="$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo '?')"
  if [ "$AHEAD" = "0" ]; then
    note "Unpushed" "none — origin is up to date"
  else
    note "Unpushed" "${AHEAD} local commit(s) not on origin — run:  checkpoint"
  fi
else
  bad "Repo" "$REPO missing — re-run the bootstrap cell to clone"
fi

# --- Claude ------------------------------------------------------------------
if command -v claude >/dev/null 2>&1; then
  ok "Claude" "$(claude --version 2>/dev/null | head -1)"
else
  bad "Claude" "not on PATH — re-run the bootstrap cell"
fi

# --- GPU (as a fresh SSH login shell would see it) ---------------------------
if env -i bash -lc 'nvidia-smi -L' >/dev/null 2>&1; then
  ok "GPU" "$(env -i bash -lc 'nvidia-smi -L' 2>/dev/null | head -1)"
else
  note "GPU" "none visible (CPU runtime, or env not propagated — re-run bootstrap)"
fi

echo "=========================================="
echo "Tip: run long jobs and 'claude' inside tmux ('dev') so disconnects don't kill them."
