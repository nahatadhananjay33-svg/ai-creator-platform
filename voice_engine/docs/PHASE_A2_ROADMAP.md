# Phase A2 Roadmap — Production Voice Engine

Everything below builds on A1 modules unchanged: adapters, interfaces,
datasets, evaluation, reporting, and the foundation packages are reused
as-is. A2 adds production capability around them.

## Milestone 1 — Measured benchmark (GPU box, ~week 1-2)

- Install candidates per INSTALLATION.md on the P1 GPU profile.
- Record the reference-audio set (datasets/reference_audio/README.md).
- Run full benchmark (all adapters × 4 languages × all categories,
  repetitions ≥ 3); archive reports.
- Blind listening round (≥3 native raters per language) using
  `HumanEvalProtocol` score sheets; resolve the four decision gates in
  RECOMMENDATIONS.md.

## Milestone 2 — Production synthesis service (`voice_engine/tts`)

- `TTSService`: request routing (language/use-case → engine per benchmark
  results), retry + fallback chain, output caching via `foundation.cache`
  keyed on (engine, voice, text, params).
- `voice_engine/pipelines`: chunked long-form pipeline (sentence split,
  per-chunk synthesis, crossfade concat, loudness normalize) — turns
  utterance-scale engines (Chatterbox/IndicF5) into narration engines.
- Pronunciation layer (`voice_engine/pronunciation`): lexicon overrides for
  builder/project names, RERA/phone-number verbalization per language.
  A1's entity prompt categories are the acceptance tests.

## Milestone 3 — Voice library (`voice_engine/cloning`, `voice_engine/voices`)

- Profile store (create/version/approve voices; consent metadata mandatory).
- Reference-audio intake with `validate_reference()` gating + quality report.
- Conditioning-latent caching per engine for fast cold starts.

## Milestone 4 — Streaming service (`voice_engine/streaming`)

- `StreamingTTSEngine` wrapper service: chunk pacing, barge-in cancel,
  resample to 8/16 kHz telephony formats.
- Pipecat integration (TTS service class consuming `astream_synthesize`).
- Latency SLO harness: reuse `StreamingScenarioCase` against the live
  service (benchmark-as-monitoring).
- Decision: CosyVoice 2 serving stack (vLLM) vs Orpheus, per gate #3.

## Milestone 5 — Indic depth

- IndicF5 adapter subclass + license outcome; Hinglish text-frontend rules
  (script normalization, romanization policy) informed by A1 text metrics.
- If gate #1 shows both engines weak on Hinglish: scope a fine-tune
  (Chatterbox-multilingual or F5 arch) on curated Hinglish sales-call data.

## Milestone 6 — Hardening

- Async batch queue for reel/narration jobs; structured-log dashboards
  (JSON logging already in foundation).
- Golden-output regression suite: benchmark run pinned per release.
- API surface for other engines (avatar A3/A4 consumes `SynthesisResult`
  + word timestamps — add timestamp extraction here).

## Explicit non-goals for A2

Real-time avatar lip-sync (A4), reel assembly (A5), multi-tenant serving
(later), training custom base models (only fine-tunes if gates demand).
