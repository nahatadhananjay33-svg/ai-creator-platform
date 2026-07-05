# Avatar Model Hardware Requirements

Practical inference envelopes (maintainer docs + community issue reports,
verified 2026-07-04). Authoritative data lives in
`research/catalog.py`; regenerate `output/research/model_comparison.csv`
for the machine-readable version.

## Summary

| Model | Min VRAM | Recommended | RAM | Disk | CPU-only? |
|---|---|---|---|---|---|
| SadTalker | 4 GB | 8 GB | 8 GB | 3 GB | yes (very slow) |
| LivePortrait | 3 GB | 6 GB | 8 GB | 2 GB | no |
| MuseTalk | 6 GB | 8 GB | 16 GB | 10 GB | no |
| LatentSync | 6.5 GB | 8 GB | 16 GB | 12 GB | no |
| Ditto | 6 GB | 12 GB | 16 GB | 6 GB | no |
| EchoMimicV3 | 6.5 GB (768×512) | 12 GB (768×768) | 32 GB | 8 GB | no |
| EchoMimicV2 | 16 GB | 24 GB | 32 GB | 15 GB | no |
| Hallo2 | 16 GB | 24 GB | 32 GB | 20 GB | no |
| MEMO | 16 GB | 24 GB | 32 GB | 20 GB | no |
| OmniAvatar | 8 GB (1.3B) | 24 GB (14B) | 32 GB | 40 GB | no |
| FantasyTalking | 5 GB (offload, very slow) | 24 GB | 32 GB | 40 GB | no |
| InfiniteTalk | 12 GB (480p quant.) | 24 GB (480p full) | 64 GB | 60 GB | no |

720p on the Wan-family models exceeds 24 GB consumer cards (verified:
InfiniteTalk issue #187 — RTX 4090 OOM).

## What this means for the platform

- **This dev machine (Windows, CPU-only)** runs: the mock pipeline, all
  research/reporting tooling, dataset prep, and SadTalker (slow smoke
  tests only). All real benchmarking needs GPU hardware.
- **Benchmark machine (Phase A4):** one 24 GB card (RTX 4090 class) covers
  every candidate except Wan-family 720p. Cloud rental works: the full
  scenario suite across ~8 models is hours, not days, of GPU time.
- **Serving tiers implied by the data:**
  - Interactive tier: MuseTalk / Ditto (6–12 GB, real-time)
  - Standard generation tier: EchoMimicV3 (12 GB, offline)
  - Hero content tier: InfiniteTalk 480p→upscale (24 GB, batch)
