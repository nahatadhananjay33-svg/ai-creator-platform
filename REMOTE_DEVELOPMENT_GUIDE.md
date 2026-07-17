# Remote Development Guide — VS Code + Claude Code on Colab

The unified notebook ([notebooks/tanshi_voice_cloning_setup.ipynb](notebooks/tanshi_voice_cloning_setup.ipynb))
turns a Colab runtime into a full remote dev box: after **Run All**, you edit in VS Code and run
Claude Code *on the runtime itself* — no more copying errors between Colab and a local Claude.

## 0. One-time setup (already done if you used this before)

- `~/.ssh/config` on Windows contains the `Host colab` block (port 2222, key
  `~/.ssh/colab_ed25519`, `cloudflared access ssh` ProxyCommand). The matching public key is
  baked into the notebook's bootstrap cell.
- `cloudflared.exe` installed on Windows (`C:\Program Files (x86)\cloudflared\`).
- Recommended Colab **Secrets**: `GITHUB_TOKEN` (lets `checkpoint` push), optionally
  `TUNNEL_MODE`, `CF_TUNNEL_TOKEN`, `CF_TUNNEL_HOSTNAME`, `VSCODE_TUNNEL_NAME`.

## 1. Per-runtime flow

1. Open the notebook in Colab → Runtime → **T4 GPU** → **Run All**.
2. The Section 1 cell prints connect instructions when it finishes:
   - **quick mode** (default): paste the printed PowerShell one-liner (updates the
     `HostName …trycloudflare.com` line in `~/.ssh/config` — the hostname changes every
     runtime; this is the #1 gotcha).
   - **named mode**: hostname is stable; nothing to update after the first time.
   - **vscode mode**: no SSH at all — use *Remote-Tunnels: Connect to Tunnel…*.
3. Verify: `ssh colab whoami` → `root`.

## 2. Connect VS Code

- Command Palette → **Remote-SSH: Connect to Host…** → `colab`
  (or **Remote-Tunnels: Connect to Tunnel…** in vscode mode).
- **File → Open Folder** → `/content/ai-creator-platform`.
- If the connection was working and drops: the runtime probably rotated or the tunnel died.
  Re-run the bootstrap cell (it self-heals), update the hostname if quick mode, reconnect.

## 3. Claude Code on the runtime

In the VS Code terminal:

```bash
dev            # tmux session "dev" + Claude Code, in the repo directory
```

- `claude` runs **on the Colab machine**: it sees the T4, the venvs, the logs, the Drive
  mount — it can run `setup_benchmark`, tail training logs, and fix errors in place.
- tmux means a dropped SSH/browser connection does NOT kill Claude or a running job —
  reconnect and run `dev` again to re-attach exactly where you were.
- `recover` — read-only status report after any disconnect (sshd, tunnel, repo, GPU, Claude).
- `checkpoint "message"` — commit + push the working tree so nothing dies with the runtime.
  Requires the `GITHUB_TOKEN` Secret; without it commits stay local (and are lost on reclaim).

## 4. Troubleshooting

| Symptom | Cause → fix |
| --- | --- |
| `Failed to parse remote port` / `websocket: bad handshake` | Stale `HostName` in `~/.ssh/config` (new runtime = new trycloudflare hostname). Paste the printed one-liner again. |
| `nvidia-smi: couldn't find libnvidia-ml.so` over SSH | SSH shell missing the kernel env — re-run the bootstrap cell (it re-propagates PATH/LD_LIBRARY_PATH). |
| `claude: command not found` over SSH | Same env issue as above; bootstrap re-run fixes it. |
| Tunnel dies mid-session | The watchdog restarts it within ~20 s; if the hostname rotated (quick mode), update `~/.ssh/config`. |
| Long job killed on disconnect | It wasn't inside tmux. Always launch long jobs via `dev` (or `tmux`). |
| `checkpoint` says push failed | No/expired `GITHUB_TOKEN` Secret. Fix the token, re-run `checkpoint`. |

## 5. Idempotency contract

Re-running the bootstrap (or the whole notebook) at any time is safe: every step
verifies-then-repairs — packages install only if missing, the SSH key appends only once,
the tunnel restarts only if unhealthy, the repo pulls instead of recloning, venvs and HF
model caches are reused, and the watchdog replaces itself under a lock.
