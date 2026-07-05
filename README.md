# AI Creator Platform

A modular platform for AI-driven content generation and voice AI. It is built
as a set of independent **engines** on top of a shared **foundation**, so each
capability (voice, avatar, script, captions, reels) can be researched,
benchmarked, and productionised without entangling the others.

**Target use cases**

- Instagram Reels / YouTube video generation
- Talking-avatar videos and digital influencers
- Real-estate voice AI agents (calls, WhatsApp voice)
- Multilingual content (English / Hindi / Hinglish / Bengali)

> **Model stack status (as of Phase A3.6):** the production model stack is
> **not yet frozen** — it is blocked on a GPU benchmark pass that adequate
> hardware can run. The *framework* is production-ready; only the final model
> selection awaits measured GPU data. See
> [`docs/PRODUCTION_STACK.md`](docs/PRODUCTION_STACK.md) and
> [`docs/PHASE_A36_REPORT.md`](docs/PHASE_A36_REPORT.md).

---

## Folder architecture

| Path | Purpose |
| --- | --- |
| `foundation/` | Shared production infrastructure: config, logging, caching, model manager, hardware/environment probing, benchmarking runner, reporting, shared utils. Every engine depends on this and nothing else. |
| `voice_engine/` | Voice cloning / TTS: adapters, multilingual datasets, benchmark, evaluation, reporting, streaming, pronunciation, cloning. |
| `avatar_engine/` | Talking avatars: face generation, lip sync, motion, image consistency, model research catalog, benchmark + evaluation. |
| `script_engine/` | Script generation (planned). |
| `caption_engine/` | Captioning (planned). |
| `reel_engine/` | Automatic reel assembly (planned). |
| `export/` | Final media export (planned). |
| `benchmark/` | Cross-engine benchmark entry points. |
| `demos/`, `notebooks/` | Exploration only — never imported by production code. |
| `docs/` | Platform architecture, phase reports, hardware & production-stack docs. |
| `.venvs/` | Per-model isolated virtual environments (git-ignored, machine-local). |
| `archive/` | Superseded/regenerable reports (git-ignored). |

**Engineering rules** (kept from Phase A1):

1. Engines depend on `foundation/`, never on each other's internals — only on
   published interfaces (`*_engine/interfaces/`).
2. No benchmark-only code: benchmarks orchestrate real production modules.
3. Configuration-driven: behaviour changes via YAML in `foundation/config/`
   and engine configs, not code edits.
4. Heavy ML dependencies are optional extras; the core installs and tests
   without a GPU or any model weights.

---

## Completed phases

| Phase | Title | Outcome |
| --- | --- | --- |
| **A1** | Voice Cloning Research & Platform Foundation | Foundation + Voice Engine research/benchmark framework; multilingual datasets; single- vs dual-model recommendation. |
| **A1.5** | Model Integration, Installation & Scientific Validation | Real voice adapters installed into isolated venvs; CPU-measured validation. |
| **A2** | Production Voice Engine (readiness) | Verdict: ready to start; reuse map defined. |
| **A3.5** | Avatar Model Installation & Scientific Validation | Avatar framework + real adapters (SadTalker, LivePortrait); one real CPU generation path (SadTalker, offline batch). |
| **A3.6** | GPU Validation & Production Stack Freeze | **Blocked by hardware** — the available GPU (GTX 1050, 3 GB, driver 451.67) is not CUDA-usable and below every model's VRAM/RAM floor. No GPU benchmark could run; production stack not frozen. Framework confirmed sound. |

Full reports live in [`docs/`](docs/).

---

## Current roadmap

1. **Complete the A3.6 GPU freeze** on adequate hardware (see below): run the
   existing voice + avatar suites `--device cuda`, then freeze the production
   stack from measured data.
2. **Phase A4 — Production Avatar Engine**: begins once at least one avatar
   model has a measured GPU benchmark (identity / lip-sync / motion / long-form).
3. **Phase A5 — Reel assembly**: compose voice + avatar + captions into reels.

The framework and benchmark suites are ready to run unchanged the moment a
CUDA-usable GPU is available — no code changes are required to produce the
missing measurements.

