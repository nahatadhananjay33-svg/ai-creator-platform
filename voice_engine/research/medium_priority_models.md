# Medium-Priority Models

## MeloTTS (MyShell)

**Verdict: latency/efficiency baseline; production-viable for English with
an Indian accent; no cloning.**

- VITS-family, ~52M params; MIT code + weights.
- **CPU real-time** — the only high-priority-adjacent model that is; also
  the base TTS inside OpenVoice V2.
- Languages: EN (US/UK/AU/**EN-India accent**), ZH, JA, KO, ES, FR. No
  Hindi/Bengali *text* support (EN-India is accented English, not Hindi).
- No cloning, no emotion control, no native streaming (but RTF << 1 on CPU
  makes sentence-chunk pseudo-streaming responsive).
- Fit: fallback/edge voice for English voice AI; cost floor for serving.

## Spark-TTS (SparkAudio)

**Verdict: interesting research (BiCodec single-stream tokens, attribute-
controlled voice creation), deprioritized for us: EN/ZH only and unclear
weight licensing.**

- 0.5B Qwen2.5 backbone; zero-shot cloning; can also *create* voices from
  attributes (gender, pitch, rate) without reference audio.
- Code Apache-2.0; released weights carry **CC-BY-NC-4.0 signals** in parts
  of the release — commercial use unverified. EN/ZH only, no streaming.
- Revisit only if Indic finetunes with clear licensing appear.

## Seed-TTS (ByteDance) — EXCLUDED

- Landmark paper (2024) defining the zero-shot quality bar (Seed-TTS_ICL /
  factorized speaker control), but **no open weights, no code** — API-only
  inside ByteDance products (Doubao).
- Fails the phase's "open-source, self-hostable" requirement. Its published
  evaluation protocol (SIM/WER on multilingual test sets) informed our
  metric design; the model itself is out of scope.

## StyleTTS 2

**Verdict: fastest high-quality English synthesis; MIT; English-only keeps
it a baseline, and the GPL phonemizer needs isolation in proprietary
deployments.**

- Style-diffusion + adversarial training, ~148M params; human-level MOS
  claims on LJSpeech; GPU RTF ~0.03-0.1, near-real-time on strong CPUs.
- Zero-shot style transfer from ~3 s reference — but transfers *style*
  vector, so timbre fidelity trails LLM-token cloners (F5/Chatterbox).
- MIT code + weights; **espeak-ng (GPL-3.0)** used by the standard
  phonemizer — run it out-of-process or replace for closed deployments.
- English only (community multilingual efforts exist but are not
  production-grade). Kokoro-82M (see emerging_models.md) is effectively its
  production-hardened descendant and supersedes it for our purposes.
