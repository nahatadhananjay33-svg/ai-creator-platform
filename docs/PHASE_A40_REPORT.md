# Phase A4.0 Report — MuseTalk Integration

**Date:** 2026-07-06 · **Scope:** integrate MuseTalk into the existing avatar
benchmark framework, reusing the SadTalker/LivePortrait pattern exactly.
MuseTalk only — no EchoMimic; no framework/adapter/installer/reporting redesign
(only extension).

## Architecture (unchanged, extended)

MuseTalk plugs into the same stack as SadTalker/LivePortrait: an isolated
per-model venv (installer), a subprocess-dispatch adapter (A3.7 venv-aware
diagnostics), and the shared benchmark → evaluation → reporting pipeline. This
phase added a real adapter, a completed install spec, a weight manifest, a
weight validator, comparison inclusion, notebook steps, tests, and docs —
nothing structural changed.

## Changes

- **Adapter** `avatar_engine/models/musetalk.py` — `MuseTalkAdapter`, audio-driven
  (`source_image` + `driving_audio` → `GenerationResult`, exactly like
  SadTalker). MuseTalk's inference is config-yaml driven, so the adapter writes
  a temporary task YAML (`video_path`/`audio_path`/`bbox_shift`) and runs the
  repo's `scripts.inference` (v1.5) in MuseTalk's venv. Implements
  `required_paths`, `weight_report`, `inference_command`, load, generate,
  cleanup.
- **Weights** `avatar_engine/models/musetalk_weights.py` — the authoritative file
  manifest (from upstream `download_weights.sh`), presence/size verification,
  and the install prefetch snippet.
- **Installer** — completed the `musetalk` spec: `git_repo`, GPU-aware
  `torch="auto"`, py3.10 venv, `verify_imports=(diffusers, mmpose, cv2)`, and a
  `prefetch_code` that bootstraps pip, `mim install`s the MMLab stack
  (mmengine/mmcv 2.0.1/mmdet 3.1.0/mmpose 1.1.0), and runs the upstream
  `download_weights.sh`. Reuses the existing installer — no redesign.
- **Registry** — the real adapter replaces the planned placeholder for
  `musetalk`.
- **Validator** `avatar_engine/scripts/validate_musetalk_weights.py` →
  `musetalk_weights_report.{md,json}` (verified / missing / corrupted).
- **Comparison** — `compare_models` and the report now include MuseTalk
  (SadTalker vs LivePortrait vs MuseTalk); title generalized.
- **Notebook** — step 7b validates MuseTalk weights alongside LivePortrait;
  MuseTalk is already in the model list, so Run All installs, validates, and
  benchmarks it automatically (same portraits + Kokoro audio as SadTalker).
- **Docs** — `avatar_engine/docs/MUSE_TALK.md`; this report.

## Root cause of the prior "planned/skipped" state

MuseTalk was a `PlannedAvatarAdapter` stub: no adapter, and the install spec had
no `git_repo`, no weight download, and no MMLab step. A4.0 supplies all of them.

## Upstream inspection (not guessed)

Weights, layout, config format, and the inference command were taken from the
official repo: `README.md`, `download_weights.sh`, and
`configs/inference/test.yaml`. HF sources: `TMElyralab/MuseTalk`,
`stabilityai/sd-vae-ft-mse`, `openai/whisper-tiny`, `yzd-v/DWPose`,
`ByteDance/LatentSync`, plus Google Drive (face-parse-bisent) and a PyTorch URL
(resnet18).

## Benchmark results

Measured GPU numbers (generation time, RTF, FPS, VRAM peak/avg, GPU util/temp,
resolution, duration, output size, success rate + evaluation metrics) are
produced by the Colab **T4** run and written to `model_comparison_report.md`.
They are **not** included here: this repo host has no CUDA GPU **and** MuseTalk's
MMLab stack compiles only on Linux/CUDA (`supported_on_this_platform=False` on
Windows). The notebook produces them automatically on Colab. Everything not
requiring a GPU was verified on the dev host (manifest, verification, adapter
availability/command/yaml, registry, comparison, notebook validity).

## Limitations

- **Linux/CUDA only** (mmcv/mmpose). Runs on Colab; not on the dev host or
  native Windows.
- Weights ~10 GB across five sources; download delegated to the upstream
  `download_weights.sh` for correctness.
- MuseTalk is a lip-sync editor: with a single portrait it animates the mouth
  region to the audio. Per-file SHA256 is not published upstream, so weight
  verification is presence + size-floor, not an exact hash.

## Future work

- EchoMimic V3 (the remaining planned model) via the same pattern.
- Per-file sizes/SHA in the manifest once upstream publishes them.

## Regression

14 new tests (`test_musetalk.py`) covering the spec, weight manifest/verification
(missing/corrupted/required-valid), prefetch (mmlab + download), adapter
availability/command/yaml, registry, and comparison inclusion. Two A3.7 tests
that used `musetalk` as their *planned* example were repointed to `echomimic-v3`
(still planned). Full suite: **263 passed**.
