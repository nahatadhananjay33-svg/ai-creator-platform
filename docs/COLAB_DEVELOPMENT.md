# Colab Development Environment

Resilient remote-dev setup: **Windows VS Code → Cloudflare tunnel → Google Colab → Claude Code**,
working on `/content/ai-creator-platform`.

The design assumes the connection *will* drop (free Cloudflare quick tunnels have no SLA;
Colab reclaims idle runtimes). The goal is that a drop costs little or no work:

- **`tmux`** keeps `claude` and long jobs running when SSH/VS Code disconnects — you reattach.
- **`checkpoint`** pushes your work to GitHub so it survives even a full runtime reclaim.
- **watchdog** keeps `sshd` + the tunnel alive and records any new hostname.
- **`recover`** tells you, after any disconnect, exactly what survived and what to do.

---

## 1. Normal startup

1. Start a fresh Colab runtime, upload/open **`colab_bootstrap.ipynb`**, run the one cell.
2. It prints a readiness summary and a **PowerShell one-liner**. On Windows, paste it — it
   updates `HostName` in `~/.ssh/config` to this session's tunnel hostname.
3. Verify and connect:
   ```powershell
   ssh colab whoami        # expect: root
   ```
   Then in VS Code: **Remote-SSH: Connect to Host… → colab**.
4. In the VS Code terminal, start a persistent session and launch Claude inside it:
   ```bash
   dev            # attaches (or creates) the tmux session named "dev"
   claude         # run Claude Code INSIDE tmux
   ```

> Always run `claude` and long-running commands inside `dev` (tmux). A disconnect then
> leaves them running; you reattach with `dev` instead of losing the process.

The expected end-of-bootstrap summary:

```
SSH ............ OK
Tunnel ......... OK
Git ............ OK
Claude ......... OK
GPU ............ OK
```

---

## 2. Reconnect procedure (tunnel still alive)

If VS Code drops but the Colab runtime is still running:

1. In VS Code: **Remote-SSH: Connect to Host… → colab** again. If it hangs, run
   **Remote-SSH: Kill VS Code Server on Host…**, then reconnect.
2. Open a terminal and reattach your session:
   ```bash
   dev            # your claude session is exactly where you left it
   recover        # optional: confirm SSH/Tunnel/Git/Claude/GPU
   ```

No work is lost — the processes kept running inside tmux.

---

## 3. Crash recovery (after any disconnect)

Run the diagnostics first — it's read-only and tells you what to do:

```bash
recover
```

It reports **SSH / Tunnel / Repo / Branch / Commit / uncommitted work / unpushed commits /
Claude / GPU**. Act on what it flags:

- `SSH FAIL` or `Tunnel FAIL` → re-run the bootstrap cell in Colab.
- `Uncommitted: YES` → run `checkpoint "wip"` immediately.
- `Unpushed: N commit(s)` → run `checkpoint` (it will push).
- Tunnel hostname changed → see §4.

If the **Colab runtime itself was reclaimed** (`/content` is gone): start a new runtime,
re-run the bootstrap (re-clones + `git pull`), and your last **pushed** checkpoint is on
GitHub. Anything only committed locally (never pushed) is gone — which is why `checkpoint`
pushes.

---

## 4. Updating the tunnel hostname

Free quick tunnels get a **new random hostname** whenever cloudflared restarts (new runtime,
or the watchdog restarting a dead tunnel). Find the current hostname on Colab:

```bash
cat /content/tunnel_hostname.txt        # written by the watchdog / bootstrap
```

On Windows, point `~/.ssh/config` at it (the bootstrap prints this line ready to paste):

```powershell
$new = "THE-hostname.trycloudflare.com"
(Get-Content $HOME\.ssh\config) -replace '^(\s*HostName\s+).*trycloudflare\.com', "`$1$new" | Set-Content $HOME\.ssh\config -Encoding ascii
```

Then `ssh colab whoami` and reconnect VS Code.

---

## 5. Checkpoint workflow

Save work early and often — especially before risky steps:

```bash
checkpoint "LatentSync installer progress"
```

Behavior:
- **Skips** if the working tree is clean (no empty commits).
- Otherwise `git add -A` (respects `.gitignore` — never stages `.venvs/`, logs, weights),
  commits with a timestamped message, and **pushes to origin**.
- If push fails (no credential), it still commits locally and **warns loudly** that the
  work will be lost on a runtime reclaim until you fix auth.

A good rhythm: `checkpoint` after each working sub-step, and always before ending a session.

### GitHub push auth

`checkpoint` pushes over HTTPS, which needs a credential on Colab. Pick one:

- **Colab Secret (recommended).** Create a GitHub **Personal Access Token** (fine-grained,
  `Contents: read/write` on this repo). In Colab's left sidebar → **🔑 Secrets**, add
  `GITHUB_TOKEN` = your token, and enable notebook access. The bootstrap reads it via
  `google.colab.userdata` and configures git's credential store for the session.
- **Env var.** Before running the bootstrap: `import os; os.environ["GITHUB_TOKEN"]="ghp_…"`.
- **No token.** `checkpoint` commits locally only and warns — acceptable only if you accept
  losing work on a runtime reclaim.

The token is written to `~/.git-credentials` on the ephemeral Colab disk and is **never**
committed. Revoke it from GitHub any time.

---

## 6. What the bootstrap configures

| Area | Detail |
|---|---|
| Packages | `openssh-server git curl wget nodejs npm cloudflared tmux` — installed only if missing |
| SSH | `sshd` on port 2222, key-only root, env propagated (`LD_LIBRARY_PATH`, PATH) so `nvidia-smi`/`claude` work in SSH shells |
| Tunnel | Cloudflare quick tunnel → `ssh://127.0.0.1:2222`; hostname in `/content/tunnel_hostname.txt` |
| Watchdog | `scripts/colab_watchdog.sh` — restarts sshd/tunnel if they die, records new hostname |
| Claude | Installed if missing; verified with `claude --version` |
| Repo | Cloned or `git pull` at `/content/ai-creator-platform` |
| Commands | `checkpoint`, `recover`, `dev` installed to `/usr/local/bin` |

Everything is idempotent — re-running the bootstrap never duplicates config or stacks
processes.
