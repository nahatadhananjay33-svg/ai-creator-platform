# End-to-End Pipeline — AI Creator Platform v1 (Phase C3)

**Version 1 of the AI Creator Platform**: the first *complete* path from a line
of text to a playable social reel. Phase C2 built the deterministic Reels Engine
skeleton (Timeline IR + renderers + exports); the Voice and Avatar engines were
built and benchmarked in parallel. **Phase C3 wires them together** into one
orchestration layer and proves the architecture end to end — nothing more.

This is a *walking skeleton*. It deliberately does **not** add captions, scene
planning, script generation, b-roll, stock footage, music, branding, templates,
effects, transitions, an editing UI, asset search, or scheduling. Those are C4+.
What it proves is that the seams between the engines line up and that a real MP4
falls out the far end with no manual intervention.

```
  script.txt ─► Voice Engine ─► Avatar Engine ─► Timeline IR ─► Renderer ─► reel.mp4
  reference_face                (talking head)   (one scene)    (ffmpeg)    (+ exports)
```

## Architecture

The orchestrator is a thin coordination layer over the *existing* engines — it
reimplements none of their logic. Each stage sits behind a small protocol so the
whole pipeline is testable with deterministic fakes and no model weights.

| Package | Responsibility |
|---|---|
| `reel_engine/orchestrator/config.py` | `PipelineConfig` — layered YAML/env config; reuses the Reels Engine `RenderConfig`/`ExportConfig` |
| `reel_engine/orchestrator/adapters.py` | `VoiceStage`/`AvatarStage` protocols + engine-backed `EngineVoiceStage`/`EngineAvatarStage` |
| `reel_engine/orchestrator/pipeline.py` | `CreatorPipeline` — times the five stages, builds+validates the Timeline, renders |
| `reel_engine/orchestrator/benchmark.py` | End-to-end per-stage timing/memory/GPU benchmark |
| `reel_engine/orchestrator/assets/` | Demo `script.txt` + `reference_face.png` |
| `reel_engine/scripts/run_pipeline.py` | Pipeline CLI |
| `reel_engine/scripts/run_pipeline_benchmark.py` | Benchmark CLI |

The five stages:

1. **Voice** — `EngineVoiceStage` calls the production `VoiceEngine` (Kokoro by
   default; Chatterbox or `mock` by config). Text → a speech **WAV**; reports
   sample rate + duration.
2. **Avatar** — `EngineAvatarStage` calls `avatar_engine.models.create_adapter`
   (MuseTalk by default; LatentSync or `mock`). `(reference, speech WAV)` → a
   **talking-head video**. The reference is routed to `source_image` or
   `driving_video` according to the adapter's declared `REQUIRED_INPUTS`, so one
   config field works for image-driven and video-driven model families alike.
3. **Timeline** — a single **video scene** (`Scene.from_video`) carrying the
   footage on a `video` track and the authoritative speech WAV on an `audio`
   track. Validated, then serialized to `project.json` (the resumable anchor
   later phases build on).
4. **Render** — the C2 deterministic `FFmpegRenderer`, now able to lower a video
   scene (the C3/M1 fix): it letterboxes the footage into the master frame at the
   configured resolution/fps and muxes the real speech audio.
5. **Export** — the master is fitted into each requested platform/aspect profile
   (`reel_9x16`, `square_1x1`, `landscape_16x9`) via the shared scale+pad math.

### The one architectural change C3 required

The C2 renderer could only *synthesize* solid-colour scenes, so generated
footage had no path through the Timeline. The smallest fix (Phase C3/M1) added a
**video-backed scene**:

- `Scene.from_video()` + `video`/`audio_file` clip kinds (frozen IR, forward-compatible).
- Validation accepts them and treats a scene as renderable if it has a background
  **or** a video track.
- `FFmpegRenderer._render_video_scene()` decodes the footage, letterboxes it, and
  muxes real audio.

Serde, hashing, and the export pipeline are schema-generic and needed no change.

## Configuration

Everything is configuration, not code (`reel_engine/orchestrator/defaults.yaml`),
layered `defaults <- user YAML <- AICP__section__key env <- overrides`:

