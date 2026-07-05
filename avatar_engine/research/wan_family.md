# Wan2.1-based generators — InfiniteTalk, FantasyTalking, OmniAvatar

The 2025–2026 wave: audio-driven avatar video built on Alibaba's
**Wan2.1-I2V-14B** open video prior (Apache-2.0). Highest open-source
realism ceiling, highest hardware cost. Verified 2026-07-04.

## InfiniteTalk (MeiGen) — `infinitetalk`

7,349 stars · last push 2026-05-22 · very active (fastest-growing repo in
the category). **Apache-2.0** end to end.

- **Unlimited-length** talking video via sparse-frame dubbing; both
  image→video and video→video modes; body motion follows the audio.
- Hardware: 480p runs on a single RTX 4090 (quantized variants lower
  this); 720p OOMs 24 GB cards (issue #187). ~60 GB of downloads
  (Wan2.1-I2V-14B-480P + chinese-wav2vec2-base + InfiniteTalk weights).
- Install: flash-attn + Wan stack — Linux/WSL2 only, CUDA build toolchain
  required. SEVERE complexity, worth it for hero content.

## FantasyTalking (Alibaba AMAP) — `fantasy-talking`

1,623 stars · last push 2026-01-26 · active. Apache-2.0.

- Wan-quality realism with **documented low-VRAM offload** (down to ~5 GB
  at heavy speed cost — hours per clip).
- Smaller community than InfiniteTalk; same stack burden.

## OmniAvatar (Alibaba/ZJU) — `omniavatar`

1,842 stars · last push 2025-08-06 · slowing. Apache-2.0. 1.3B and 14B
variants.

- Prompt-controllable full-body behavior.
- Caveat from independent evaluations (SoulX-LiveTalk report): human
  raters score it **below** its objective metrics — over-optimized lip
  region harms perceived naturalness. A concrete reminder why our
  benchmark separates auto metrics from human MOS.

## Platform take

InfiniteTalk is the **realism-ceiling track**: batch-render hero content
on rented GPU capacity. None of these fit interactive or high-volume
economics today; quantization and distilled variants are the trend to
watch (SoulX-LiveTalk-class streaming DiTs may change this within a year).

## Sources

- https://github.com/MeiGen-AI/InfiniteTalk (+ issue #187 on 720p VRAM)
- https://github.com/Fantasy-AMAP/fantasy-talking
- https://github.com/Omni-Avatar/OmniAvatar
- arXiv:2508.14033 (InfiniteTalk), arXiv:2512.23379 (SoulX-LiveTalk)
