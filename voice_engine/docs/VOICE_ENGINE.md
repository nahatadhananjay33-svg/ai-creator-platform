# Voice Engine — Production API (Phase A2)

The Voice Engine is the platform's reusable speech layer. Instagram Reels,
YouTube narration, talking avatars, real-estate voice AI, WhatsApp voice
messages, and the benchmark all consume the same facade:

```python
from voice_engine import VoiceEngine

voice = VoiceEngine()                                   # config-driven
voice.load_model("kokoro")                              # optional; defaults apply

profile = voice.clone_voice(
    "priya_reference.wav", "Agent Priya",
    language_hint="hi",
    consent="P. Sharma, 2026-07-04, marketing use",     # mandatory to save
)

result = voice.generate(
    "Namaste! Capital Greens mein aapka swagat hai.",
    language="hi-en", voice=profile, emotion="happy",
)

for chunk in voice.stream("Hello! How can I help?", language="en"):
    play(chunk.pcm_s16le)                               # barge-in: stop iterating

voice.save_profile(profile)
profile = voice.load_profile(profile.profile_id)
voice.export(result, "narration.mp3")                   # FFmpeg-backed
```

Nothing outside `voice_engine` imports adapters or managers directly:
consumers use `VoiceEngine` plus the frozen types in
`voice_engine.interfaces` (`SynthesisResult`, `VoiceProfile`, `AudioChunk`).

## Architecture

The facade composes single-purpose managers; every one reuses the Phase A1
foundation (config loader, disk cache, structured logging, WAV I/O,
exceptions) and the frozen A1 interfaces/adapters:

| Component | Module | Responsibility |
| --- | --- | --- |
| `VoiceEngine` | `voice_engine/engine.py` | Facade: model lifecycle, request assembly, public API |
| Adapters (A1) | `voice_engine/adapters/` | One thin wrapper per model behind `TTSEngine`/`VoiceCloner` |
| Voice Profile Manager | `voice_engine/voices/` | Persistent profile store, consent-gated, durable reference copies |
| Pronunciation Manager | `voice_engine/pronunciation/` | Lexicon rewrites (RERA, BHK, project names) before synthesis |
| Emotion Manager | `voice_engine/emotion/` | One emotion enum mapped to per-engine controls (exaggeration / instruct / hint) |
| Streaming Manager | `voice_engine/streaming/` | Native chunk streaming or sentence-chunked fallback; 8/16 kHz resampling |
| Cache Manager | `voice_engine/tts/cache.py` | Content-addressed synthesis cache (foundation `DiskCache`) |
| Engine Router | `voice_engine/tts/router.py` | Config-driven use-case → engine chains |
| Quality Pipeline | `voice_engine/pipelines/quality.py` | Long-form: sentence split → synth → crossfade → normalize |
| Real-Time Pipeline | `voice_engine/pipelines/realtime.py` | Text front-end + paced PCM chunks for live agents |
| Audio Export Manager | `voice_engine/pipelines/audio_export.py` | WAV/PCM natively; MP3/OGG/FLAC via platform FFmpeg |

Request flow for `generate()`:

```
text ─ pronunciation.apply ─ emotion.render ─ cache.get ──hit──▶ result
                                             │ miss
                                             ▼
                            adapter.synthesize / QualityPipeline
                                             │
                                     cache.put ─▶ SynthesisResult
```

## Configuration (model switching without code changes)

Layers (later wins): packaged `voice_engine/tts/defaults.yaml` → optional
environment YAML (`VoiceEngine(config_path=...)`) → `AICP__section__key`
env vars → explicit `overrides={...}`.