```yaml
voice:
  model: kokoro        # kokoro (default) | chatterbox | mock
  language: en
  speed: 1.0
  device: auto
avatar:
  model: musetalk      # musetalk (default) | latentsync | mock
  device: auto
render:
  renderer: ffmpeg     # ffmpeg (real MP4) | mock (hermetic raw-AVI proxy)
  width: 1080
  height: 1920
  fps: 30
  bitrate: "6M"
  audio_sample_rate: 44100
export:
  profiles: [reel_9x16]          # + square_1x1, landscape_16x9
reference_face: null             # null -> packaged demo face
output_dir: null                 # null -> reel_engine/orchestrator/output
```

Override precedence example — switch to Chatterbox voice + LatentSync avatar at
720×1280 without touching a file:

```bash
AICP__voice__model=chatterbox AICP__avatar__model=latentsync \
  python -m reel_engine.scripts.run_pipeline --width 720 --height 1280
```

## Running the pipeline

**Hermetic demo** (no weights, no GPU — dependency-free `mock` voice + avatar,
real ffmpeg MP4):

```bash
python -m reel_engine.scripts.run_pipeline \
  --voice-model mock --avatar-model mock \
  --script "Hello from the AI Creator Platform."
```

**Production models** (Kokoro + MuseTalk installed — see the Voice/Avatar engine
install docs):

```bash
python -m reel_engine.scripts.run_pipeline \
  --script-file my_script.txt --reference my_face.jpg \
  --profiles reel_9x16 square_1x1
```

**From Python:**

```python
from reel_engine.orchestrator import load_pipeline_config, CreatorPipeline

cfg = load_pipeline_config(overrides={"voice": {"model": "mock"},
                                      "avatar": {"model": "mock"}})
result = CreatorPipeline(cfg).run(script="One line becomes a reel.")
print(result.output_path, result.duration_s, result.timings)
```

Each run writes, under `output_dir/<name>/`: `speech.wav`, the avatar video,
`project.json` (the Timeline), the master `<name>.mp4`, and one file per export
profile.

**Benchmark** — per-stage voice/avatar/timeline/render/export/total time, RSS,
and (on GPU hosts) peak GPU memory + utilisation:

```bash
python -m reel_engine.scripts.run_pipeline_benchmark --repetitions 3
```

## Validation

The end-to-end integration test (`tests/test_orchestrator.py::
test_end_to_end_real_engine_stack`, ffmpeg-gated) and the demo CLI both confirm a
single command produces a reel that is **playable**, has the **correct duration
and resolution**, contains **muxed audio**, has **no missing assets**, and
completes with **no pipeline failures**. Hermetic tests (fake stages + mock
renderer) pin orchestration, Timeline generation, configuration, error handling,
and renderer integration with no models or ffmpeg. Exactly one integration test
exercises the real engine stack.

## Known limitations (by design — this is a skeleton)

- **One scene, no editing.** No transitions, overlays, captions, or multi-scene
  composition. `Scene.from_video` is the minimal video scene.
- **Audio authority.** The speech WAV is muxed over the footage; scene length
  follows the generated footage and the renderer trims to the shorter of
  footage/audio, so a small voice/avatar mismatch cannot overrun.
- **No caption/planning/branding/music/b-roll** — explicitly out of scope (C4+).
- **Real models need their weights/GPU.** Kokoro and MuseTalk/LatentSync must be
  installed to run the production path; the `mock` voice+avatar make the whole
  pipeline runnable anywhere (they validate plumbing, not audio/video quality).
- **Mock render backend** produces a proxy frame for video scenes (it does not
  decode media); the real, legible reel comes from the `ffmpeg` backend.

## Future expansion (C4+)

The Timeline IR already carries inert, defaulted fields for what comes next, so
these populate the same schema without breaking it:

- **Caption Engine** → a `text`/caption track synced to the speech WAV.
- **Scene Planner / Script Generator** → many scenes instead of one.
- **B-roll, stock footage, music, branding, templates** → additional tracks and
  asset kinds; the content-addressed `AssetRef.content_hash` is reserved for the
  asset store.
- **Transitions & effects** → the `Transition` type and per-clip `box`/`keyframes`
  fields already exist, unused, for fades/PIP/ken-burns.
- **Resumable/incremental render** → `project.json` + the deterministic Timeline
  content hash make caching a natural next step.
