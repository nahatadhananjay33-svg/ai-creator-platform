<!-- GENERATED SNAPSHOT: regenerate with `python -m avatar_engine.scripts.generate_research_report` and copy output/research/model_comparison.md here. Do not edit by hand. -->

# Avatar Model Comparison (Phase A3 research)

Generated: 2026-07-04T17:12:17.048683+00:00  
Ratings below are **static research priors** (papers, demos, community evidence) — not our measurements. The benchmark replaces them with measured values on GPU hardware in Phase A4.

## Comparison matrix

| Model | Task | Weights license | Commercial | VRAM (min/rec GB) | Install | Maintenance | Rating | Production? |
|---|---|---|---|---|---|---|---|---|
| Ditto TalkingHead | audio_driven_head | Apache-2.0 | yes | 6 / 12 | high | slowing | 3.6/5 | yes |
| EchoMimicV2 | audio_driven_body | Apache-2.0 | yes | 16 / 24 | high | active | 4.0/5 | yes |
| EchoMimicV3 | audio_driven_body | Apache-2.0 | yes | 6.5 / 12 | moderate | active | 4.0/5 | yes |
| FantasyTalking | audio_driven_body | Apache-2.0 | yes | 5 / 24 | high | active | 4.0/5 | yes |
| FLOAT | audio_driven_head | CC-BY-NC-ND-4.0 | **NO** | 8 / 12 | moderate | slowing | 4.0/5 | no — CC-BY-NC-ND-4.0 forbids commercial use and derivative works. |
| Hallo2 | audio_driven_head | MIT | yes | 16 / 24 | high | stale | 4.0/5 | yes |
| Hallo3 | audio_driven_head | MIT | yes | 24 / 40 | severe | stale | 4.6/5 | no — Hardware envelope (24-40 GB VRAM) and generation latency are incompatible with platform serving economics in 2026. |
| InfiniteTalk | audio_driven_body | Apache-2.0 | yes | 12 / 24 | severe | active | 4.6/5 | yes |
| LatentSync | video_lip_sync | OpenRAIL++ | yes | 6.5 / 8 | moderate | slowing | 3.6/5 | yes |
| LivePortrait | portrait_reenactment | MIT (but InsightFace dep is non-commercial) | **NO** | 3 / 6 | moderate | active | 4.6/5 | yes |
| MEMO | audio_driven_head | Apache-2.0 | yes | 16 / 24 | high | slowing | 4.0/5 | yes |
| MuseTalk | video_lip_sync | MIT | yes | 6 / 8 | high | slowing | 3.8/5 | yes |
| OmniAvatar | audio_driven_body | Apache-2.0 | yes | 8 / 24 | high | slowing | 4.0/5 | yes |
| OmniHuman-1/1.5 | audio_driven_body | not released | **NO** | CPU-capable | severe | active | 5.0/5 | no — Not open-source: weights unavailable as of 2026-07; tracked only as the quality reference the open models chase. |
| SadTalker | audio_driven_head | Apache-2.0 | yes | 4 / 8 | low | stale | 2.8/5 | yes |
| Sonic | audio_driven_head | CC-BY-NC-SA-4.0 | **NO** | 10 / 16 | moderate | active | 4.4/5 | no — CC-BY-NC-SA-4.0 forbids commercial use. |
| Wav2Lip | video_lip_sync | research-only | **NO** | 2 / 4 | low | stale | 2.4/5 | no — Non-commercial license and obsolete visual quality; useful only as a benchmark baseline on a research machine. |

## Production readiness ranking

Composite of research quality (35%), commercial license (20%), maintenance (15%), hardware envelope (15%), install complexity (15%).

