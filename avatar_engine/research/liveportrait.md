# LivePortrait — portrait reenactment

**Repo:** https://github.com/KwaiVGI/LivePortrait (now KlingAIResearch org)
**Verified:** 2026-07-04 · 18,680 stars · last push 2026-06-01 · very active

## What it is

Implicit-keypoint portrait animation from Kuaishou/Kling: a source portrait
is driven by a performance *video* (expressions + head pose transfer) at
~12.8 ms/frame on an RTX 4090. The most-starred and most-integrated
portrait animation project in the ComfyUI ecosystem; supports stylized
sources and fine retargeting controls (eyes/lips).

## License — the critical caveat

- Code and released weights: **MIT**.
- But the pipeline ships **InsightFace buffalo_l** detection/analysis
  models, which are **non-commercial research-only**
  ([issue #193](https://github.com/KwaiVGI/LivePortrait/issues/193)).
- Commercial path: replace InsightFace face detection/alignment with a
  commercially usable stack (MediaPipe Face, YOLO-face, SCRFD-retrained).
  Community forks prove feasibility; budget ~1–2 engineer-weeks + QA.

## Hardware

~3 GB VRAM floor, 6 GB comfortable; ~2 GB weights; near real-time on
midrange GPUs. Official Windows one-click package exists; macOS (MPS)
supported.

## Role for the platform

Not audio-driven — it cannot make a talking avatar alone. Its value is as
the **motion/expression layer**: pair with an audio-to-motion driver, or
retarget one recorded human performance onto many avatar identities.
Ratings in the catalog reflect that framing (lip_sync 3 = only as good as
the driving video's mouth).

## Sources

- https://github.com/KwaiVGI/LivePortrait
- https://github.com/KwaiVGI/LivePortrait/issues/193 (InsightFace licensing)
- https://huggingface.co/KwaiVGI/LivePortrait