```yaml
engine:
  default_model: kokoro        # <- switch the platform default here
  device: auto
  models:                      # per-model adapter config
    kokoro: { voice: hf_alpha }

routing:                       # use-case -> preference chain (first installed wins)
  phone_agent:        [kokoro, mock]              # low-latency branded voice
  realtime_streaming: [kokoro, mock]              # live agents / WebRTC
  content_creation:   [chatterbox, kokoro, mock]  # reels/YouTube; quality first
  premium_clone:      [chatterbox, mock]          # persona voice clone
  realtime: [kokoro, melotts, mock]               # capability tiers (back-compat)
  quality:  [chatterbox, styletts2, kokoro, mock]
  cloning:  [chatterbox, styletts2, f5-tts, mock]

cache: { enabled: true, namespace: voice_synthesis, directory: null }
profiles: { directory: null, require_consent: true }
pronunciation: { lexicons: [] }          # extra lexicon YAMLs
emotion: { strategies: {} }              # engine_id -> exaggeration|instruct|hint|none
streaming: { chunk_ms: 200, sample_rate: null, max_sentence_chars: 300 }
export: { format: wav, peak_dbfs: -1.0 }
```

Defaults encode the measured **Phase B2.3 benchmark** (see *Benchmark results &
model selection* below): Kokoro is the deployable real-time / low-latency tier;
Chatterbox heads the commercial quality/cloning chain; F5-TTS stays
non-commercial; XTTS v2 is benchmark-only. Promoting a model after a benchmark
round is a YAML edit, never a code change.

`voice.model_for_use_case("phone_agent", language="hi")` resolves a chain at
runtime; `voice.load_model(...)`, `voice.switch_model(...)` pin one explicitly.

## Benchmark results & model selection (Phase B2.3)

The two production-hardened models — **Kokoro** (real-time tier, B2.1) and
**Chatterbox** (cloning/quality tier, B2.2) — were benchmarked **on the same
machine** so the comparison is apples-to-apples.

**Environment:** Google Colab — **Tesla T4** (15 GB), **2 vCPU**, 12.7 GB RAM,
Python 3.12. **Instruments:** the permanent per-model smoke tests
(`smoke_kokoro.py`, `smoke_chatterbox.py`) for startup/RTF/VRAM/RAM, and the
production `VoiceBenchmark` harness (`run_benchmark`) over real dataset
conversation prompts (EN+HI) for corroborating per-prompt RTF + resource means.
Each model runs in its own venv (conflicting torch pins); numbers below are the
measured means.

### Head-to-head

| Metric | **Kokoro-82M** | **Chatterbox (Multilingual v2)** |
|---|---|---|
| Params / size | 82M (~0.4 GB) | 0.5B (~3.2 GB weights) |
| License (code+weights) | Apache-2.0 | MIT |
| Startup (adapter `load`) | ~0 s; first-synth pipeline build ~15 s (EN) / ~4 s (HI) | **~40 s** (0.5B backbone + S3 codec + voice encoder onto GPU) |
| **Warm RTF — GPU (T4)** | **~0.05** (EN 0.046 / HI 0.047)¹ | EN **1.07** / HI **1.49** (harness mean 1.34) |
| **Warm RTF — true CPU (2 vCPU)** | EN 1.82 / HI 1.96 (**not** real-time here) | not viable (research-only) |
| Peak VRAM | trivial (<0.5 GB; auto-uses T4) | **~3.5 GB** (`max_memory_allocated`; ~6.5 GB fp16 headroom) |
| Peak RAM | ~2.2–2.7 GB | ~3.0 GB |
| Cloning | ✗ (branded voice packs) | ✓ zero-shot (~7–20 s reference) |
| Emotion control | ✗ | ✓ `exaggeration` knob (0–1) |
| Streaming | good (chunked) | limited (no official low-latency path) |
| Languages (production) | EN, HI | EN, HI, Hinglish |
| Harness result (EN+HI conv.) | 12/12 passed, mean RTF **0.090**, peak RAM 2.2 GB | 8/8 passed, mean RTF **1.34**, peak RAM 3.0 GB |

