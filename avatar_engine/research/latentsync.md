# LatentSync — diffusion lip sync

**Repo:** https://github.com/bytedance/LatentSync
**Verified:** 2026-07-04 · 5,835 stars · last push 2025-06-20 · slowing

## What it is

ByteDance's end-to-end audio-conditioned latent diffusion lip-sync — no
intermediate motion representation. Regarded as the accuracy leader for
open lip sync. Version history: 1.5 added temporal layers (consistency,
Chinese-video performance); 1.6 retrained at 512×512 to fix 1.5's
blurriness.

## License

- Code: **Apache-2.0**.
- Weights (`ByteDance/LatentSync-1.6` on HF): **OpenRAIL++** — commercial
  use allowed, subject to responsible-AI use restrictions (no deception,
  impersonation, rights violations). An avatar product needs a documented
  compliance position (consented likenesses, disclosure), which the
  platform requires anyway.

## Hardware

**6.5 GB VRAM** inference — modest for diffusion. Offline speed: roughly
minutes per minute of footage on consumer GPUs; not real-time.

## Strengths / weaknesses

- + Best-in-class sync accuracy (LSE-C/LSE-D benchmarks in the paper);
  reasonable VRAM; clean install relative to mmlab-based stacks.
- − Not real-time (MuseTalk wins there); mouth-region editor only;
  OpenRAIL++ compliance clause.

## Sources

- https://github.com/bytedance/LatentSync
- https://huggingface.co/ByteDance/LatentSync-1.5 (license: openrail++)
- https://comfyui-wiki.com/en/news/2025-01-04-latentsync-bytedance-lipsync-tool
