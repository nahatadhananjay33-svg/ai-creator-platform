#!/usr/bin/env bash
# =============================================================================
# colab_watchdog.sh — keep sshd + the active tunnel transport alive.
#
# Transport-agnostic. The bootstrap writes two small scripts per mode:
#   /content/tunnel_healthy.sh  → exit 0 if the transport is actually serving
#   /content/tunnel_up.sh       → (re)start the transport, wait until it serves
# The watchdog just polls health and calls up.sh when unhealthy — so it works
# identically for quick tunnels, named Cloudflare tunnels, and VS Code tunnels.
#
# Launched in the background by the bootstrap. Single instance via flock.
# =============================================================================
set -uo pipefail

SSH_PORT="${SSH_PORT:-2222}"
WLOG="/content/watchdog.log"
HEALTHY="/content/tunnel_healthy.sh"
UP="/content/tunnel_up.sh"

exec 9>/tmp/colab_watchdog.lock
flock -n 9 || { echo "watchdog: another instance is already running"; exit 0; }

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$WLOG"; }

log "watchdog started (sshd:${SSH_PORT})"
while true; do
  # --- sshd (used by quick/named modes; harmless to keep alive in vscode mode) -
  if ! { pgrep -x sshd >/dev/null 2>&1 && ss -ltnH "sport = :$SSH_PORT" 2>/dev/null | grep -q ":$SSH_PORT"; }; then
    log "sshd down -> restarting"
    /usr/sbin/sshd 2>>"$WLOG" || log "sshd restart returned non-zero"
  fi

  # --- tunnel transport (mode-agnostic via the bootstrap-written scripts) ------
  if [ -x "$HEALTHY" ] && [ -x "$UP" ]; then
    if ! bash "$HEALTHY" 2>/dev/null; then
      log "transport unhealthy -> restarting via tunnel_up.sh"
      if bash "$UP" >>"$WLOG" 2>&1; then
        log "transport restarted; host=$(cat /content/tunnel_hostname.txt 2>/dev/null || echo n/a)"
      else
        log "transport restart did not confirm within its timeout"
      fi
    fi
  fi

  sleep 20
done
