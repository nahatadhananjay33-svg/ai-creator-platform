# Voice Cloning Model Research — Phase A1

Engineering evaluation of open-source voice cloning / TTS models for the AI
Creator Platform. Commercial API-only services (ElevenLabs, PlayHT, Seed-TTS
API, etc.) are out of scope by design.

## Documents

| File | Contents |
| --- | --- |
| [comparison_matrix.md](comparison_matrix.md) | Master comparison tables (license, languages, hardware, streaming, use-case fit) |
| [f5_tts.md](f5_tts.md) | F5-TTS deep dive |
| [xtts_v2.md](xtts_v2.md) | XTTS v2 deep dive |
| [openvoice_v2.md](openvoice_v2.md) | OpenVoice V2 deep dive |
| [chatterbox.md](chatterbox.md) | Chatterbox deep dive |
| [dia.md](dia.md) | Dia deep dive |
| [cosyvoice2.md](cosyvoice2.md) | CosyVoice 2 deep dive |
| [indic_models.md](indic_models.md) | Indic Parler-TTS, IndicF5 (Hindi/Bengali specialists) |
| [medium_priority_models.md](medium_priority_models.md) | MeloTTS, Spark-TTS, StyleTTS 2, Seed-TTS (excluded) |
| [emerging_models.md](emerging_models.md) | Kokoro, Orpheus, Zonos, GPT-SoVITS, IndexTTS-2, others |

## Methodology and provenance

Two evidence classes, never mixed silently:

1. **Static research** (this folder + each adapter's `ModelSpec`): licenses,
   architectures, community status, vendor-reported latencies. Compiled from
   upstream repos/papers as of early 2026. Anything uncertain is marked
   *verify*. License conclusions must be re-checked against the upstream
   repository before any production deployment.
2. **Measured results** (`voice_engine/output/runs/`): produced by
   `python -m voice_engine.scripts.run_benchmark` on named hardware. Every
   run report embeds its hardware profile; results from different machines
   are not comparable.

Perceptual rankings (naturalness, accent, code-switching) come only from the
blind human listening protocol (`voice_engine/evaluation/human_eval.py`) —
minimum 3 native-speaker raters per language.

## Candidate disposition

| Model | Adapter | Status |
| --- | --- | --- |
| F5-TTS | `f5-tts` | Benchmark candidate (license caveat) |
| XTTS v2 | `xtts-v2` | Baseline only — non-commercial weights |
| OpenVoice V2 | `openvoice-v2` | Benchmark candidate |
| Chatterbox | `chatterbox` | **Primary candidate** (quality tier) |
| Dia | `dia` | Niche (dialogue clips) |
| CosyVoice 2 | `cosyvoice2` | **Primary candidate** (streaming tier) |
| MeloTTS | `melotts` | Latency baseline; no cloning |
| Spark-TTS | `spark-tts` | Deprioritized — license unclear, EN/ZH only |
| Seed-TTS | — | **Excluded**: no open weights (paper/API only) |
| StyleTTS 2 | `styletts2` | English-only fast baseline |
| Indic Parler-TTS | `indic-parler` | **Primary candidate** (Hindi/Bengali) |
| Kokoro-82M | `kokoro` | **Primary candidate** (real-time CPU tier) |
