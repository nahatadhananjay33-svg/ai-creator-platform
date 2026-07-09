# Music & Audio Mixing Engine — Timeline-Native Audio (Phase C8)

The Music Engine makes **background music a first-class citizen of the Timeline**.
Music is *data*, not a renderer special-case: the engine builds a validated
`MusicTrack` (a looped, faded, envelope-shaped, speech-ducked bed) and the
renderer **mixes** that track under the voice. No soundtrack is ever hardcoded
into the renderer.

It is **100% deterministic and rule-based**. There is **no AI music generation,
no streaming APIs, no licensing system, no beat detection, no AI soundtrack
selection, no speech enhancement, no noise removal** — those belong to later
phases. The same `(timeline, config)` always mixes to the same audio, byte for
byte, on any machine (the DSP is pure Python, no numpy/ffmpeg dependency).

```
reel duration + soundtrack ─► plan ─► resolve (local file / procedural bed)
                          ─► MusicTrack ─► Timeline.music_tracks ─► renderer mixes ─► MP4
```

It slots into the pipeline after visual assets, then reuses the rest of the
platform unchanged:

```
Script ─► Storyboard ─► Voice ─► Avatar ─► Timeline ─► Caption Track
       ─► Branding Track ─► Visual Asset Track ─► Music Track ─► Renderer ─► playable MP4
```

**Audio compositing (bottom → top): voice bed → music beds → soft limiter.**
The video compositing order (base → assets → captions → branding) is unchanged.

## Architecture

Reuses the platform foundation (config, logging, benchmarking) and the engine
module pattern. The **frozen music IR lives in `reel_engine.interfaces`** (the one
Timeline contract) and the **shared mixer lives renderer-side** in
`reel_engine.render.music` — exactly like visual assets, where the geometry math
lives in `reel_engine.render.assets`. The Music Engine depends on the Reels
Engine, never the reverse.

| Package | Responsibility |
|---|---|
| `foundation/shared_utils/audio_mix.py` | Pure, dependency-free sample DSP: int16↔float, resample, loop/crossfade, fades, envelope, ducking, mix, soft limiter |
| `reel_engine/render/music.py` | **Renderer-side lowering**: `resolve_music`, `speech_windows`, `build_voice_bed`, `mix_timeline_audio` (shared by both backends) |
| `music_engine/providers/` | `LocalMusicProvider` (local WAV) + `ProceduralSoundtrack` (deterministic chord-bed generator) — no downloads/streaming/AI |
| `music_engine/mixing/` | Scene-aware planning (`plan_background_music`, `plan_for_timeline`) + re-export of the shared mixer |
| `music_engine/timeline/` | `build_music_track` — specs + config → validated `MusicTrack` |
| `music_engine/config/` | `defaults.yaml` bound to a frozen `MusicEngineConfig` |
| `music_engine/benchmark/` | Deterministic loading/mixing/render/export benchmark |
| `music_engine/scripts/` | `render_music_demo`, `run_benchmark` CLIs |
| `music_engine/engine.py` | `MusicEngine` facade: intent/specs → `MusicTrack` |

## Timeline integration

Phase C8 extends the Timeline IR **additively** (schema `v4 → v5`); v1..v4
projects load unchanged (they simply carry no music). All music types are
immutable `@dataclass(frozen=True)`, timed in **absolute reel time**:

| Type | Meaning |
|---|---|
| `AudioFade` | A clip's fade-in / fade-out seconds (+ curve; C8 renders linear) |
| `AudioEnvelope` | Piecewise-linear `(time_s, gain)` volume automation over the reel |
| `DuckingRule` | Deterministic speech ducking: `duck_level` under speech, `attack_s`/`release_s` ramps, `pad_s` |
| `LoopRule` | Tile a short bed to fill the window, with an optional `crossfade_s` seam |
| `MusicClip` | One bed: source, window, `gain`, `source_offset_s`, fade, envelope, loop, ducking, `mute_sections` |
| `MusicTrack` | An ordered set of clips + a track master `gain` → `Timeline.music_tracks` |

The renderer **consumes** the track — it is not special-cased. Both backends call
the same `mix_timeline_audio`; the mock writes the mix as its WAV sidecar, the
FFmpeg backend extracts the master's voice audio, mixes, and remuxes over the
untouched video (`-c:v copy`) before export, so every profile inherits an
identical, non-clipping voice+music mix.

## Mixing

`mix_timeline_audio(timeline, sr)` builds the reel's audio in the normalized
float domain, then quantizes to 16-bit PCM:

1. **Voice bed** — each scene's real audio file summed at its offset (silence
   when a scene has only a silent bed, e.g. the hermetic mock path).
2. **Each music clip** — load the source, then (all multiplicative, so
   order-independent):
   - **loop** the source to the window length (`LoopRule`, optional crossfade),
   - apply the **base gain** (`clip.gain × track.gain`),
   - apply **fade-in / fade-out** (`AudioFade`),
   - apply the **volume envelope** (`AudioEnvelope`),
   - apply **speech ducking** (`DuckingRule`),
   - zero any **mute sections**,
   - mix into the reel at `start_s`.
3. **Soft limiter** — a `tanh` knee guarantees `|sample| < 1.0`, so the mix
   **can never clip** regardless of how many beds overlap or how hot the gains.

### Speech ducking (deterministic)