¹ Kokoro's `KPipeline` auto-selects CUDA when a GPU is visible, so on the T4 it
runs GPU-assisted (RTF ~0.05) even though the 82M model is small. With the GPU
hidden, the 2-vCPU box gives RTF ~1.8–2.0 — **Kokoro needs a GPU or ≥4 CPU cores
for comfortably sub-1.0 RTF**; on a well-provisioned CPU (Phase A1.5 measured HI
RTF ~0.99 on a faster/more-core host) it is real-time without a GPU.

> **Quality observations** (engineering, not a listening test): both models
> produced clean, non-clipped, correctly-multilingual audio across every EN+HI
> case (0 failures, silence-ratio ~0.22–0.25). **Perceptual** cloning/emotion/
> naturalness quality requires the human listening protocol with the recorded
> reference set (`datasets/reference_audio/README.md`) — the synthetic reference
> used here validates the *mechanics*, not the fidelity. Research consensus:
> Chatterbox is top-two among open models for EN cloning with working emotion
> control and native Hindi; Kokoro is exceptional quality-per-parameter for a
> fixed branded voice.

### Recommendations

| "Best …" | Winner | Why |
|---|---|---|
| **Real-time model** | **Kokoro** | Warm RTF ~0.05 on GPU; chunked streaming; ~0 s load |
| **Cloning model** | **Chatterbox** | Only zero-shot cloner of the two; ~7–20 s reference |
| **CPU model** | **Kokoro** | Only CPU-real-time model (needs ≥4 cores / faster host); Chatterbox is GPU-only |
| **GPU model** | depends: **Kokoro** for latency, **Chatterbox** for quality/cloning | Kokoro ~0.05 RTF; Chatterbox ~3.5 GB VRAM, best quality |
| **Hindi model** | **Kokoro** for real-time, **Chatterbox** for cloned Hindi | Both native Hindi; Kokoro faster, Chatterbox clones + Hinglish |
| **English model** | **Chatterbox** (quality/cloning) · **Kokoro** (latency) | Chatterbox top-tier EN quality; Kokoro when latency/cost dominate |

### Production routing rules

Routing is **config-driven** (`tts/defaults.yaml → routing:`, resolved by
`EngineRouter`): the first adapter in a chain that is installed *and* satisfies
the request's language/cloning constraints wins. `mock` terminates every chain
so resolution never hard-fails in dev/CI.

