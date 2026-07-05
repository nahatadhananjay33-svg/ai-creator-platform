# Avatar Model Recommendations (Phase A3)

> **Updated with Phase A3.5 measured results** — see
> [docs/PHASE_A35_REPORT.md](../../docs/PHASE_A35_REPORT.md). On this
> CPU-only host: **SadTalker is the only model that generates video**
> (measured RTF ≈ 255 at 256², Hindi audio works; interim offline
> baseline). LivePortrait installed but timed out on CPU (>60 min for a
> ~5 s clip); EchoMimic V3 deps-ready, Not Tested; MuseTalk/InfiniteTalk/
> Wan-family Not Supported on native Windows (documented). Comparative
> quality rankings remain deferred to the A4 GPU pass.

Conclusions below are from the research phase. Grounded in verified
licenses, repository activity, hardware envelopes, and community evidence —
**not yet in our own measurements**. The Phase A4 GPU benchmark must
confirm this ordering before integration work begins. Machine-readable
version: `python -m avatar_engine.scripts.generate_research_report`.

## Best in class (static research ratings)

| Award | Model | Why |
|---|---|---|
| Best lip sync | **MuseTalk** (real-time) / **LatentSync** (accuracy) | MIT real-time inpainting vs SOTA diffusion sync |
| Best realism | **InfiniteTalk** | Wan 14B prior; unlimited length with stable identity |
| Best identity consistency | **LivePortrait** | implicit-keypoint transfer barely touches identity (license caveat) |
| Best lightweight | **LivePortrait** (3 GB; caveat) → **SadTalker** (4 GB, commercial-clean) | |
| Best production model | **EchoMimicV3** | Apache-2.0, active, 1.3B params, 12 GB covers 768×768 |

## Recommended architecture: three tracks

1. **Standard avatar generation — EchoMimicV3.** Image + voice-engine
   audio → talking avatar. Apache-2.0, active Ant Group backing, best
   quality-per-GB (6.5–12 GB). Fallback: EchoMimicV2 where hand gestures
   justify 16 GB+.
2. **Dubbing / re-sync — LatentSync 1.6**, with **MuseTalk** where
   real-time matters (interactive avatars, live hosts). Both pair with
   template footage or LivePortrait-driven motion.
3. **Hero content — InfiniteTalk** at 480p + upscale, batch-rendered on
   rented 24 GB GPUs. Not for high-volume or interactive use.

Baseline/fallback: **SadTalker** (lowest hardware bar, Apache-2.0, runs
even on CPU) — also the quality floor every candidate must beat in the
human eval.

## License positions to track

- **LivePortrait**: MIT but InsightFace detection models are
  non-commercial. Replace detection stack before any commercial use
  (~1–2 engineer-weeks; community forks prove feasibility).
- **LatentSync**: OpenRAIL++ weights — commercial OK with responsible-use
  clauses; the platform's consent/disclosure policy must be documented.
- **Identity metric**: benchmark uses InsightFace (research-only) —
  acceptable for evaluation, must swap for production identity checks.
- Rejected outright: Sonic (CC-BY-NC-SA), FLOAT (CC-BY-NC-ND), Wav2Lip
  (research-only), OmniHuman (closed).

## Phase A4 gate

Before integration: run the full benchmark on a 24 GB GPU machine with
real portraits + voice-engine audio, collect ≥3-rater human MOS, and
confirm (a) EchoMimicV3 beats SadTalker decisively on `mos_overall`, and
(b) LatentSync/MuseTalk hit `lip_sync_confidence` parity with published
LSE-C numbers. If either fails, re-rank from the measured data — the
framework regenerates every report automatically.
