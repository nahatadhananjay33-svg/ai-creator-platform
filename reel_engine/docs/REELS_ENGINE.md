# Reels Engine — Walking Skeleton (Phase C2)

The Reels Engine is the platform's **orchestration layer**: it turns structured
content into production-ready social videos. Phase C1 designed the full
architecture; **Phase C2 builds the deterministic skeleton** — the Timeline IR,
two renderers, the export pipeline, and the benchmark — with **no AI, no GPU, no
Voice/Avatar/Caption integration**. Those generative stages arrive in C3+ and
simply *populate* the IR this phase proves.

The core idea (C1): the engine is a **compiler**. A generative front-end (later)
produces a declarative **Timeline** (the intermediate representation); a
deterministic back-end **lowers** that Timeline to video. C2 implements the IR
and the back-end. Because rendering is a pure function of the Timeline plus its
assets, caching / resumability / incremental render come essentially for free in
later phases.

```
Scene list ──► Timeline (IR, JSON, content-hashed) ──► Renderer ──► master + exports
              (interfaces/ + timeline/)                (render/)     (exporters/)
```

## Architecture

Reuses the platform foundation (config, logging, cache, benchmarking, video/
audio I/O) and follows the engine module pattern (frozen `interfaces/`, no
cross-engine imports). C2 packages:

| Package | Responsibility |
|---|---|
| `reel_engine/interfaces/` | **Frozen** value types — the contract others depend on |
| `reel_engine/timeline/` | The IR: builders, validation, JSON serde, content hashing |
| `reel_engine/render/` | The back-end: `MockRenderer`, `FFmpegRenderer`, ffprobe |
| `reel_engine/exporters/` | Per-platform aspect profiles + letterbox math |
| `reel_engine/config/` | `defaults.yaml` bound to frozen dataclasses |
| `reel_engine/benchmark/` | Deterministic render/export benchmark (BenchmarkCase) |
| `reel_engine/scripts/` | `render_demo`, `run_benchmark` CLIs |
| `reel_engine/tests/` | Hermetic tests (no FFmpeg/GPU/AI) + gated FFmpeg tests |

## Timeline IR

A layered, declarative, immutable document (`interfaces/types.py`):

```
Timeline
├── schema_version                       # versioned; loader rejects newer schemas
├── meta: TimelineMeta                    # title, width, height, fps, default bg (no timestamps)
└── scenes: tuple[Scene]                  # play order; duration is derived, never stored
      Scene
      ├── scene_id, index, duration_s
      ├── tracks: tuple[Track]            # background | text | audio (z-order = order)
      │     Track.clips: tuple[Clip]
      │       Clip: solid_color | text | silent_audio
      │         (+ inert C3+ fields: source AssetRef, box/PIP, keyframes)
      └── transition_in/out: Transition   # C2: "cut" only
```

- **Immutable** — frozen dataclasses, tuple collections; a built Timeline cannot
  be mutated in place.
- **Forward-compatible** — fields later phases need (asset hashes, per-clip
  `box`/`keyframes`, non-cut transitions) exist now, inert, so C3+ populates them
  without a schema break.
- **Serde** (`timeline_to_json` / `timeline_from_json`) — lossless, sorted-key
  JSON; the portable `project.json`. The loader rejects a `schema_version` newer
  than it understands rather than mis-parsing.
- **Content hashing** (`timeline_content_hash`) — SHA-256 over canonical JSON.
  The schema carries **no volatile fields**, so the same reel always hashes the
  same, and the hash is stable across a serde round-trip. This is the future
  render-cache / scene-reuse key (`scene_content_hash` per scene).
- **Validation** (`validate_timeline`) — renderability checks: supported schema,
  even encoder-friendly dimensions, positive fps/durations, a background per
  scene, in-range clip times, non-empty text. `validate_or_raise` reports every
  problem at once.

Build one with `build_demo_timeline()` or `storyboard([(color, text, seconds), …])`.

## Renderers

Both implement one contract — `TimelineRenderer.render(RenderRequest) ->
RenderResult` — and share the frame-count/dimension math so timing is identical.