| Use case | Chain | Rationale |
|---|---|---|
| **Phone agent** | `kokoro → mock` | Lowest latency, branded voice, CPU-friendly |
| **Realtime streaming** | `kokoro → mock` | Live agents / WebRTC; chunk-streamed, RTF ≪ 1 on GPU |
| **Content creation** | `chatterbox → kokoro → mock` | Reels/YouTube: best quality first, Kokoro fallback if GPU-scarce |
| **Premium voice clone** | `chatterbox → mock` | Requires zero-shot cloning (Kokoro can't clone) |

```
Phone Agent / Realtime Streaming ─▶ Kokoro   (latency tier)
Content Creation / Premium Clone ─▶ Chatterbox (quality + cloning tier)
```

Resolve at runtime with `voice.model_for_use_case("premium_clone", language="hi",
require_cloning=True)`.

### Deployment recommendations

- **Real-estate / phone voice AI, WhatsApp, live agents** → **Kokoro** on a small
  **GPU** (or a ≥4-core CPU box). RTF ~0.05 on a T4 leaves ample headroom for
  concurrency; ~0 s model load suits autoscaling. Set `streaming.sample_rate:
  8000` (telephony) / `16000` (WebRTC).
- **Reels / YouTube narration, digital influencers** → **Chatterbox** on a GPU
  with **≥6 GB VRAM** (T4 measured ~3.5 GB peak, comfortably fits 15 GB). Budget
  a **~40 s cold start** — keep the worker warm; batch/queue utterance-scale jobs
  rather than expecting interactive latency. Long-form goes through
  `generate(..., long_form=True)` (sentence chunk → crossfade → normalize).
- **Persona voice clones** → **Chatterbox** with a clean **~20 s** reference
  (A1.5 study); the `exaggeration` knob drives emotion. Every output carries the
  imperceptible PerTh watermark (provenance).
- **Cost / CPU-only fallback** → **Kokoro** on a well-provisioned CPU host; on a
  2-vCPU box it is *not* real-time (RTF ~1.8–2.0), so size the host accordingly.
- **One GPU, mixed workload** → both fit the T4 together (Kokoro <0.5 GB +
  Chatterbox ~3.5 GB VRAM); run them in their isolated venvs and route per use
  case.

Re-running the benchmark: `.venvs/<model>/bin/python -m
voice_engine.scripts.run_benchmark --adapters <model> --languages en hi
--categories conversation --no-streaming` (add `--reference-audio` for
Chatterbox). Per-model smoke tests give the startup/VRAM/RTF snapshot.

## Feature notes

- **Voice profiles** — `clone_voice()` validates the reference through the
  adapter (`validate_reference`), builds the profile, and (by default)
  persists it. Saving requires consent metadata; the reference clip is
  copied into the store. Use ~20 s references (A1.5 study recommendation).
- **Emotion** — pass `emotion="excited"` or
  `EmotionSpec(Emotion.EXCITED, intensity=0.8)`. Strategy per engine:
  Chatterbox exaggeration knob, CosyVoice/Parler style instructions, plain
  hints elsewhere; engines without emotion control ignore it cleanly.
- **Pronunciation** — the built-in real-estate lexicon
  (`pronunciation/default_lexicon.yaml`) ships RERA/EMI/BHK rules; add
  project/builder lexicons via `pronunciation.lexicons`. Applied before
  caching, so fixes invalidate stale audio automatically.
- **Streaming** — native `StreamingTTSEngine` adapters stream directly;
  every other engine gets sentence-chunked fallback streaming. Set
  `streaming.sample_rate: 8000` for telephony or `16000` for
  Pipecat/WebRTC. `astream()` serves async pipelines.
- **Caching** — keyed on engine + voice + text + language + speed + emotion
  + seed + extra. Re-rendering an unchanged reel line is free.
- **Long form** — `generate(..., long_form=True)` routes through the
  quality pipeline (sentence chunking, crossfade joins, peak
  normalization) so utterance-scale engines narrate minutes of script.
- **Export** — `voice.export(result, "clip.mp3")`; WAV/PCM need no
  dependencies, compressed formats use the platform FFmpeg
  (`.venvs/_tools/ffmpeg`) or any `ffmpeg` on PATH.

## Consumers

- **Reel/YouTube narration**: `generate(script, long_form=True,
  model_id=voice.model_for_use_case("quality"))`, then `export(...)` to the
  container the editor needs.
- **Talking avatars (A3/A4)**: consume `SynthesisResult.audio_path` +
  `metadata` (word-timestamp extraction is an A2 milestone-6 follow-up).
- **Real-estate voice AI / WhatsApp**: `astream(...)` with
  `streaming.sample_rate: 8000/16000`; the Kokoro chain serves Hindi at
  **RTF ~0.05 on a T4** (B2.3) — real-time with wide headroom — or RTF ~1–2 on a
  small CPU box (size for ≥4 cores or a GPU; see *Benchmark results*).
- **Benchmark**: `VoiceBenchmark` obtains every adapter through
  `VoiceEngine.load_model()`, so it measures exactly what production serves.

## Testing

`python -m pytest voice_engine/tests foundation/tests` — the A2 suites
(`test_voice_engine.py`, `test_profile_manager.py`, `test_pronunciation.py`,
`test_emotion.py`, `test_streaming_manager.py`, `test_pipelines.py`,
`test_tts_service.py`) run dependency-free on the mock adapter, like all
platform tests.
