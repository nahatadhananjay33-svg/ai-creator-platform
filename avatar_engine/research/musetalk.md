# MuseTalk — real-time lip sync

**Repo:** https://github.com/TMElyralab/MuseTalk
**Verified:** 2026-07-04 · 6,118 stars · last push 2025-09-26 · slowing

## What it is

Tencent Music's real-time high-quality lip-sync model (v1.5, paper
arXiv:2410.10122): latent-space inpainting of the mouth region of an
existing video, driven by new audio, at **30 fps+ on a V100** — the only
mature open model that makes *interactive* dubbed avatars practical.

## License

MIT for code **and** weights; README states explicitly there is no
limitation for academic or commercial usage. Cleanest license in the
lip-sync category.

## Hardware

~6 GB VRAM (fp16); face region processed at 256×256. Real-time on
datacenter cards, near-real-time on RTX 30/40 consumer cards.

## Installation

The main risk is the **mmlab chain** (mmcv/mmdet/mmpose via `mim`):
compiled, version-locked, painful on native Windows — plan on Linux/WSL2.
Weights fetched by the repo's `download_weights.sh`.

## Strengths / weaknesses

- - Real-time; perfect identity outside the mouth; commercial-clean; works
  on any template video (pairs naturally with LivePortrait or recorded
  presenter footage).
- − Mouth-only edit (needs a motion source for everything else); 256×256
  crop softens extreme close-ups; install complexity.

## Sources

- https://github.com/TMElyralab/MuseTalk (+ LICENSE, MIT, verified raw)
- https://huggingface.co/TMElyralab/MuseTalk
- https://arxiv.org/abs/2410.10122
