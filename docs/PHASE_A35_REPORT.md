# Phase A3.5 Report — Avatar Model Installation & Scientific Validation

**Date:** 2026-07-05 · **Hardware:** Intel i7-6700HQ-class (8 logical cores),
15.9 GB RAM, GTX 960M 4 GB (driver 398.35 — CUDA unusable), Windows 10.
All measurements below are **CPU-only** real executions archived under
`avatar_engine/output/`. Research-based statements are labeled *research*.

## 1. Installation results (candidate list + A3 extras)

| Model | Outcome | Reason / evidence |
| --- | --- | --- |
| **SadTalker** | ✅ Installed + validated + **benchmarked** | 4 real videos generated; pins: torch 2.0.1/tv 0.15.2 (cpu), numpy 1.23.5+numba 0.58.1 (facexlib `np.float`), setuptools<81 (pkg_resources), checkpoints HF `vinthony/SadTalker-V002rc` (the plain repo 404s the safetensors) |
| **LivePortrait** | ⚠️ Installed; **Not Tested to completion** | insightface built; weights fetched (HF KwaiVGI/LivePortrait); CPU generation of a ~5 s clip **exceeded the 60-min timeout** (measured) — GPU required |
| **EchoMimic V3** | ⏸ Not Tested | deps installable, but 1.3B video-diffusion inference is not CPU-viable; awaits A4 GPU (research: 6.5 GB VRAM floor) |
| **MuseTalk** | ❌ Not Supported (this host) | mmcv/mmpose compiled deps fail on native Windows — WSL2/Linux path documented |
| **InfiniteTalk** | ❌ Not Supported (this host) | Wan2.1-14B stack: flash-attn build + ≥12 GB VRAM floor; far beyond this machine |
| LatentSync, EchoMimic V2, Ditto, Hallo2, MEMO, FantasyTalking, OmniAvatar (A3 extras) | ❌ Not Supported (this host) | compiled deps / VRAM floors; specs encode reasons |

Framework changes (all reusable, no duplication): shared install CLI moved
to `foundation.model_manager.install_cli` (voice + avatar wrappers), repo
clone + checkpoint prefetch support in `InstallationManager`, FFmpeg
auto-pathing promoted to `foundation.shared_utils.ffmpeg`, real adapters
(`sadtalker.py`, `liveportrait.py`) replacing planned placeholders, and an
avatar `ModelValidator` + `validate_models` script.

## 2. Measured validation

| Model | Load | First generation | Output | RTF (CPU) |
| --- | --- | --- | --- | --- |
| SadTalker | 0.01 s (subprocess model) | 1137.8 s for 4.12 s video | 256×256@25fps, playable | 276 |
| LivePortrait | 0.0 s | timeout > 3600 s | none | not measurable |

## 3. Measured benchmark (run `avatar-bench-20260704-191049-3dafa8`)

Real assets: portraits from the SadTalker example set; **driving audio is
real Kokoro speech** synthesized by the platform Voice Engine from each
scenario script (10 scenario WAVs, EN + HI) — no placeholder tones.
4/4 cases PASSED, solo run (no competing load):

| Scenario | Video | Gen time | RTF | Flicker | Frozen frames | Sharpness |
| --- | --- | --- | --- | --- | --- | --- |
| neutral-intro-en | 8.24 s | 2316 s | 281.1 | 0.496 | 0.0% | 8.27 |
| neutral-pricing-en | 7.40 s | 1843 s | 249.0 | 0.544 | 0.0% | 8.31 |
| hindi-welcome-hi | 9.20 s | 2215 s | 240.8 | 0.511 | 0.44% | 8.32 |
| silence-pauses-en | 4.12 s | 1026 s | 249.1 | 0.577 | 0.0% | 8.36 |

Observations (measured): stable RTF (241–281) across scenarios; sharpness
uniform (8.27–8.36 → no quality collapse over time); motion present in all
outputs (frozen-frame ≈ 0); **Hindi audio drives the model without
failure**. Generated videos: `avatar_engine/output/runs/<run>/video/*.mp4`
+ validation smoke video.

**Measurement gaps (honest):**
- *Identity similarity and lip-sync confidence were not measured* — their
  optional backends (InsightFace/SyncNet-class) are not installed in the
  sadtalker venv; the evaluator omitted them rather than fake them.
  Perceptual lip-sync/expression quality therefore awaits the A4 human
  eval + GPU metric pass.
- `peak_rss_mb` (~220 MB) covers the orchestrating process only; the
  generation subprocess's memory is not captured by the in-process monitor.
  Fixing this (child-process sampling) is a known A4 item.
- No comparative quality ranking is possible: exactly one model completed
  the benchmark on this hardware.

## 4. Rankings (measured-only; unbenchmarked models are not ranked)

| Category | Verdict |
| --- | --- |
| Best overall / production / identity / lip-sync / realism | **Not rankable** — one model benchmarked; comparative rankings require the A4 GPU pass |
| Best CPU-compatible model | **SadTalker** — the only candidate that produced video on CPU (measured; offline batch only at RTF ≈ 255) |
| Best lightweight model | SadTalker (2.4 GB checkpoints, 256² mode) — by default of being the only measured runner |
| Best GPU model / long-form model | Not measurable on this host — *research* points to EchoMimic V3 (quality) and InfiniteTalk (unbounded length), unverified |

## 5. Known issues (reproduced this phase)

1. SadTalker dependency archaeology: 4 pins required (documented in install_specs.py with reasons); the stack is 2023-frozen — treat as legacy baseline, not a foundation.
2. LivePortrait CPU path exists upstream (`--flag_force_cpu`) but is not practically usable (>60 min for ~5 s).
3. Avatar repos assume ffmpeg/ffprobe on PATH — now auto-injected platform-wide.
4. HF checkpoint layouts drift (SadTalker safetensors moved repos) — prefetch code pins the verified repo.

## 6. Final engineering answers (measured basis only)

**1. Move into the Production Avatar Engine:** SadTalker — the only model
with a measured end-to-end success on platform infrastructure — as the
*interim offline baseline*; LivePortrait and EchoMimic V3 advance to the A4
GPU evaluation (installed / deps-ready respectively, quality unmeasured).

**2. Discard:** nothing on quality grounds — no comparative quality data
exists. Discard *from the native-Windows path*: MuseTalk, InfiniteTalk and
the Wan-family stacks (measured/verified install blockers); they remain
WSL2-GPU candidates only if A4 procurement materializes. InfiniteTalk is
additionally deprioritized (*research*: 14B/multi-GPU class) as mismatched
with the platform's hardware budget.

**3. Default production avatar model:** cannot be named from measurements —
only SadTalker completed, and its 2023-era stack + RTF 255 on CPU make it a
stopgap, not a default. Decision deferred to the A4 GPU benchmark (the
framework runs unchanged there). Until then SadTalker is the *only*
supported generation path.

**4. Lightweight local generation:** SadTalker 256² CPU mode (measured:
~4-9 s clips in 17-39 min) — usable for occasional offline renders, not
interactive work.

**5. High-end cloud rendering:** *research, not measured*: EchoMimic V3
(quality/VRAM balance) first, InfiniteTalk (long-form) second — both
explicitly pending real A4 measurements before any commitment.

## Artifacts

- Installation + compatibility: `avatar_engine/output/installs/`
- Validation JSONs + smoke video: `avatar_engine/output/validation/`
- Benchmark run (CSV/JSON/MD + 4 videos): `avatar_engine/output/runs/avatar-bench-20260704-191049-3dafa8/`
- Real scenario audio (Kokoro): `avatar_engine/datasets/data/assets/*.wav`
