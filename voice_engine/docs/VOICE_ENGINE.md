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
  realtime: [kokoro, melotts, mock]
  quality: [chatterbox, styletts2, kokoro, mock]
  cloning: [chatterbox, styletts2, f5-tts, mock]

cache: { enabled: true, namespace: voice_synthesis, directory: null }
profiles: { directory: null, require_consent: true }
pronunciation: { lexicons: [] }          # extra lexicon YAMLs
emotion: { strategies: {} }              # engine_id -> exaggeration|instruct|hint|none
streaming: { chunk_ms: 200, sample_rate: null, max_sentence_chars: 300 }
export: { format: wav, peak_dbfs: -1.0 }
```

Defaults encode the measured Phase A1.5 verdicts (`docs/PHASE_A15_REPORT.md`):
Kokoro is the deployable real-time tier; Chatterbox heads the commercial
quality/cloning chain; F5-TTS stays non-commercial; XTTS v2 is benchmark-only.
Promoting a model after the A2 GPU benchmark round is a YAML edit.

`voice.model_for_use_case("realtime", language="hi")` resolves a chain at
runtime; `voice.load_model(...)`, `voice.switch_model(...)` pin one explicitly.

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
  `streaming.sample_rate: 8000/16000`; Kokoro chain serves Hindi at RTF ≈ 1
  on CPU today.
- **Benchmark**: `VoiceBenchmark` obtains every adapter through
  `VoiceEngine.load_model()`, so it measures exactly what production serves.

## Testing

`python -m pytest voice_engine/tests foundation/tests` — the A2 suites
(`test_voice_engine.py`, `test_profile_manager.py`, `test_pronunciation.py`,
`test_emotion.py`, `test_streaming_manager.py`, `test_pipelines.py`,
`test_tts_service.py`) run dependency-free on the mock adapter, like all
platform tests.