| Rank | Model | Score | Key strength | Key risk |
|---|---|---|---|---|
| 1 | EchoMimicV3 | 0.81 | Best quality-per-GB in the family: 1.3B params, 12 GB covers 768x768 | Young project — smaller community and fewer battle scars than v2 |
| 2 | LatentSync | 0.75 | State-of-the-art lip-sync accuracy (end-to-end audio-conditioned diffusion) | Slower than MuseTalk — offline dubbing, not real-time |
| 3 | MuseTalk | 0.72 | True real-time inference (30 fps+ on V100) — enables interactive avatars | Only edits the mouth: needs a driving/template video for everything else |
| 4 | EchoMimicV2 | 0.69 | Half-body animation with hand gestures — richer than head-only models | 16 GB+ VRAM practical requirement |
| 5 | FantasyTalking | 0.69 | Wan-quality realism with documented low-VRAM offload paths | Same Wan-stack install burden as InfiniteTalk with a smaller community |
| 6 | LivePortrait | 0.69 | Best-in-class expression/pose transfer with excellent identity retention | Video-driven, not audio-driven: needs a driving performance video or an audio-to-motion front-end to make talking avatars |
| 7 | InfiniteTalk | 0.69 | Unlimited-length generation with stable identity (sparse-frame dubbing) | 14B model: heavy downloads (~60 GB), datacenter-adjacent hardware for 720p |
| 8 | Ditto TalkingHead | 0.68 | Real-time streaming audio->talking-head — the interactive-avatar niche | TensorRT engine build makes installs GPU/driver-specific and brittle |
| 9 | SadTalker | 0.68 | Easiest full image->talking-head pipeline to stand up; lowest hardware bar | Unmaintained; quality clearly behind 2024+ diffusion models |
| 10 | MEMO | 0.63 | Memory-guided temporal module targets long-video identity drift | Heavy VRAM and slow generation |
| 11 | OmniAvatar | 0.63 | Prompt-controllable full-body avatar behavior | Human evaluators rate its naturalness below its objective scores (over-optimized lip region) |
| 12 | Hallo2 | 0.57 | Hour-scale generation with identity drift countermeasures | Research-grade codebase; heavy preprocessing chain |

## Best in class

- **Best Lip Sync**: MuseTalk — Highest research lip-sync rating (5/5) among production candidates
- **Best Realism**: InfiniteTalk — Highest research realism rating (5/5) among production candidates
- **Best Identity Consistency**: LivePortrait — Highest identity-consistency rating (5/5)
- **Best Lightweight**: LivePortrait — Lowest VRAM floor (3 GB) among production candidates
- **Best Production Model**: EchoMimicV3 — Highest production-readiness score among commercially usable candidates

> LivePortrait awards carry a license caveat: commercial deployment requires replacing its InsightFace detection models first.

## Strengths and weaknesses

### Ditto TalkingHead (`ditto`)

**Strengths**
- Real-time streaming audio->talking-head — the interactive-avatar niche
- Motion-space diffusion keeps identity stable; controllable style
- Apache-2.0 end to end

**Weaknesses**
- TensorRT engine build makes installs GPU/driver-specific and brittle
- Face-region animation only; torso/background static
- Small community relative to the majors

### EchoMimicV2 (`echomimic-v2`)

**Strengths**
- Half-body animation with hand gestures — richer than head-only models
- Apache-2.0 end to end; active Ant Group backing
- Simplified conditioning vs v1 (fewer control inputs to wrangle)

**Weaknesses**
- 16 GB+ VRAM practical requirement
- Minutes of generation per clip — offline only
- English + Mandarin driving audio officially; other languages untested

### EchoMimicV3 (`echomimic-v3`)

**Strengths**
- Best quality-per-GB in the family: 1.3B params, 12 GB covers 768x768
- Unified multi-modal/multi-task: talking head AND talking body in one model
- Fresh (AAAI 2026), actively developed, Apache-2.0

**Weaknesses**
- Young project — smaller community and fewer battle scars than v2
- Still diffusion-offline; not real-time

### FantasyTalking (`fantasy-talking`)

**Strengths**
- Wan-quality realism with documented low-VRAM offload paths
- Apache-2.0

**Weaknesses**
- Same Wan-stack install burden as InfiniteTalk with a smaller community
- Slow generation

### FLOAT (`float`)

*Excluded from production: CC-BY-NC-ND-4.0 forbids commercial use and derivative works.*

**Strengths**
- Fast flow-matching sampling; emotion control

**Weaknesses**
- Non-commercial, no-derivatives license — unusable for the platform

### Hallo2 (`hallo2`)

**Strengths**
- Hour-scale generation with identity drift countermeasures
- High-resolution (up to 4K) portrait output
- MIT licensed

**Weaknesses**
- Research-grade codebase; heavy preprocessing chain
- Slow generation; high VRAM floor
- Effectively in maintenance freeze

### Hallo3 (`hallo3`)

*Excluded from production: Hardware envelope (24-40 GB VRAM) and generation latency are incompatible with platform serving economics in 2026.*

**Strengths**
- Handles dynamic backgrounds and non-frontal poses that break UNet models
- Top-tier realism from the video-DiT prior

**Weaknesses**
- 40 GB-class VRAM recommendation prices out our deployment targets
- Very slow; research scaffolding; stale repo

### InfiniteTalk (`infinitetalk`)

