# Notebook Architecture — Unified Colab Development Environment

Generated: 2026-07-17. The two-notebook workflow (`colab_bootstrap.ipynb` +
`tanshi_voice_cloning_setup.ipynb`) is now **one** notebook:
[notebooks/tanshi_voice_cloning_setup.ipynb](notebooks/tanshi_voice_cloning_setup.ipynb).
`colab_bootstrap.ipynb` (kept outside the repo) is superseded — its bootstrap cell was merged
**byte-exactly**, so nothing about the proven infra changed.

## Design

**Run All** produces, in order: a debuggable remote-dev plane → a validated voice-cloning
environment → an optional benchmark smoke test → an optional (guarded) fine-tune. Sections are
strictly modular — infrastructure knows nothing about training and vice versa; any section can
be re-run alone.

| # | Cell(s) | Section | Notes |
| --- | --- | --- | --- |
| 0 | md | Title + section map | |
| 1–2 | md + code | **1 · Infrastructure** (INFRA 2.0 bootstrap, verbatim) | apt/ssh/tunnel/Claude/GPU/git/`checkpoint·recover·dev`/watchdog. Placed **first** deliberately: if any later cell fails, the SSH tunnel is already up and the error can be debugged from VS Code/Claude on the runtime instead of copy-pasting from Colab. |
| 3 | md | **Remote Development** how-to | connect VS Code, open repo, `dev` for Claude Code; full detail in [REMOTE_DEVELOPMENT_GUIDE.md](REMOTE_DEVELOPMENT_GUIDE.md). |
| 4–10 | md + code | **2 · Voice cloning environment** | unchanged original cells: CONFIG (`MODEL` is the only edit) → Drive mount → repo clone/pull + system deps (ffmpeg) → dataset discovery → CUDA/torch/ffmpeg checks + **manifest-verified dataset integrity** → readiness summary. |
| 11–12 | md + code | **3 · Benchmark validation (T2)** | `setup_benchmark --model $MODEL --device cuda`; artifacts to Drive `benchmark_runs/<model>/`. |
| 13–14 | md + code | **4 · Fine-tuning (T3, guarded)** | `production.f5_finetune.run`; **dry-run unless `START_TRAINING = True`**; optional per-checkpoint evaluator side-process. Training pipeline itself untouched by this phase. |

## Idempotency (requirement 3) — where each guarantee lives

| Resource | Mechanism |
| --- | --- |
| apt/system packages | bootstrap probes binaries/`dpkg -s` before installing; ffmpeg cell checks `shutil.which` |
| Node/cloudflared/uv/Claude/VS Code CLI | presence + version probes; install only when missing |
| sshd / tunnel / watchdog | verify-then-repair; tunnel restarted only when unhealthy; watchdog single-instance via `flock` |
| Repo | `git pull --ff-only` when present, clone only when absent |
| Python envs | per-model `.venvs/<model>` reused when import-verification passes (`InstallationManager`); rebuilt only when broken |
| Model weights | Hugging Face cache — downloads are skipped on cache hits |
| Fine-tune state | checkpoints on Drive; trainer auto-resumes from `model_last.pt` |
| Dataset | never written — only read + checksum-verified against the committed manifest |

## Why the bootstrap stays one big embedded cell

It is the proven INFRA 2.0 cell (used across prior phases): self-contained (helper scripts
base64-baked so it works before/without the repo), self-healing, and transport-agnostic
(quick/named/vscode tunnel modes behind one watchdog contract). Splitting it into many small
cells would create partial-run states — exactly what its verify-and-repair design avoids.
Merging was done byte-exactly and every code cell is `ast.parse`-verified.

## Interactive prompts during Run All (unavoidable, by platform design)

1. Drive mount consent (Google popup, Section 2).
2. `vscode` tunnel mode only: one-time GitHub device-login code (printed by the cell).
Everything else runs unattended.
