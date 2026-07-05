# XTTS v2 (Coqui)

**Verdict: the most complete feature set on paper (17 languages incl. native
Hindi, 6 s cloning, real streaming) — but the weights are non-commercial,
which disqualifies it for our production platform. Keep as the quality/latency
baseline every candidate must beat.**

## Architecture

- Autoregressive GPT-style acoustic model over VQ latents (Tortoise lineage)
  + HiFi-GAN decoder; speaker conditioned via perceiver-based latents from
  reference audio.
- ~467M parameters (~1.9 GB download).

## License and commercial usage

| Component | License |
| --- | --- |
| Code (idiap/coqui-ai-TTS fork) | MPL-2.0 |
| XTTS-v2 weights | **Coqui Public Model License — non-commercial** |

Coqui (the company) shut down in early 2024; there is no entity to buy a
commercial license from. The Idiap Research Institute fork (`coqui-tts` on
PyPI) maintains the code. **Weights remain CPML — cannot ship in our product.**

## Repository and community

- Original repo archived; idiap/coqui-ai-TTS actively maintained; the largest
  installed base of any open cloning model (years of tutorials, integrations,
  streaming servers).
- Installation: `pip install coqui-tts` — mature, but heavy transitive deps.

## Voice cloning

- Zero-shot from **6 s** reference (no transcript needed); multiple reference
  clips improve stability.
- Good speaker similarity; occasional voice drift on paragraphs > ~250 chars
  (mitigate with sentence splitting, which its API does internally).
- Known artifacts: sporadic trailing noises, rare language flips on
  code-mixed text.

## Languages

| Language | Support |
| --- | --- |
| English | Native (very good) |
| Hindi | **Native** (added v2.0.3, Devanagari input) — best out-of-box Hindi among the "big" cloning models |
| Hinglish | Workable: romanized text via `language="hi"`; quality inconsistent at switch points |
| Bengali | Not supported |

## Performance (research figures)

- GPU: RTF ~0.2-0.4 (RTX 3060+); ~4 GB VRAM.
- CPU: RTF ~2-5 — not real-time.
- Fine-tuning: well-documented recipes (used widely for Indic finetunes).

## Streaming

**GOOD.** Native `inference_stream()` chunked decoding; first-chunk latency
< 300 ms reported on datacenter GPUs, ~0.5-1 s on consumer GPUs. The
reference implementation other models are compared against.

## Use-case fit

| Use case | Fit |
| --- | --- |
| Reels / narration | Very good |
| Talking avatars | Very good |
| Phone voice AI | Good technically — blocked by license |
| Anything commercial | **Blocked (CPML)** |

## Strengths / weaknesses

**+** Native Hindi; 6 s cloning without transcript; true streaming; huge
community knowledge base.
**−** Non-commercial weights (fatal for us); abandoned upstream company;
aging architecture; drift on long-form; heavy dependency chain.
