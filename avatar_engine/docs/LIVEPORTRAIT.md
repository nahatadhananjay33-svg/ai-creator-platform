# LivePortrait Integration (Phase A3.9)

## Required pretrained weights (authoritative — from upstream)

Source: HF repo **`KlingTeam/LivePortrait`** and the upstream
`assets/docs/directory-structure.md`. Humans mode only
(`liveportrait_animals/` is intentionally excluded). Manifest lives in
`avatar_engine/models/liveportrait_weights.py`. Sizes are the HF-reported
values (used as a truncation/corruption guard; exact SHA256 verified when a
hash is added to the manifest).

| File (under `pretrained_weights/`) | Purpose | Size |
|---|---|---|
| `liveportrait/base_models/appearance_feature_extractor.pth` | appearance feature extractor | 3.39 MB |
| `liveportrait/base_models/motion_extractor.pth` | motion / keypoint extractor | 113 MB |
| `liveportrait/base_models/spade_generator.pth` | SPADE image generator (decoder) | 222 MB |
| `liveportrait/base_models/warping_module.pth` | warping module | 182 MB |
| `liveportrait/landmark.onnx` | landmark detection (onnx) | 115 MB |
| `liveportrait/retargeting_models/stitching_retargeting_module.pth` | stitching / retargeting | 2.39 MB |
| `insightface/models/buffalo_l/2d106det.onnx` | insightface 2D-106 landmarks | 5.03 MB |
| `insightface/models/buffalo_l/det_10g.onnx` | insightface face detection | 16.9 MB |

Total ≈ 660 MB. Repo code is cloned from `github.com/KwaiVGI/LivePortrait`;
weights are pulled from the `KlingTeam` HF mirror.

## Download & verification

The installer's `prefetch_code` runs, inside the LivePortrait venv:

```python
hf_hub_download(repo_id="KlingTeam/LivePortrait", filename=<rel>, local_dir=pretrained_weights)
```

per file — which **resumes** partial downloads, verifies the HF etag, and
returns instantly for files already present (so **valid weights are never
re-downloaded**). Post-download, `check_weights()` classifies each file:

| Status | Meaning |
|---|---|
| `validated` | present and size (and SHA when known) valid |
| `missing` | not downloaded |
| `corrupted` | present but size far off nominal (truncated / error page) |
| `checksum_mismatch` | present, correct size, wrong SHA256 |

```bash
python -m avatar_engine.scripts.validate_liveportrait_weights
```

## Adapter availability

`LivePortraitAdapter.required_paths()` returns `inference.py` **plus every
weight file** (not just the top-level directory). So the A3.7 diagnostics name
the *specific* missing weight instead of a bare `missing files: liveportrait`.
`weight_report()` returns the full per-weight status.

## Running it in the benchmark (video-driven)

LivePortrait is **video-driven** (source portrait + driving video), unlike
SadTalker (audio-driven). The framework's `GenerationRequest.driving_video`
field is now wired through the dataset/case:

- `ResolvedAssets.driving_video` resolves a per-scenario `driving_video` or a
  shared `driving_video.mp4` in the assets dir.
- The benchmark passes it to the adapter; audio-driven models ignore it.
- If a video-driven model has **no** driving video, its scenarios are recorded
  SKIPPED with a clear reason (no separate execution path).

The Colab notebook seeds `driving_video.mp4` from LivePortrait's own example
clips. LivePortrait uses the **same source portraits and scenarios** as
SadTalker; the scenario audio is still associated for evaluation.

> LivePortrait does not lip-sync to the scenario audio (it isn't audio-driven),
> so audio lip-sync metrics are only meaningful for SadTalker. The comparison
> measures performance and video/motion quality on measured numbers only.

## Comparison report

```bash
python -m avatar_engine.scripts.compare_models
```

Aggregates the latest run per model into
`avatar_engine/output/comparisons/model_comparison_report.{md,json}`:
generation time, RTF, FPS, VRAM (peak/avg), GPU util/temp, resolution,
duration, output size, success rate, and the framework's evaluation metrics —
no subjective judgement.
