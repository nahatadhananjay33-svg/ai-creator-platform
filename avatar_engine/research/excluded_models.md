# Excluded models — and why

Documented so the exclusions are auditable and revisitable. Verified
2026-07-04.

## Sonic (Tencent/Zhejiang) — license

3,263 stars · active · quality competitive with the best open heads.
**CC-BY-NC-SA-4.0** (LICENSE file verified) — non-commercial, ShareAlike.
Unusable for the platform in any form. Revisit only if relicensed.

## FLOAT (DeepBrain AI) — license

483 stars · flow-matching talking head with emotion control, fast
sampling. **CC-BY-NC-ND-4.0** (README verified): non-commercial AND
no-derivatives. DeepBrain sells commercial licenses — a buy-vs-build data
point, not an open-source candidate.

## Wav2Lip (IIIT-H) — license + age

13,083 stars · the historical lip-sync baseline. Research-only license
(commercial rights via Sync Labs); 96×96 mouth region, 2020 quality.
Excluded from production; legitimate as a benchmark reference point on a
research machine only.

## OmniHuman-1 / 1.5 (ByteDance) — closed

The quality reference for audio-driven full-body animation
(arXiv:2502.01061). **Weights never released**; available only as a paid
API (Dreamina/BytePlus). Tracked in the catalog as the bar the open models
chase; not a candidate. ByteDance's open releases in this space remain
LatentSync (lip sync only).

## Hallo3 (Fudan) — hardware economics

MIT-licensed and impressive, but 24–40 GB VRAM per generation at very low
throughput. See [hallo_family.md](hallo_family.md).

## Honorable mentions (watchlist)

- **SoulX-LiveTalk / Live Avatar** (arXiv:2512.23379) — real-time infinite
  streaming DiT avatars; weights availability unclear at observation date.
- **MultiTalk** (MeiGen, NeurIPS 2025) — multi-person conversational
  video; same Wan stack; niche for us today.
- **JoyVASA, AniTalker, GeneFace++** — research-grade, low maintenance
  signal; none clears the production bar.
