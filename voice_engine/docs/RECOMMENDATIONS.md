# Production Recommendations (Phase A1 → A2)

> **Updated with Phase A1.5 measured results** — see
> [docs/PHASE_A15_REPORT.md](../../docs/PHASE_A15_REPORT.md). Measured on
> CPU-only hardware: Kokoro is real-time in Hindi (RTF 0.99) and is the
> recommended immediate engine for voice-AI prototyping; Chatterbox has the
> best commercially-usable measured cloning similarity (0.935) and remains
> the content-tier primary pending GPU verification. OpenVoice V2 and
> Spark-TTS are now **discarded** (Windows-blocked / license). CosyVoice 2
> remains the streaming candidate, unmeasurable on native Windows — A2
> gate #3 moves it to WSL2/GPU.

Full rationale: [docs/PHASE_A1_FINAL_REPORT.md](../../docs/PHASE_A1_FINAL_REPORT.md).

## Recommended model portfolio

| Slot | Model | Why |
| --- | --- | --- |
| **Quality tier — EN + HI cloning** | Chatterbox (Multilingual) | MIT, top open EN quality, native HI, emotion control |
| **Quality tier — Indic cloning** | IndicF5 (pending license confirmation) | Only strong HI+BN open cloner; F5 architecture |
| **Quality tier — BN + persona voices** | Indic Parler-TTS | Apache-2.0, only clean-license native Bengali |
| **Real-time tier — cloned voice calls** | CosyVoice 2 (EN now; HI via A2 fine-tune) | 150 ms streaming, Apache-2.0 |
| **Real-time tier — pragmatic HI/EN calls** | Kokoro-82M | CPU real-time, Apache-2.0, HI voices, cheapest scaling |
| Creative niche (EN dialogue reels) | Dia | Unique non-verbal dialogue generation |
| Baselines (benchmark only) | XTTS v2, F5-TTS base, MeloTTS, StyleTTS 2 | Quality/latency yardsticks |

## Do NOT ship

- **XTTS v2** — CPML weights are non-commercial; no licensing entity exists.
- **F5-TTS base checkpoints** — CC-BY-NC (Emilia). Architecture is fine;
  those weights are not.
- **Spark-TTS / Fish-OpenAudio weights** — NC or unclear terms.

## Decision gates before A2 build-out

1. **Hinglish listening test** (the pivotal unknown): Chatterbox-multilingual
   vs IndicF5 on the `hi-en` dataset with ≥3 native raters. The winner
   becomes the reels/avatar default voice engine.
2. **IndicF5 license confirmation** with AI4Bharat (email; document reply).
3. **CosyVoice EN accent check** with EN raters; if accent color is
   unacceptable, Orpheus becomes the streaming-tier candidate.
4. **Kokoro Hindi MOS** ≥ 3.8 on our rubric to green-light it for
   production phone lines.

## Operating principles

- Every model behind `BaseVoiceAdapter`; product code never imports a model
  library directly. Swapping engines must stay a config change.
- Voice cloning of real persons requires recorded consent stored with the
  profile (voices/ package, Phase A2); watermarked output (Chatterbox) is
  preferred for digital-influencer content.
- Re-run the benchmark and archive reports whenever a model version, driver,
  or serving stack changes; reports are the regression baseline.