---

## Setup instructions

Requires **Python ≥ 3.10**.

```bash
# from repo root
python -m venv .venv                 # or: uv venv
source .venv/Scripts/activate        # Windows Git Bash; use .venv/bin/activate on Linux/macOS
pip install -e .[dev]                # core has NO heavy ML deps

pytest                               # verify: full suite green, no GPU needed
python -m voice_engine.scripts.run_benchmark --adapters mock --languages en
```

### Check what this machine can run

The platform probes hardware and reports per-model compatibility before you
install any weights:

```bash
python -m voice_engine.scripts.install_models  --all --report-only
python -m avatar_engine.scripts.install_models --report-only
```

This prints your GPU / driver / VRAM / RAM and, for every model, whether it
resolves to `gpu`, `cpu`, `cpu-offline`, or `none`.

### GPU / model installs

- CUDA model installs require an NVIDIA driver **≥ 452.39** (the CUDA 11.8
  floor). On older drivers the probe reports `CUDA usable: no`.
- Install PyTorch from the CUDA index matching your driver, e.g.
  `--index-url https://download.pytorch.org/whl/cu118`.
- Per-model venvs under `.venvs/` are **machine-bound** (built against a
  specific base Python) and are git-ignored — **rebuild them after cloning**
  or moving machines. Do not copy `.venvs/` between machines.

---

## Google Colab usage

Colab provides the CUDA-capable GPU this project needs for benchmarking and
avatar generation.

```python
# 1. Clone (private repo: use a token or the GitHub CLI)
!git clone https://github.com/<your-username>/<your-repo>.git
%cd <your-repo>

# 2. Confirm the GPU + driver
!nvidia-smi

# 3. Install the core (no heavy deps yet)
!pip install -e .[dev]

# 4. Probe compatibility on Colab's GPU
!python -m voice_engine.scripts.install_models --all --report-only
!python -m avatar_engine.scripts.install_models --report-only

# 5. Install the models the probe cleared, then benchmark on GPU
!python -m voice_engine.scripts.run_benchmark  --adapters <cleared> --device cuda \
    --languages en hi hi-en bn
!python -m avatar_engine.scripts.run_benchmark --adapters <cleared> --device cuda
```

Notes:
- Colab GPUs (T4 16 GB / L4 / A100) clear far more of the catalogue than a
  local 3 GB card — this is the recommended path to complete the A3.6 freeze.
- Colab storage is ephemeral: `.venvs/`, weights, and `*/output/` are all
  git-ignored and will not persist. Re-run installs each session, or mount
  Google Drive for caches.
- Generated media and benchmark `output/` are regenerable and intentionally
  not committed — download the reports you want to keep.

---

## Future development plan

- **Freeze the production model stack** from measured GPU benchmarks (voice:
  real-time / quality / lightweight; avatar: production / lightweight /
  high-end), then mark [`docs/PRODUCTION_STACK.md`](docs/PRODUCTION_STACK.md)
  FROZEN.
- **Build the Production Avatar Engine** (Phase A4) on the frozen stack.
- **Reel assembly** (Phase A5): orchestrate voice + avatar + captions + export.
- **Multi-GPU / deployment**: data-parallel serving of many short jobs when
  multi-GPU hardware is procured (see
  [`docs/MULTI_GPU_COMPATIBILITY_REPORT.md`](docs/MULTI_GPU_COMPATIBILITY_REPORT.md));
  distributed inference is documented but intentionally not yet implemented.

---

## Key documents

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — platform architecture and phase reuse map
- [docs/PHASE_A36_REPORT.md](docs/PHASE_A36_REPORT.md) — latest phase: GPU validation findings
- [docs/HARDWARE_COMPATIBILITY_REPORT.md](docs/HARDWARE_COMPATIBILITY_REPORT.md) — measured per-model hardware verdicts
- [docs/PRODUCTION_STACK.md](docs/PRODUCTION_STACK.md) — production stack (currently NOT frozen)
- [voice_engine/docs/INSTALLATION.md](voice_engine/docs/INSTALLATION.md) — model installation guide
