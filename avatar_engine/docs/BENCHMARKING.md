# Avatar Benchmarking Guide

How to run, extend, and interpret the avatar benchmark. The framework is
the same composition pattern as the voice benchmark: generic
`foundation.benchmarking` primitives + avatar scenarios + avatar metrics.

## Quick start

```bash
# Wiring check with the mock adapter (runs anywhere, no GPU):
python -m avatar_engine.scripts.run_benchmark

# Real run on a GPU machine (Phase A4, once adapters land):
python -m avatar_engine.scripts.run_benchmark \
    --adapters sadtalker echomimic-v3 latentsync --human-eval-sheet

# Static research comparison (no benchmark needed):
python -m avatar_engine.scripts.generate_research_report
```

Outputs land in `avatar_engine/output/runs/<run-id>/`:
`results_detail.csv`, `results_summary.csv`, `run_full.json`,
`run_summary.json`, `report.md`, generated videos under `video/`, and
(with `--human-eval-sheet`) the blind rating sheet + confidential key.

## Architecture

| Layer | Module | Responsibility |
|---|---|---|
| Cases | `benchmark/scenarios.py` | one adapter × one scenario × one repetition |
| Orchestration | `benchmark/orchestrator.py` | case building, asset resolution, reports |
| Runner | `foundation.benchmarking` | timing, resource monitoring, error isolation |
| Metrics | `evaluation/` | frame stats, identity, lip sync, human protocol |
| Reports | `reporting/` + `foundation.reporting` | CSV / JSON / Markdown |

Adapters that raise `AdapterNotAvailableError` are recorded **SKIPPED**
with the reason — a run over the full roster is always safe; unimplemented
or uninstalled models simply skip.

## Metrics: automatic vs human

Automatic (`source="auto"`, computed in `evaluation/`):

- Performance: `generation_time_s`, `real_time_factor`, `output_fps`,
  resolution, `peak_rss_mb`, `peak_gpu_mem_mb`.
- Frame statistics (any machine): `mean_frame_difference`,
  `flicker_index`, `frozen_frame_ratio`, `mean_sharpness`,
  `sharpness_drift`, `mean_brightness`.
- Optional backends (GPU machine):
  - `identity_similarity` / `identity_drift` — ArcFace cosine vs source
    portrait (`pip install .[face-id]`). InsightFace models are
    research-only: fine for benchmarking, swap the embedder for
    production checks.
  - `lip_sync_confidence` / `lip_sync_distance` — SyncNet LSE-C/LSE-D
    analogs. Setup: clone `joonson/syncnet_python`, place
    `syncnet_v2.model` under `foundation/cache/data/model_weights/syncnet/`.
    The interface is frozen; the pipeline call lands with the first GPU
    run.

Human (`source="human"`, collected via `AvatarHumanEvalProtocol`):
`mos_lip_sync`, `mos_expression`, `mos_head_movement`,
`mos_motion_realism`, `mos_identity`, `mos_video_quality`, `mos_uncanny`,
`mos_overall` — blind, ≥3 raters, audio on, Hindi clips scored by Hindi
speakers. Reports never mix the two sources silently; research priors are
labeled `static`.

## Scenarios

Defined in `datasets/data/scenarios.yaml` (10 scenarios, 9 categories).
Each declares its `evaluation_focus` so reports can slice results by what
a scenario was designed to stress. Missing assets are auto-replaced by
placeholders (sine WAV + gray PNG) unless `--no-placeholders` — placeholder
runs validate wiring only, never quote their metrics.

## Adding a new model later

1. Add its research profile to `research/catalog.py` (+ a research note).
2. Add an `InstallSpec` to `models/install_specs.py`.
3. Implement an adapter subclassing `BaseAvatarAdapter` (three `_impl`
   hooks) and register it in `models/registry.py` — replacing the
   auto-generated planned placeholder.
4. Run the benchmark; every report picks it up unchanged.
