# Phase A2 Readiness Report

**Date:** 2026-07-04 · Verdict: **READY to start A2**, with three
environment prerequisites and four decision gates carried forward.

## What A2 inherits, already working

- **Operational research platform:** installer (venv-per-model, resumable,
  pins codified), environment/compatibility detection, model validation
  battery, reference-audio study, scoped benchmarking, run merging,
  CSV/JSON/MD reporting — all exercised end-to-end this phase.
- **Six runnable engines** behind the frozen adapter interface with real
  baseline measurements (69 passed benchmark cases; see
  [PHASE_A15_REPORT.md](PHASE_A15_REPORT.md)).
- **A production-deployable voice-AI path today:** Kokoro serves Hindi at
  RTF ≈ 1.0 on a 2015 laptop CPU — real-estate phone/WhatsApp agents do not
  have to wait for GPU procurement to prototype (persona voice, not cloned).
- 77 green tests; zero benchmark-only model code added.

## Environment prerequisites (blockers for specific A2 milestones)

1. **GPU or cloud GPU** (P1 profile: RTX 3060/4070-class, 12 GB) — required
   for: Chatterbox/F5 production-speed content generation, Dia validation,
   CosyVoice 2 streaming measurements, credible GPU rankings. This
   machine's GTX 960M runs driver 398.35 (CUDA 9.2 era); even updated,
   4 GB Maxwell is below every candidate's GPU envelope.
2. **WSL2** on the benchmarking box — unlocks CosyVoice 2 and OpenVoice V2
   (both verified unbuildable on native Windows).
3. **User actions:** accept gated-repo terms for `ai4bharat/indic-parler-tts`
   (+ set `HF_TOKEN`); record the human reference-audio set
   (datasets/reference_audio/README.md) with consent.

## Decision gates carried into A2 (unchanged, now sharpened)

1. **Hinglish listening test** — Chatterbox-multilingual vs IndicF5 on the
   `hi-en` corpus (≥3 native raters, blind protocol ready). Nothing measured
   this phase changes the gate; it remains the platform's biggest unknown.
2. **IndicF5 license confirmation** with AI4Bharat (email, document reply).
3. **CosyVoice 2 streaming measurement** (WSL2/GPU): first-chunk latency,
   chunk cadence, barge-in — the streaming scenario harness already exists
   (`StreamingScenarioCase`); it has only ever measured the mock engine.
4. **Kokoro Hindi MOS ≥ 3.8** with native raters to green-light production
   phone lines (mechanical validation passed; perceptual pending).

## Measured facts A2 should build on

- Dual-tier architecture is now **measured fact** on CPU: cloning engines
  are 2.3-54× slower than real time; real-time engines don't clone.
- Speaker-similarity instrumentation works end-to-end (resemblyzer GE2E via
  webrtcvad-wheels); F5 0.959 > Chatterbox 0.935 > StyleTTS2 0.916 >
  XTTS 0.810 against a synthetic reference.
- 20 s is the recommended reference duration for every validated cloner.
- Installation is the dominant integration cost; every resolved pin is
  codified in `install_specs.py` — A2 must keep that file authoritative.

## Suggested A2 kickoff order (revision of the A1 roadmap)

1. Prototype the real-estate voice agent on **Kokoro (CPU)** immediately —
   it's deployable now and de-risks the A7 product while GPUs are procured.
2. Stand up the P1 GPU box (or cloud) + WSL2; rerun the full benchmark
   unscoped (all 4 languages × 15 prompts × all engines + streaming
   scenarios); merge with this phase's CPU baseline.
3. Close gates 1-4; then build `voice_engine/tts` routing + pipelines per
   the A1 roadmap, with engines chosen by the merged measured results.
