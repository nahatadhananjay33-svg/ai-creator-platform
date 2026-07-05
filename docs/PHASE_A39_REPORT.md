# Phase A3.9 Report — LivePortrait Completion & Benchmark

**Date:** 2026-07-06 · **Scope:** complete the existing LivePortrait
integration so it becomes a runnable, benchmarked model. LivePortrait only —
no MuseTalk/EchoMimic, no framework/adapter/installer redesign.

## Architecture (unchanged)

LivePortrait plugs into the existing avatar stack: a per-model venv (installer),
a subprocess-dispatch adapter (A3.7 venv-aware validation), the shared
benchmark → evaluation → reporting pipeline. This phase only *completed the
missing pieces* around that stack.

## Root cause

The adapter reported `missing files: liveportrait` because:

1. **Weights were never downloaded.** The LivePortrait install spec cloned the
   repo but had no `prefetch_code` (unlike SadTalker), so
   `pretrained_weights/` was empty.
2. **Availability checked only a directory.** `required_paths()` looked for
   `pretrained_weights/liveportrait` — not the actual weight files — so the
   diagnostic was vague.
3. **The benchmark never fed it a driving video.** LivePortrait is *video*-
   driven, but the case only passed `driving_audio`; the framework's existing
   `GenerationRequest.driving_video` field was never populated.

## Fix (measured, from upstream — not guessed)

- **Weight manifest** `avatar_engine/models/liveportrait_weights.py`: the exact
  8 humans-mode files from HF `KlingTeam/LivePortrait` +
  `assets/docs/directory-structure.md` (see `docs/LIVEPORTRAIT.md` for the
  table). Single source of truth for installer, adapter, and diagnostics.
- **Installer**: LivePortrait spec gains `prefetch_code` that downloads each
  weight via `hf_hub_download` (resumable, cached, skips valid — never
  redownloads). No installer redesign; reuses the existing `prefetch_code` hook.
- **Verification**: `check_weights()` → validated / missing / corrupted /
  checksum_mismatch per file; `weights_to_download()` returns only invalid
  files. Script `validate_liveportrait_weights.py` →
  `liveportrait_weights_report.{md,json}`.
- **Adapter**: `required_paths()` now returns `inference.py` + every weight, so
  the A3.7 diagnostic names the specific missing weight. Added `weight_report()`.
- **Driving-video plumbing**: `AvatarScenario.driving_video`,
  `ResolvedAssets.driving_video`, `resolve_assets` resolution, and the case now
  passes `driving_video` (audio-driven models ignore it). The orchestrator skips
  a video-driven model's scenarios with a clear reason when no driving clip is
  present — using the same benchmark path, no separate execution route.
- **Comparison**: `avatar_engine/reporting/comparison.py` +
  `compare_models.py` aggregate the latest run per model into
  `model_comparison_report.{md,json}` (measured metrics only).
- **Notebook**: fresh Colab → **Run All** installs LivePortrait, downloads +
  validates weights, seeds a driving clip, validates CUDA, runs the benchmark,
  and generates the comparison — no manual commands.

## Benchmark results

Measured GPU numbers (generation time, RTF, FPS, VRAM, GPU util/temp,
resolution, duration, output size, success rate + the framework's evaluation
metrics) are produced by the Colab **T4** run and written to
`model_comparison_report.md`. They are **not** included here because this
repository host has no CUDA-capable GPU (GTX 1050, driver below the CUDA 11.8
floor, per A3.6) — fabricating them would violate the project's measured-only
rule. The notebook emits them automatically on Colab.

Verified on the dev host (no GPU needed):
- Weight manifest, verification (missing/corrupted/checksum/skip-valid), and the
  prefetch snippet.
- Adapter availability now names the specific missing weight.
- Driving-video plumbing: LivePortrait scenarios skip with a clear reason when
  no clip is present, and run when one is.
- Comparison report renders both models side by side.
- Notebook is valid and contains every Run-All step.

## Limitations

- **LivePortrait is video-driven, not audio-driven.** It uses the same source
  portraits and scenarios as SadTalker plus a shared driving clip; it does not
  lip-sync to the scenario speech, so audio lip-sync metrics are only meaningful
  for SadTalker. The comparison is honest about this and reports measured
  performance/quality, not a lip-sync verdict for LivePortrait.
- Measured benchmark/comparison numbers require the Colab run (this host cannot
  execute CUDA).
- InsightFace detection weights are research-only (documented) — production use
  requires replacing the detection stack.

## Future work

- Per-file SHA256 in the manifest for exact (not size-band) integrity.
- Per-scenario driving clips (vs one shared clip) if motion diversity matters.
- An audio-driven talking-head front-end if lip-sync-to-audio is required from
  LivePortrait (out of scope here).

## Regression

14 pre-existing avatar suites + **20 new tests** (`test_liveportrait.py`,
`test_notebook_smoke.py`) covering weight validation, missing/corrupted/checksum
detection, download-skip (resume) semantics, adapter availability, driving-video
plumbing, comparison, and the notebook smoke test. Full suite green.
