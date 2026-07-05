# Hardware Requirements Guide

## Per-model envelope (inference)

| Model | Min VRAM | Rec. VRAM | RAM | Disk | CPU-only? |
| --- | --- | --- | --- | --- | --- |
| Kokoro-82M | — | 2 GB | 4 GB | 0.4 GB | **Yes (real-time)** |
| MeloTTS | — | 2 GB | 4 GB | 0.5 GB | **Yes (real-time)** |
| StyleTTS 2 | 2 GB | 4 GB | 8 GB | 1 GB | Near-real-time |
| OpenVoice V2 | 2 GB | 4 GB | 8 GB | 1 GB | Slow |
| F5-TTS / IndicF5 | 4 GB | 8 GB | 8 GB | 1.5 GB | No (RTF > 3) |
| XTTS v2 | 4 GB | 8 GB | 8 GB | 2 GB | No |
| CosyVoice 2 | 4 GB | 8 GB | 16 GB | 3 GB | No |
| Chatterbox | 6 GB | 8 GB | 16 GB | 4 GB | No |
| Indic Parler-TTS | 6 GB | 8 GB | 16 GB | 3.5 GB | No |
| Dia | 6 GB (bf16) | 10 GB | 16 GB | 6.5 GB | No |

## Deployment profiles

### P0 — Development / this workstation (CPU-only, 16 GB RAM)
Runs: platform core, mock benchmark, Kokoro, MeloTTS, dataset/report
tooling. Cannot meaningfully benchmark GPU models — use P1.

### P1 — Single consumer GPU (RTX 3060 12 GB / 4070 12 GB, 32 GB RAM)
The Phase A2 benchmarking box. Runs every candidate (Dia in bf16), one
model at a time. Batch content generation: fine. Concurrent voice AI
calls: 1-3 per GPU depending on model.

### P2 — Production content tier (RTX 4090 24 GB or L4/A10G cloud)
Quality models (Chatterbox + IndicF5/Indic Parler) resident simultaneously;
batch reel/narration generation with queue. ~2-4× faster than P1 per job.

### P3 — Production real-time tier (L4/A10G per ~8-15 concurrent calls)
CosyVoice 2 (or Orpheus) with vLLM-class serving for cloned-voice calls;
Kokoro on CPU nodes scales cheap non-cloned Hindi/English lines
(one modern CPU core ≈ 1-2 concurrent streams).

## Rules of thumb

- **VRAM** is the binding constraint, not compute: RTF < 1 on any RTX-class
  card for every candidate; concurrency = VRAM / model footprint.
- **Latency tiering beats bigger GPUs:** a phone agent needs < 500 ms to
  first audio — that's an architecture property (streaming decoder), not
  something more VRAM fixes. Hence the dual-tier design in the final report.
- Benchmark reports embed the exact hardware profile of each run
  (`environment` block) — never compare numbers across profiles.
