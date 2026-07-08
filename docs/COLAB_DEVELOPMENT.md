# Colab Development Environment

Resilient remote-dev setup: **Windows VS Code → Cloudflare tunnel → Google Colab → Claude Code**,
working on `/content/ai-creator-platform`.

The design assumes the connection *will* drop (free Cloudflare quick tunnels have no SLA;
Colab reclaims idle runtimes). The goal is that a drop costs little or no work:

- **`tmux`** keeps `claude` and long jobs running when SSH/VS Code disconnects — you reattach.
- **`checkpoint`** pushes your work to GitHub so it survives even a full runtime reclaim.
- **watchdog** keeps `sshd` + the tunnel alive and records any new hostname.
- **`recover`** tells you, after any disconnect, exactly what survived and what to do.

The bootstrap notebook is **self-contained and self-healing**: it bakes in the
`checkpoint`/`recover`/`dev`/watchdog scripts (so they exist on any branch, even before
the repo is cloned), installs only what's missing, and re-running only repairs what broke.
The notebook is version-controlled at [`notebooks/colab_bootstrap.ipynb`](../notebooks/colab_bootstrap.ipynb);
upload that file to a fresh runtime (it must exist before the clone).

---

## 0. Tunnel modes — pick your transport

Set the **`TUNNEL_MODE`** Colab Secret (or env var). Default is `quick`. This is the lever
for the "constant timeouts" problem — `quick` is convenient but flaky; `named` and `vscode`
are stable.

| Mode | Stability | Setup | How you connect |
|---|---|---|---|
| `quick` (default) | low — new random hostname each runtime, quick tunnels drop | none | Remote-SSH `colab`, paste the printed PowerShell line each time |
| `named` | high — **fixed** hostname, production Cloudflare tunnel | one-time Cloudflare setup (below) | Remote-SSH `colab`, set `HostName` **once** — never changes |
| `vscode` | high — Microsoft-hosted, no hostname at all | one-time GitHub device login per runtime | **Remote-Tunnels: Connect to Tunnel…** (no SSH, no PowerShell) |

**`named` (stable Cloudflare tunnel) — one-time setup.** Requires a Cloudflare account with a
domain on Cloudflare. In the Zero Trust dashboard → Networks → Tunnels → *Create a tunnel*
(Cloudflared), name it, copy the **token**, and add a **Public Hostname** route (e.g.
`colab.yourdomain.com`) with service **SSH → `localhost:2222`**. Then add two Colab Secrets:
`CF_TUNNEL_TOKEN` = the token, `CF_TUNNEL_HOSTNAME` = `colab.yourdomain.com`, and set
`TUNNEL_MODE=named`. Your `~/.ssh/config` `HostName` is that domain **forever** — no more
per-session updates.

**`vscode` (VS Code Tunnels) — no account setup.** Set `TUNNEL_MODE=vscode`. The cell prints
a `https://github.com/login/device` URL + code; authorize once (per runtime). Then in VS Code:
Command Palette → *Remote-Tunnels: Connect to Tunnel…* → `colab-dev` (override the name with
the `VSCODE_TUNNEL_NAME` secret). No cloudflared, no SSH config, no hostname to chase. This is
the least-fuss way to end the timeouts if you don't have a Cloudflare domain.

Under every mode you still get `dev` / `checkpoint` / `recover` and the watchdog (which is
transport-agnostic — it restarts whatever tunnel you chose).

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
4. In the VS Code terminal, start your session — `dev` opens tmux **and starts Claude**:
   ```bash
   dev            # attaches the "dev" tmux session, or creates it running claude
   ```

> `dev` is the one command to run after every (re)connect. It launches Claude inside tmux,
> so a disconnect leaves it (and any long jobs) running — you just run `dev` again to
> reattach instead of losing the process. When Claude exits, the pane drops to a shell so
> the session stays alive.

The expected end-of-bootstrap summary:

```
=====================================
Environment Ready
SSH ............. OK
Tunnel .......... OK
Claude .......... OK
GPU ............. OK
CUDA ............ OK
Git ............. OK
Branch .......... main
Commit .......... <hash>
Checkpoint ...... OK
Recover ......... OK
Dev ............. OK
Watchdog ........ OK
=====================================
```

---

## 2. Reconnect procedure (tunnel still alive)

If VS Code drops but the Colab runtime is still running:

1. In VS Code: **Remote-SSH: Connect to Host… → colab** again. If it hangs, run
   **Remote-SSH: Kill VS Code Server on Host…**, then reconnect.
2. Open a terminal and reattach your session:
   ```bash
   dev            # your claude session is exactly where you left it
   ```
   (Optionally run `recover` first to confirm SSH/Tunnel/Git/Claude/GPU.)

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

### `websocket: bad handshake`

This means cloudflared reached Cloudflare's edge but there is **no live tunnel** registered
for that hostname — the quick tunnel died at the edge while its process kept running (a
"zombie"). The fix is always the same: **re-run the bootstrap cell**. It now kills any
existing tunnel and starts a fresh one, waiting until it is actually *edge-registered*
(`Registered tunnel connection`) before printing the hostname — so the hostname it gives you
is guaranteed live. Then paste the new PowerShell line and reconnect. (The watchdog also
now restarts a never-registered zombie automatically.)

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
| Packages | `openssh-server git curl wget tmux nodejs npm cloudflared uv python` — installed only if missing |
| SSH | `sshd` on port 2222, key-only root, env propagated (`LD_LIBRARY_PATH`, PATH) so `nvidia-smi`/`claude` work in SSH shells |
| Tunnel | Cloudflare quick tunnel → `ssh://127.0.0.1:2222`; hostname in `/content/tunnel_hostname.txt` (reused if already alive) |
| GPU/CUDA | Verifies `nvidia-smi` in a clean SSH-login shell, reports driver CUDA version and base-env `torch.cuda.is_available()` (best-effort; torch lives in per-model `.venvs`) |
| Claude | Installed if missing; verified with `claude --version` |
| Repo | Cloned or `fetch` + `pull` at `/content/ai-creator-platform`; identity set to `Dhananjay Nahata <nahatadhananjay33@gmail.com>` (override via `GIT_USER_NAME`/`GIT_USER_EMAIL`) |
| Commands | `checkpoint`, `recover`, `dev` **baked into the notebook** and written to `/usr/local/bin` unconditionally (no repo dependency) |
| Watchdog | `/usr/local/bin/colab_watchdog.sh` — restarts sshd/tunnel if they die, records new hostname; single instance via `flock` |

Everything is idempotent — re-running the bootstrap never duplicates config or stacks
processes.
