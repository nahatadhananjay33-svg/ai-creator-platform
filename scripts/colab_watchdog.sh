#!/usr/bin/env bash
# =============================================================================
# colab_watchdog.sh — keep sshd + the Cloudflare tunnel alive.
#
# Launched in the background by the bootstrap notebook. Every 20s it checks
# that sshd is listening and cloudflared is running; if either died it restarts
# it. When the tunnel restarts it gets a NEW *.trycloudflare.com hostname — the
# watchdog records it to /content/tunnel_hostname.txt and /content/watchdog.log
# so you can update ~/.ssh/config and reconnect.
#
# Single instance enforced via flock, so re-running the bootstrap won't stack
# multiple watchdogs.
# =============================================================================
set -uo pipefail

SSH_PORT="${SSH_PORT:-2222}"
LOG="/content/cloudflared.log"
HOSTFILE="/content/tunnel_hostname.txt"
WLOG="/content/watchdog.log"

exec 9>/tmp/colab_watchdog.lock
flock -n 9 || { echo "watchdog: another instance is already running"; exit 0; }

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$WLOG"; }

# Start a tunnel and wait until it is actually EDGE-REGISTERED, not just named.
# A named-but-unregistered tunnel returns "websocket: bad handshake" to clients.
start_tunnel() {
  pkill -f 'cloudflared tunnel' 2>/dev/null || true
  sleep 2
  : >"$LOG"
  nohup cloudflared tunnel --no-autoupdate --url "ssh://127.0.0.1:${SSH_PORT}" \
        --logfile "$LOG" --loglevel info >/dev/null 2>&1 &
  local h="" reg=""
  for _ in $(seq 1 60); do
    [ -z "$h" ] && h="$(grep -oE '[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | tail -1)"
    grep -q 'Registered tunnel connection' "$LOG" 2>/dev/null && reg=1
    if [ -n "$h" ] && [ -n "$reg" ]; then
      echo "$h" >"$HOSTFILE"
      log "tunnel up + registered: $h"
      return 0
    fi
    sleep 1
  done
  [ -n "$h" ] && echo "$h" >"$HOSTFILE"
  log "tunnel restart incomplete: hostname=${h:-none} registered=${reg:-no}"
  return 1
}

log "watchdog started (sshd:${SSH_PORT})"
while true; do
  # sshd
  if ! { pgrep -x sshd >/dev/null 2>&1 && ss -ltnH "sport = :$SSH_PORT" 2>/dev/null | grep -q ":$SSH_PORT"; }; then
    log "sshd down -> restarting"
    /usr/sbin/sshd 2>>"$WLOG" || log "sshd restart returned non-zero"
  fi
  # cloudflared — restart if the process is gone, OR if it is alive but never
  # registered with the edge (a zombie that would serve "bad handshake").
  if ! pgrep -f 'cloudflared tunnel' >/dev/null 2>&1; then
    old="$(cat "$HOSTFILE" 2>/dev/null || echo none)"
    log "tunnel down (was ${old}) -> restarting"
    start_tunnel && log "NEW HOSTNAME $(cat "$HOSTFILE") — update ~/.ssh/config on Windows and reconnect"
  elif ! grep -q 'Registered tunnel connection' "$LOG" 2>/dev/null; then
    log "cloudflared alive but never edge-registered (zombie) -> restarting"
    start_tunnel && log "NEW HOSTNAME $(cat "$HOSTFILE") — update ~/.ssh/config on Windows and reconnect"
  fi
  sleep 20
done
