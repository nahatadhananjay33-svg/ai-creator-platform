# F5-TTS Setup Report — T1 Benchmark Pipeline

Generated: 2026-07-16
Verdict: **F5-TTS is fully operational on this machine (CPU) and ready for future training work.**
No fine-tuning was performed, no dataset was touched, no other model was benchmarked.

Everything below was produced by one command of the new reusable pipeline
(see [BENCHMARK_PIPELINE_REPORT.md](BENCHMARK_PIPELINE_REPORT.md)):

```bash
python -m voice_engine.scripts.setup_benchmark --model f5-tts --languages en --device cpu
```

## 1. Dependencies installed

- Rebuilt `.venvs/f5-tts` (Python 3.12.12 via uv) — the previous venv was machine-bound to the old
  ASUS host and could not spawn here.
- `torch 2.13.0+cpu` (CPU wheel index; GTX 1050 driver 451.67 is below the 452.39 CUDA floor).
- `f5-tts 1.1.21` + full dependency set, with two pins:
  `pyarrow==21.0.0` (existing spec pin) and **`numba>=0.60` (new)** — fresh resolution otherwise
  backtracks to llvmlite 0.36, which cannot build on Python 3.12.
- Imports verified inside the venv: `f5_tts`, `soundfile`. Shared FFmpeg (`.venvs/_tools/ffmpeg`)
  confirmed working.

## 2. Pretrained models downloaded (automatic, cache-aware)

- `SWivid/F5-TTS` → `F5TTS_v1_Base/model_1250000.safetensors` (~1.35 GB)
- `charactr/vocos-mel-24khz` vocoder
- Both landed in the HF cache on first load; the second run reused the cache (no re-download).

## 3. Model load verified

- Load succeeded on CPU. Warm-cache init: **80.75 s** (first-ever load incl. download: ~566 s).

## 4. Smoke inference (pretrained only, no fine-tuning)

- Zero-shot cloning against the checked-in synthetic reference clip
  (`voice_engine/datasets/reference_audio/synthetic/synthetic_en_20s.wav`) — reference accepted.
- English smoke sentence synthesized: **4.46 s of audio at 24 kHz** (verified non-silent,
  peak amplitude 0.396).
- First inference: **870.7 s** on this 8-core/7.8 GB CPU box (RTF ≈ 195 — functional check only;
  GPU hosts run F5 at RTF 0.15–0.3). Peak RSS 1.93 GB.

## 5. Artifacts

| Artifact | Path |
| --- | --- |
| Generated audio | `voice_engine/output/validation/f5-tts-en-smoke.wav` |
| Validation JSON (timings, RSS, pass/fail) | `voice_engine/output/validation/f5-tts-validation.json` |
| Full run log (stdout+stderr) | `voice_engine/output/benchmark_setup/f5-tts/setup.log` |
| Machine-generated setup report | `voice_engine/output/benchmark_setup/f5-tts/f5-tts_SETUP_REPORT.md` |

## 6. Caveats for the training phase

- **License:** F5-TTS code is MIT, but the pretrained base weights are **CC-BY-NC-4.0** (Emilia
  data) — not commercially usable without retraining/relicensing. This is exactly why the plan
  fine-tunes on own data; keep the restriction in mind for any demo built on the base weights.
- **This machine is CPU-only** (GTX 1050 / driver 451.67 / 7.8 GB RAM). It validates that the stack
  works; training and performance benchmarking belong on the Colab GPU setup from Phase B0.
- The compatibility probe formally rates this host "incompatible" (RAM floor 8 GB vs 7.8 GB
  available); actual measured peak was 1.93 GB, so setup validation is safe here regardless.