**Strengths**
- Unlimited-length generation with stable identity (sparse-frame dubbing)
- Both image->video and video->video modes; full-body motion follows audio
- Apache-2.0 on a 14B video prior — best open realism ceiling
- Very active development and ComfyUI ecosystem support

**Weaknesses**
- 14B model: heavy downloads (~60 GB), datacenter-adjacent hardware for 720p
- Minutes per clip; flash-attn/Wan stack is Linux-first and fragile

### LatentSync (`latentsync`)

**Strengths**
- State-of-the-art lip-sync accuracy (end-to-end audio-conditioned diffusion)
- 1.6 fixed the 1.5 blurriness by moving to 512x512 training
- Modest inference VRAM (6.5 GB) for a diffusion approach

**Weaknesses**
- Slower than MuseTalk — offline dubbing, not real-time
- Mouth-region editor only; needs existing footage
- OpenRAIL++ use restrictions require a compliance check for avatar products

### LivePortrait (`liveportrait`)

**Strengths**
- Best-in-class expression/pose transfer with excellent identity retention
- Near real-time on midrange GPUs; official Windows one-click package
- Very active, huge community (ComfyUI ecosystem)
- Stitching/retargeting controls (eyes, lips) for editorial use

**Weaknesses**
- Video-driven, not audio-driven: needs a driving performance video or an audio-to-motion front-end to make talking avatars
- InsightFace dependency blocks commercial use until replaced

### MEMO (`memo`)

**Strengths**
- Memory-guided temporal module targets long-video identity drift
- Emotion-aware audio conditioning
- Apache-2.0

**Weaknesses**
- Heavy VRAM and slow generation
- Modest community; release cadence slowed after initial drop

### MuseTalk (`musetalk`)

**Strengths**
- True real-time inference (30 fps+ on V100) — enables interactive avatars
- Identity preserved perfectly outside the mouth region (inpainting approach)
- MIT license incl. weights, explicit commercial permission
- Works on any existing video — pairs naturally with a motion source

**Weaknesses**
- Only edits the mouth: needs a driving/template video for everything else
- 256x256 face crop limits quality on tight close-ups
- mmcv/mmpose dependency chain is painful to install, esp. on Windows

### OmniAvatar (`omniavatar`)

**Strengths**
- Prompt-controllable full-body avatar behavior
- 1.3B variant offers a lighter quality/cost point

**Weaknesses**
- Human evaluators rate its naturalness below its objective scores (over-optimized lip region)
- Momentum shifted to InfiniteTalk within the same ecosystem

### OmniHuman-1/1.5 (`omnihuman`)

*Excluded from production: Not open-source: weights unavailable as of 2026-07; tracked only as the quality reference the open models chase.*

**Strengths**
- Industry-reference quality bar for audio-driven full-body animation

**Weaknesses**
- Weights never released; API pricing and ToS control the product

### SadTalker (`sadtalker`)

**Strengths**
- Easiest full image->talking-head pipeline to stand up; lowest hardware bar
- Permissive license, enormous install base and documentation

**Weaknesses**
- Unmaintained; quality clearly behind 2024+ diffusion models
- Stiff head motion, waxy faces, visible jaw artifacts

### Sonic (`sonic`)

*Excluded from production: CC-BY-NC-SA-4.0 forbids commercial use.*

**Strengths**
- Excellent perceptual quality and audio-motion coupling
- Strong community adoption despite the license

**Weaknesses**
- Non-commercial license — unusable for the platform

### Wav2Lip (`wav2lip`)

*Excluded from production: Non-commercial license and obsolete visual quality; useful only as a benchmark baseline on a research machine.*

**Strengths**
- Trivial to install; historical baseline every paper compares against
- Tiny model, CPU-capable

**Weaknesses**
- 2020-era visual quality: blurry 96x96 mouth region
- Research-only license — cannot ship

## Overall recommendation

1. **Primary avatar generation:** EchoMimicV3 — highest production-readiness score (0.81); Apache-2.0, active, and the best quality-per-GB envelope.
2. **Lip-sync / dubbing track:** MuseTalk for re-syncing existing footage; MuseTalk where real-time matters.
3. **Realism ceiling (batch content):** InfiniteTalk on rented GPU capacity for hero content where minutes-per-clip latency is acceptable.
4. **Do not build on:** Sonic, FLOAT, Wav2Lip (licenses); Hallo3 (hardware economics); OmniHuman (closed).

Validate this ordering with measured GPU benchmark runs before any Phase A4 integration commitment — see `avatar_engine/docs/BENCHMARKING.md`.
