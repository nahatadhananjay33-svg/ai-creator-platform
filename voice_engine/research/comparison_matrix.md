# Master Comparison Matrix

Static research synthesis (early 2026). Measured numbers come from benchmark
runs in `voice_engine/output/runs/`; this matrix is the research layer.
Adapter `ModelSpec`s in `voice_engine/adapters/` are the machine-readable
source of truth for the license/hardware columns.

## 1. Licensing and commercial readiness

| Model | Code | Weights | Commercial today? |
| --- | --- | --- | --- |
| Chatterbox | MIT | MIT | **Yes** (watermarked output) |
| CosyVoice 2 | Apache-2.0 | Apache-2.0 | **Yes** |
| Indic Parler-TTS | Apache-2.0 | Apache-2.0 | **Yes** |
| Kokoro-82M | Apache-2.0 | Apache-2.0 | **Yes** |
| Dia | Apache-2.0 | Apache-2.0 | **Yes** |
| OpenVoice V2 | MIT | MIT | **Yes** |
| MeloTTS | MIT | MIT | **Yes** |
| StyleTTS 2 | MIT | MIT | Yes (isolate GPL espeak-ng) |
| F5-TTS | MIT | CC-BY-NC-4.0 | **No** (base weights); path via retrain/IndicF5 |
| IndicF5 | MIT (arch) | verify | **Verify with AI4Bharat** |
| XTTS v2 | MPL-2.0 | CPML (non-commercial) | **No** |
| Spark-TTS | Apache-2.0 | NC signals — verify | **Assume no** |
| Seed-TTS | — | not released | Excluded |

## 2. Language coverage (our four targets)

| Model | English | Hindi | Hinglish | Bengali | Cloning |
| --- | --- | --- | --- | --- | --- |
| Chatterbox | ★★★★★ | ★★★★ (native) | ★★★? (verify) | — | zero-shot |
| IndicF5 | ★★★ | ★★★★★ | ★★★? (verify) | ★★★★★ | zero-shot |
| Indic Parler-TTS | ★★★★ | ★★★★★ | ★★★ | ★★★★★ | none (persona voices) |
| XTTS v2 | ★★★★ | ★★★★ (native) | ★★★ | — | zero-shot |
| F5-TTS (base) | ★★★★★ | — | — | — | zero-shot |
| CosyVoice 2 | ★★★★ | — | — | — | zero-shot |
| Kokoro | ★★★★ | ★★★ (fixed voices) | — | — | none |
| MeloTTS | ★★★★ (EN-India accent) | — | — | — | none |
| StyleTTS 2 / Dia / OpenVoice / Spark | EN only (for us) | — | — | — | varies |

★ ratings are research expectations to be confirmed by blind listening tests
(`?` = highest uncertainty). "—" = not supported.

## 3. Performance envelope (research figures; verify on our hardware)

| Model | Params | Min VRAM | CPU real-time | GPU RTF (class) | Ref. audio |
| --- | --- | --- | --- | --- | --- |
| Kokoro | 82M | none | **Yes** | <0.1 | n/a |
| MeloTTS | 52M | none | **Yes** | <0.1 | n/a |
| StyleTTS 2 | 148M | 2 GB | near | 0.03-0.1 | 3 s |
| F5-TTS | 336M | 4 GB | No | 0.15-0.3 | 5-10 s + transcript |
| XTTS v2 | 467M | 4 GB | No | 0.2-0.4 | 6 s |
| CosyVoice 2 | 500M | 4 GB | No | <1 (streams) | 3-10 s + transcript |
| Chatterbox | 500M | 6 GB | No | 0.3-0.6 | 7-20 s |
| Indic Parler | 880M | 6 GB | No | <1 | n/a (description) |
| Dia | 1.6B | 6-10 GB | No | ~1 | 5 s + transcript |

## 4. Streaming classification

| Class | Models | Notes |
| --- | --- | --- |
| **Excellent** | CosyVoice 2 | ~150 ms first packet, chunk-aware decoder, barge-in friendly |
| **Good** | XTTS v2 (license-blocked), Kokoro | XTTS: native stream API. Kokoro: RTF so low that sentence chunks feel streamed |
| **Limited** | F5-TTS, Chatterbox, Indic Parler, MeloTTS, StyleTTS 2, OpenVoice, Spark | sentence pipelining only; 1-2 s perceived latency floor |
| **Not suitable** | Dia | whole-utterance, high latency |

## 5. Use-case winners (pre-listening-test)

| Use case | Winner | Runner-up |
| --- | --- | --- |
| EN content narration (cloned voice) | Chatterbox | F5-TTS (license caveat) |
| HI content narration | Chatterbox / IndicF5 | Indic Parler-TTS |
| Hinglish reels | Chatterbox (verify) | IndicF5 (verify) |
| BN content | **Indic Parler-TTS** | IndicF5 |
| EN dialogue skits | Dia | — |
| Talking avatar audio | Chatterbox | IndicF5 |
| Phone / Pipecat voice AI (EN) | CosyVoice 2 | Kokoro (no cloning) |
| Phone voice AI (HI) today | **Kokoro (HI voices)** | CosyVoice 2 + HI fine-tune (later) |
| Edge / CPU-only deployments | Kokoro | MeloTTS |

## 6. Overall

- **Best multilingual (our languages):** Indic Parler-TTS (breadth) /
  Chatterbox (quality where covered)
- **Best Hindi:** Chatterbox and IndicF5 (cloning); Indic Parler (persona)
- **Best Hinglish:** unresolved between Chatterbox and IndicF5 — the single
  most important listening test of Phase A2
- **Best Bengali:** Indic Parler-TTS (only clean-license native option)
- **Best content creation:** Chatterbox
- **Best streaming:** CosyVoice 2
- **Best voice AI:** CosyVoice 2 (EN), Kokoro (HI, pragmatic)
- **Best overall single model:** *none satisfies all constraints* — see
  final report for the dual-tier architecture decision.
