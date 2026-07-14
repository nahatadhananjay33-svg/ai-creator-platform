# Avatar Dataset Evaluator

Evaluates whether a folder of raw videos is suitable for building a **digital
avatar** — fully **local, CPU-only, offline, deterministic**. It trains nothing,
downloads nothing, and does not touch the Avatar Engine. It only produces an
evaluation: per-clip measurements, accept/reject, and dataset-level reports.

```bash
python -m production.avatar_dataset_evaluator.evaluate
```

## What "no AI models" means here

Reliable face/pose/expression analysis usually needs neural networks (MediaPipe,
dlib). To honour the *no-AI-models / no-GPU / no-internet* constraint, this engine
uses **OpenCV's bundled Haar cascade classifiers** (classical Viola-Jones — no deep
learning, no download, CPU) for face/eye/smile detection, and DSP/statistics for
everything else. Consequently the metrics have **different confidence levels**:

| Confidence | Metrics |
|---|---|
| **High** | resolution, fps, orientation, codec, bitrate, duration, file size, brightness, sharpness (Laplacian variance), face visibility %, face size, frontal vs profile |
| **Medium** | eye/mouth visibility, occlusion, camera stability/movement (phase correlation), scene changes, speaking % (lower-face motion) |
| **Low / heuristic** | walking vs stationary, indoor vs outdoor (brightness proxy), expression (smile cascade), head-rotation degree |
| **Not determinable classically** | laughing vs smiling, precise emotions — reported as n/a; time-of-day comes from the file's **metadata timestamp**, not pixels |

The reports flag low-confidence fields. For production-grade diversity labelling
you'd add an AI pass in a later, separately-approved phase.

## Input / output

- **Input:** `D:\AI_CREATOR_DATA\Tanshi\raw_videos` (recursive), formats
  `.mp4 .mov .avi .mkv .m4v`. Override with `--base DIR` or `$AVATAR_EVAL_BASE`.
- **Output:** `…\avatar_dataset\`
  ```
  accepted/     hardlinks of accepted videos (no extra disk)
  rejected/     hardlinks of rejected videos
  thumbnails/   one mid-frame JPEG per video
  reports/      report.json + report.txt
  dataset.sqlite · dataset.csv · dataset.xlsx
  ```

## Per-video measurements

Technical: filename, duration, resolution, fps, aspect ratio, orientation, file
size, codec, bitrate, frame count, creation time.
Visual: face visibility %, avg face size, frontal/profile %, face view, head
rotation, lighting mean + consistency, camera stability, sharpness, occlusion,
eye/mouth visibility, speaking %, walking/stationary %, camera movement, scene
changes, time-of-day, setting, expression.

## Classification

Composite **0–100 score** (weighted: face visibility, face size, frontal, sharpness,
lighting, stability, resolution, eyes) → band **excellent / good / usable / poor /
reject**. Accepts *usable* and above. Hard-reject reasons: no visible face · face
too small · heavy blur · extreme head rotation · face covered · very dark · very
bright · low resolution · too shaky · too short. All thresholds live in
[`config.py`](config.py) and are tunable.

## Reports

- **Totals/averages:** accepted/rejected, usable hours, avg duration/resolution/
  fps/face-visibility/lighting/stability.
- **Diversity:** front/left/right, standing/walking, indoor/outdoor, time-of-day,
  expressions (low-confidence flagged).
- **Missing-data:** plain-English "need more X" (side profiles, smiling, static
  talking, close-ups, total footage, …).
- **Avatar Readiness Score (0–100)** and heuristic **per-model likelihood** for
  MuseTalk / LatentSync / EchoMimic / Hallo2 (all talking-head lip-sync models —
  likelihood is driven by the amount of frontal talking-head footage + mouth
  visibility + minutes; it is an estimate, not a guarantee).

## Resume, progress, validation

Re-running **skips already-evaluated files** (keyed by filename in the prior
`dataset.sqlite`). A tqdm bar shows progress. The CLI prints the full report plus
a random **30 accepted / 30 rejected** audit (filename, duration, score, reason).

## Tests

```bash
python -m pytest production/avatar_dataset_evaluator/tests -q
```

Hermetic and deterministic: OpenCV writes small synthetic videos in-process (no
ffmpeg dependency, no GPU, no models) and an autouse fixture blocks the network.
The accept path is validated separately on real footage.

## Requirements

Python ≥ 3.10, `numpy`, `opencv-python`, `openpyxl`. `ffmpeg`/`ffprobe` optional
(richer technical metadata; OpenCV is the fallback). No GPU, no internet at runtime.