Ducking is driven by the reel's **speech windows** — the caption segments, else
the spoken scenes — **not** by analysing the audio waveform. So it is 100%
deterministic and identical across renderers: while narration plays the music
gain ramps down to `duck_level` (over `attack_s`); in the gaps it ramps back to
full (over `release_s`). This is classic side-chain ducking expressed as a plan,
with none of the non-determinism of live envelope-following — and no beat
detection or AI.

## Configuration

`music_engine/config/defaults.yaml`, layered like every engine (packaged defaults
← user file ← `AICP__music__*` env ← explicit overrides). Nothing here can turn
mixing non-deterministic.

| Key | Default | Meaning |
|---|---|---|
| `volume` | `0.18` | base music level under the voice (0..1) |
| `track_gain` | `1.0` | track master gain (on top of each clip's gain) |
| `default_soundtrack` | `ambient` | built-in procedural bed: `ambient`/`upbeat`/`lofi`/`cinematic` |
| `ducking.enabled` | `true` | lower music while narration plays |
| `ducking.level` | `0.35` | music multiplier under speech (lower = more duck) |
| `ducking.attack_s` / `release_s` | `0.25` / `0.60` | ramp-down / ramp-up times |
| `ducking.pad_s` | `0.15` | widen each speech window (avoids pumping) |
| `fade.fade_in_s` / `fade_out_s` | `1.5` / `2.0` | music rise at the start / tail at the end |
| `fade.curve` | `linear` | `linear` \| `equal_power` (C8 renders linear) |
| `loop.enabled` | `true` | tile the bed to fill a reel longer than the source |
| `loop.crossfade_s` | `0.5` | overlap between loop iterations (0 = hard seam) |

## Usage

```python
from music_engine import MusicEngine

engine = MusicEngine()
# whole-reel background bed from config defaults (pick a built-in soundtrack):
music = engine.generate(reel_duration_s, soundtrack="ambient", asset_dir=work)
# ...or scene-aware: fades matched to the timeline's branding intro/outro:
music = engine.generate_for_timeline(timeline, soundtrack="upbeat", asset_dir=work)

import dataclasses
timeline = dataclasses.replace(timeline, music_tracks=(music,))   # native track
# the renderer mixes it — no other change needed.
```

Bring your own music with `source="/path/to/bed.wav"` (a local file, never a
download); the built-in `ProceduralSoundtrack` exists so the demo and tests have
real, deterministic audio with no assets.

## Demo & validation

```
python -m music_engine.scripts.render_music_demo                  # ffmpeg MP4
python -m music_engine.scripts.render_music_demo --renderer mock  # hermetic proxy
python -m music_engine.scripts.render_music_demo --soundtrack cinematic
```

The demo builds a complete reel — talking head + captions + branding + visual
assets + **background music** — renders a playable MP4 + `reel_9x16` /
`square_1x1` exports, and verifies the **backend-independent** voice+music mix the
renderer muxes: background music present, **speech ducking** (music dips under the
caption windows), **fade in/out**, **looping** (a short bed tiled to fill the
reel), **correct timing**, **no clipping**, and a **byte-identical** deterministic
mix. The master + exports are then probed for playability and an audio stream.

## Benchmark

```
python -m music_engine.scripts.run_benchmark
```

Measures music loading, mixing overhead, render overhead (with vs without music),
export, peak memory, and FPS over a fixed reel. Pure CPU and fully hermetic — no
FFmpeg, GPU, model, or network.

## Regression tests

`music_engine/tests/`, `reel_engine/tests/test_music_*`, and
`foundation/tests/test_audio_mix.py` — fully hermetic and deterministic (no
renderer, ffmpeg, GPU, model, network). Cover the DSP primitives, the `MusicTrack`
IR + serde + validation, mixing (looping, envelopes, ducking, mute, no-clip,
determinism), renderer integration, and the engine (providers, planning, builder,
config). Every built track runs through the shared Timeline validator, so the
engine can never emit an unrenderable music track.

```
python -m pytest music_engine/tests reel_engine/tests/test_music_ir.py \
                 reel_engine/tests/test_music_render.py foundation/tests/test_audio_mix.py -q
```

## Limitations (Phase C8 scope)

- **Deterministic mixing only** — ducking follows the *plan* (caption/scene
  windows), not the waveform; there is no side-chain compressor listening to the
  actual speech. This is by design (reproducible, backend-identical).
- **Procedural beds are placeholders** — the built-in soundtracks are simple
  chord pads so the pipeline has real, license-free, deterministic audio; they
  are not a music library. Bring a local WAV for real tracks.
- **Linear fades / mono mix** — `equal_power` fades are carried but rendered
  linear; the mix is mono (the platform's canonical interchange format).
- **No generation / search / licensing / scheduling** — the engine only mixes
  what it is given or deterministically generates.

## Future AI soundtrack integration

The `MusicTrack` shape is frozen precisely so AI can slot in **without touching
the mixer or the renderer**:

- **AI soundtrack selection** — a model picks a bed for the reel's mood/energy;
  it still produces a `MusicClip` with a resolved `source`, mixed the same way.
- **AI music generation** — a generative model writes the source WAV; it becomes
  a `MusicClip.source` like any other file. The loop/fade/envelope/duck plan is
  unchanged.
- **Licensing / stock providers** — a `MusicProvider` that resolves a licensed
  track (with attribution metadata) drops in beside `LocalMusicProvider`.
- **Beat-aware editing** — a later phase can populate `AudioEnvelope` /
  `mute_sections` from detected beats; the IR already carries them.

None of these change the deterministic mixer or the renderer — they only change
how a `MusicClip`'s source and parameters are chosen.
