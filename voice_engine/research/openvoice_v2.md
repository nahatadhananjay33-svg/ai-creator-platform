# OpenVoice V2 (MyShell)

**Verdict: cleanest license (MIT everything) and lightest cloning stack, but
cloning is timbre-transfer only and there is no Hindi/Bengali path. A useful
tool, not a platform foundation.**

## Architecture

Two decoupled stages:

1. **Base TTS** — MeloTTS (VITS-family) generates speech in a stock voice.
2. **Tone Color Converter** — flow-based model transfers the target
   speaker's timbre onto the base speech.

Consequence: prosody, accent, and emotion come from the *base speaker*;
only voice color comes from the cloned speaker. That is both its efficiency
trick and its quality ceiling.

## License and commercial usage

MIT code **and** MIT weights (V2, since April 2024). Zero friction — the
best license posture of all candidates.

## Repository and community

- github.com/myshell-ai/OpenVoice — very high star count; development slowed
  after 2024 (V2 is the final major release); install from git (not on PyPI).
- Depends on MeloTTS install; occasional dependency pinning pain (Japanese
  tokenizers etc.).

## Voice cloning

- Reference: ~10-30 s clean audio, no transcript required.
- Speaker similarity: moderate — recognizable timbre, but flattened prosody;
  accent of the cloned speaker is **not** preserved (base-speaker accent
  dominates). Weak gender edge cases when reference and base differ strongly.
- Very stable long-form (no drift) because the base TTS is deterministic.

## Languages

EN/ES/FR/ZH/JA/KO via MeloTTS bases. **No Hindi, no Bengali, no viable
Hinglish.** An Indic base TTS could theoretically be tone-converted — an
experiment, not a plan.

## Performance (research figures)

- Lightest GPU footprint of the cloning candidates (~2 GB); CPU-only
  possible but converter pushes total past real time.
- Two-stage pipeline doubles I/O; still fast overall (RTF ~0.3-0.6 GPU).

## Streaming

**LIMITED.** Neither stage streams natively; tone conversion needs the whole
utterance. Sentence-pipelining only.

## Use-case fit

| Use case | Fit |
| --- | --- |
| English content with cloned timbre | Good |
| Hindi/Hinglish/Bengali anything | Not possible |
| Phone voice AI | Poor |
| Budget/edge deployments (EN) | Good |

## Strengths / weaknesses

**+** MIT everything; tiny footprint; stable long-form; no transcript needed.
**−** Timbre-only cloning (prosody/accent lost); no Indic languages; slowing
maintenance; two-model pipeline complexity; no streaming.
