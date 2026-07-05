# Avatar Model Research (Phase A3)

Research notes behind the machine-readable catalog in `catalog.py`. The
catalog is authoritative — these documents record the evidence, sources,
and reasoning; the code records the conclusions. Observed: **2026-07-04**.

## Methodology

Every candidate was assessed on:

1. **License** — code *and* weights separately (they often differ), plus
   transitive blockers (e.g. InsightFace models inside MIT projects).
2. **Commercial usage** — the practical answer for this platform.
3. **Repository activity** — stars, last push (verified via GitHub API on
   the observation date), maintenance trajectory.
4. **Hardware** — practical inference VRAM/RAM/disk envelopes from
   maintainer docs and community issue reports, not paper claims.
5. **Installation complexity** — dependency stack fragility, compiled
   deps, checkpoint logistics, OS support.
6. **Quality priors** — lip sync, realism, identity, expressiveness,
   motion (1–5), distilled from papers, demo reels, and community
   comparisons. These are `static` ratings until our GPU benchmark
   replaces them with measurements.

## Documents

| File | Covers |
|---|---|
| [liveportrait.md](liveportrait.md) | LivePortrait (portrait reenactment) |
| [musetalk.md](musetalk.md) | MuseTalk (real-time lip sync) |
| [latentsync.md](latentsync.md) | LatentSync (diffusion lip sync) |
| [echomimic_family.md](echomimic_family.md) | EchoMimic v1/v2/v3 |
| [sadtalker.md](sadtalker.md) | SadTalker (legacy baseline) |
| [ditto.md](ditto.md) | Ditto (real-time streaming head) |
| [hallo_family.md](hallo_family.md) | Hallo / Hallo2 / Hallo3, MEMO |
| [wan_family.md](wan_family.md) | InfiniteTalk, FantasyTalking, OmniAvatar |
| [excluded_models.md](excluded_models.md) | Sonic, FLOAT, Wav2Lip, OmniHuman |
| [comparison_matrix.md](comparison_matrix.md) | Generated snapshot of the full comparison |

## Generated comparison

Run `python -m avatar_engine.scripts.generate_research_report` to produce
`output/research/model_comparison.{csv,json,md}` from the catalog —
including the readiness ranking, best-in-class awards, and the overall
recommendation.

## Keeping this current

When re-verifying a model: update its profile in `catalog.py` (bump
`observed_on`), adjust the relevant `.md` here with new evidence, and
regenerate the comparison reports. Never edit generated files by hand.
