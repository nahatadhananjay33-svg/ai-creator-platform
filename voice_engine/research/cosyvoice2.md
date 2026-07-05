# CosyVoice 2 (Alibaba FunAudioLLM)

**Verdict: the reference architecture for open-source streaming voice AI —
~150 ms first-packet with zero-shot cloning, Apache-2.0. Primary candidate
for the platform's real-time tier; Indic languages would require our own
fine-tune.**

## Architecture

- Text LLM (Qwen2.5-0.5B base) → supervised semantic speech tokens (FSQ) →
  **chunk-aware flow-matching** decoder → vocoder.
- Designed bidirectionally streaming from the ground up: streams text in
  (LLM-agent friendly) and audio out.
- CosyVoice 3 (2025) continues the line with more data/languages; evaluate
  it in the A2 install pass — same adapter surface.

## License and commercial usage

Apache-2.0 code and weights (CosyVoice2-0.5B). Commercial use permitted.

## Repository and community

- github.com/FunAudioLLM/CosyVoice — large, active, Alibaba-backed; strong
  ecosystem (vLLM acceleration, FastAPI/gRPC serving examples, Pipecat
  community integrations).
- **Installation is the hardest of all candidates**: clone-from-source,
  pinned conda env, pynini/WeTextProcessing, matcha-tts, optional ttsfrd
  resource packs. Budget half a day the first time.

## Voice cloning

- Zero-shot from **3-10 s** reference + transcript; also supports
  instruct-mode style control ("speak cheerfully", dialect hints) and
  fine-tuned speaker embedding modes.
- Similarity/naturalness: state-of-the-art for ZH, very good for EN
  (CN-accent traces on some voices — must be validated by our EN raters);
  consistency across streaming chunks is excellent (that's the whole point
  of the chunk-aware decoder).

## Languages

| Language | Support |
| --- | --- |
| English | Native (good, occasional accent color) |
| Hindi | Not supported — fine-tune required (recipes exist upstream) |
| Hinglish | Not supported |
| Bengali | Not supported |
| ZH/JA/KO + dialects | Native (excellent) |

## Performance (research figures)

- First-packet latency ~**150 ms** (GPU, streaming mode); RTF well below 1.
- ~4-6 GB VRAM fp16; vLLM path improves throughput for concurrent calls.
- CPU: not real-time.

## Streaming

**EXCELLENT — the best native streaming of any open cloning model.**
Chunked synthesis with quality ~lossless vs offline mode; barge-in friendly
(generation cancellable per chunk); phone-conversation suitable.

## Use-case fit

| Use case | Fit |
| --- | --- |
| Pipecat / phone agents (EN today; HI after fine-tune) | Excellent |
| Real-estate voice AI | Excellent architecture; language gap is the work item |
| Reels/narration | Good (quality slightly below Chatterbox/F5 for EN) |
| Bengali | No (without training investment) |

## Strengths / weaknesses

**+** True 150 ms streaming; Apache-2.0; cloning + instruct control;
Alibaba-scale maintenance; fine-tune recipes.
**−** No Indic languages out of the box; painful install; EN accent color;
heavier serving stack (worth it only for the real-time tier).
