# Phase A1 Final Report — Voice Cloning Research & Platform Foundation

**Date:** 2026-07-04 · **Status:** research conclusions from static analysis +
pipeline verification; quantitative confirmation lands with the Milestone 1
GPU benchmark (see PHASE_A2_ROADMAP.md).

---

## The engineering question

> Can one open-source voice cloning model realistically power both
> high-quality content creation (Instagram, YouTube, talking avatars) and
> low-latency real-time voice AI (Pipecat, phone agents) — or is a
> dual-model architecture technically superior?

## Answer: a dual-model (dual-tier) architecture is technically superior — and with the current open-source field, effectively mandatory.

### Why no single model wins

The two workloads optimize opposing variables, and the model landscape
splits along exactly that line:

1. **Latency physics vs. quality architecture.** The best open cloning
   quality today comes from LLM-token or flow-matching architectures
   (Chatterbox, F5-TTS/IndicF5) that generate at utterance scale: their
   floor to *first audio* is ~1-2 s even on strong GPUs. Phone-grade
   conversation needs < 500 ms to first packet and mid-utterance
   cancellation (barge-in). The only open models engineered for that —
   CosyVoice 2 (~150 ms, chunk-aware decoder) and small real-time models
   (Kokoro) — sit one quality/expressiveness class below the content
   engines. No candidate occupies both corners; this is an architectural
   trade-off (chunk-causal decoding constrains quality), not a tuning gap
   that the next release will erase.

2. **The language×license matrix has no single-model solution.** Our
   platform needs EN + HI + Hinglish + BN under a commercially usable
   license. The only native-Bengali clean-license model (Indic Parler-TTS)
   doesn't clone and doesn't stream fast; the best commercial-OK cloner
   (Chatterbox) lacks Bengali and official streaming; the best streamer
   (CosyVoice 2) has no Indic languages; the models that cover everything
   linguistically closest (XTTS v2) or clone best (F5 base) have
   non-commercial weights. One model cannot even cover the *content* side
   alone.

3. **Operational shape differs.** Content generation is batch: queue,
   cache, retry — optimize cost per minute of audio. Voice AI is
   concurrent sessions with SLOs: pinned warm models, streaming servers.
   Coupling both to one model means every upgrade risks both product lines;
   separating tiers lets each evolve on its own cadence. This is the same
   reason production LLM stacks run big-model/small-model splits.

### Recommended architecture: two tiers, one engine

```
                    Voice Engine (one codebase, one interface)
                    ────────────────────────────────────────────
 Shared:            interfaces · adapters · datasets · evaluation ·
                    reporting · pronunciation · voice profiles · config ·
                    caching · logging (ALL of Phase A1)
                    ┌──────────────────────┬──────────────────────┐
 Tiers:             │  QUALITY TIER        │  REAL-TIME TIER      │
 (config, not code) │  batch pipeline      │  streaming service   │
                    │  Chatterbox (EN/HI)  │  CosyVoice 2 (EN,    │
                    │  IndicF5 (HI/BN)*    │   cloned voices)     │
                    │  Indic Parler (BN,   │  Kokoro (HI/EN,      │
                    │   persona voices)    │   persona, CPU-cheap)│
                    └──────────────────────┴──────────────────────┘
 Consumers:         Reels · YouTube · Avatars (A3-A5)   Pipecat · phone · WhatsApp (A6-A7)
                    (*pending license confirmation)
```

**Voice identity bridging** — the piece that makes two tiers feel like one
product: each production voice is a single `VoiceProfile` with per-engine
conditioning artifacts. A brand persona is cloned once in the quality tier;
the real-time tier serves either the same clone (CosyVoice zero-shot from
the same reference) or the persona-matched Kokoro voice, selected by SLO.
The A1 speaker-similarity metric quantifies cross-tier voice match and
gates which pairings ship.

### What stays shared vs. specialized

**Shared (already built in A1, reused verbatim):** interfaces
(`TTSEngine`/`VoiceCloner`/`StreamingTTSEngine`), `BaseVoiceAdapter` +
registry, `ModelSpec` registry, datasets, evaluation + human-eval protocol,
reporting, `foundation.*` (config/logging/cache/benchmarking/hardware).
**Shared, built in A2:** pronunciation/entity verbalization (RERA, phone
numbers, lakh/crore), voice-profile store with consent metadata, text
normalization frontend.
**Specialized per tier:** the *pipelines* — batch chunk-synth-concat-master
pipeline (quality tier) vs. streaming server with chunk pacing/barge-in/
telephony resampling (real-time tier) — plus tier-specific serving infra and
SLO monitoring. Both are thin layers over shared adapters, so maintenance
concentrates in shared code.

### Maintenance posture

Model churn is the dominant long-term cost in this space (2024-2026 saw the
leaderboard change ~every 6 months). The adapter pattern makes each model a
~100-line, independently deletable module carrying its own metadata; the
benchmark + golden reports make "new model beats incumbent?" a one-command
question. That — not any specific model choice — is Phase A1's durable bet.

---

## Supporting findings (detail in voice_engine/research/)

- **Licensing eliminated more candidates than quality did.** XTTS v2 (best
  all-round on paper) and F5-TTS base weights are non-commercial; Spark-TTS
  unclear; Seed-TTS was never open. License checks are now a mandatory field
  in every `ModelSpec`.
- **Hinglish is the pivotal open question** — no model documents it, and it
  is our highest-value register (sales calls, reels). The A1 Hinglish corpus
  + blind listening protocol exist precisely to answer it in A2 gate #1.
- **Bengali has exactly one clean answer today** (Indic Parler-TTS), which
  is persona-based, not cloning — set product expectations accordingly.
- **CPU real-time is real** (Kokoro, MeloTTS): a zero-GPU path exists for
  scaling Hindi/English phone lines if unit economics demand it.

## Phase A1 deliverables shipped

1. Platform foundation (8 packages, typed, tested — 65 tests green, zero ML deps).
2. Voice Engine research infrastructure (frozen interfaces, 12 adapters incl.
   mock, model catalog).
3. Modular benchmark framework (generic runner + voice scenarios; verified
   end-to-end: 72-case mock run producing all reports).
4. Benchmark datasets: 4 languages × 15 prompts × 13 categories,
   real-estate-specific, script-validated.
5. Evaluation framework: 15 auto metrics + 8-metric human rubric, blind
   listening protocol with score-sheet generation.
6. Reporting: CSV/JSON/Markdown with hardware provenance.
7. Documentation: 10 research docs, installation/hardware/recommendation
   guides, architecture doc, A2 roadmap, this report.