- **`MockRenderer`** (`render/mock_renderer.py`) — **hermetic, zero-dependency**,
  the analogue of the platform's mock adapters. Lowers a Timeline to a real,
  readable **uncompressed BGR24 AVI** (solid backgrounds + a centred title-card
  placeholder band) plus a **silent WAV** bed and an **SRT** caption sidecar,
  using only the stdlib writers in `foundation.shared_utils`. Written at a
  **proxy resolution** (longest side capped by `render.mock_max_dim`) that
  preserves the target aspect exactly, so hermetic tests stay tiny and fast.
  **Byte-for-byte deterministic.** Also emits per-profile exports via
  nearest-neighbour scale+pad.
- **`FFmpegRenderer`** (`render/ffmpeg_renderer.py`) — the **real MP4**. Per
  scene: one `lavfi` colour source + one `drawtext` overlay; scenes are
  **stream-copy concatenated**; each export is a `scale`+`pad` re-encode.
  Deliberately trivial filtergraphs. **C2 scope only: background, text overlay,
  concatenation, export — no transitions, effects, PIP, or animation.** Finds a
  system font; degrades to solid-only if none is present.

Pick with config (`render.renderer: ffmpeg|mock`) or `render_timeline(..., renderer=)`.

## Exports

`exporters/profiles.py` ships the three required aspects; platform names map
onto these shapes:

| Profile | Resolution | Aspect | Targets |
|---|---|---|---|
| `reel_9x16` | 1080×1920 | 9:16 | IG Reels · YT Shorts · TikTok · FB Reels |
| `square_1x1` | 1080×1080 | 1:1 | Square feed (IG/FB/LinkedIn) |
| `landscape_16x9` | 1920×1080 | 16:9 | YouTube · landscape |

The master is fitted into each profile by centred **letterbox** (`fit_box`,
pure/unit-tested): scale-to-fit preserving aspect, then pad — even dimensions
enforced for `yuv420p`. The FFmpeg backend expresses this as
`scale=…:force_original_aspect_ratio=decrease,pad=…`; the mock backend scales
pixels directly. Adding TikTok/LinkedIn variants later is a one-line registry
entry.

## Benchmarks

`benchmark/` reuses `foundation.benchmarking` (so it inherits resource
monitoring + CSV/JSON reporting). A fixed demo timeline is the deterministic
workload; one case measures **startup, render (master), export (delta), render
FPS, output duration, memory**.

```bash
python -m reel_engine.scripts.run_benchmark                    # mock (hermetic)
python -m reel_engine.scripts.run_benchmark --renderer ffmpeg  # real encode
```

Measured on the Colab box (2 vCPU, T4 present but **CPU-only encode**; 3 scenes ×
2 s = 6 s, 30 fps):

| Renderer | Resolution | Startup | Render (master) | Export (3 profiles) | Render FPS | Peak RSS |
|---|---|---|---|---|---|---|
| mock (proxy 90×160) | 1080×1920 | ~0 ms | ~99 ms | ~398 ms | ~2076 | ~568 MB |
| ffmpeg (`libx264`) | 540×960 | ~0.5 ms | ~2.9 s | ~11.9 s | ~62 | ~533 MB |

(FPS = total frames ÷ render seconds. The mock is a structural proxy; the FFmpeg
figure is a real CPU `libx264` encode — GPU `nvenc` is a later opt-in.)

## Validation

The canonical walking-skeleton reel — blue **"Title"** → green **"Subtitle"** →
red **"Call To Action"** — rendered, exported, and probed for playability:

```bash
python -m reel_engine.scripts.render_demo               # ffmpeg -> real MP4
python -m reel_engine.scripts.render_demo --renderer mock
```

Confirmed: a playable MP4 master at the requested resolution/aspect, correct
duration (≈ Σ scene durations), and all three exports at 1080×1920 / 1080×1080 /
1920×1080. `python -m pytest reel_engine/tests` runs fully hermetic (no FFmpeg
needed; the FFmpeg tests skip when it is absent).

## Limitations (by design, this phase)

- **No AI / generative stages** — no Voice, Avatar, Caption, Script engine, asset
  providers, templates, branding, music, effects, or transitions. C3+.
- **Backgrounds + centred text only** — no PIP, keyframes, camera moves, or
  animated captions. The IR carries these fields inert.
- **Mock output is a low-res proxy** — legible text and full resolution come from
  the FFmpeg renderer.
- **`drawtext` escaping is minimal** — fine for simple titles; complex
  punctuation/RTL is a later concern.
- **CPU `libx264` only** — GPU `nvenc` and parallel/incremental rendering are
  planned (C4/C5).
