# F5-TTS

**Verdict: top-tier zero-shot cloning quality; blocked for direct commercial
use by checkpoint license. The architecture to bet on via IndicF5 or a
self-trained checkpoint.**

## Architecture

- Flow-matching non-autoregressive model: Diffusion Transformer (DiT) with
  ConvNeXt V2 text refinement ("F5" = Fairytaler that Fakes Fluent and
  Faithful speech with Flow matching).
- No phoneme alignment, no duration model, no text encoder — text is padded
  to audio length and the model infills; this simplicity is why it clones so
  well zero-shot.
- ~336M parameters; Sway Sampling at inference improves quality/speed
  trade-off (fewer NFE steps).
- Successor lineage of E2-TTS; repo also hosts E2 reproduction.

## License and commercial usage

| Component | License |
| --- | --- |
| Code | MIT |
| F5TTS_v1_Base weights (Emilia-trained) | **CC-BY-NC-4.0** — non-commercial |
| Community finetunes | Varies per finetune |

The base checkpoints inherit the Emilia dataset's non-commercial terms.
Commercial paths: (a) train/finetune on permissive data, (b) use a
permissively-licensed finetune, (c) IndicF5 for Indian languages (check its
terms — see [indic_models.md](indic_models.md)).

## Repository and community

- github.com/SWivid/F5-TTS — very high adoption (>10k stars class), active
  through 2025; large finetuning ecosystem (Gradio finetune UI, community
  checkpoints in many languages).
- Installation: `pip install f5-tts` — straightforward on CUDA machines.

## Voice cloning

- Zero-shot from **5-10 s** reference + transcript of the reference.
- Speaker similarity: consistently among the best open models (published
  SIM-o ~0.66 vs ground truth on LibriSpeech-PC; subjectively near-parity
  with commercial systems for English).
- Preserves accent and gender well; emotion follows the reference clip.
- Failure modes: occasional word skips/repeats on very long inputs (mitigate
  by sentence chunking ~< 30 s per chunk); quality collapses with noisy or
  clipped references.

## Languages

| Language | Support |
| --- | --- |
| English | Native (excellent) |
| Hindi | Via **IndicF5** finetune (strong) or community checkpoints |
| Hinglish | Via IndicF5 with romanized/mixed input — must be verified in listening tests |
| Bengali | Via IndicF5 (trained on 8+ Indic languages incl. BN) |

## Performance (research figures; benchmark will measure actuals)

- GPU: RTF ~0.15-0.3 on RTX 3060/4070-class with 16-32 NFE; ~2-4 GB VRAM.
- CPU: RTF > 3 — offline generation only.
- Weights ~1.35 GB; cold start (load + first inference) ~10-20 s on GPU.

## Streaming

**LIMITED.** Non-autoregressive full-utterance generation; no native chunk
streaming. Sentence-level pipelining gets perceived latency to ~1-2 s at
best — usable for semi-interactive, not for phone-grade barge-in.

## Use-case fit

| Use case | Fit |
| --- | --- |
| Reels / YouTube narration | Excellent (with chunking pipeline) |
| Talking avatars | Excellent (batch) |
| Audiobooks | Very good (chunked long-form) |
| Pipecat / phone voice AI | Poor — latency profile wrong |

## Strengths / weaknesses

**+** Best-in-class zero-shot similarity and naturalness; tiny reference
needed; strong finetuning ecosystem; simple architecture to maintain; MIT code.
**−** NC weights license; no streaming; needs reference transcript; long-form
requires chunking layer; no explicit emotion control.
