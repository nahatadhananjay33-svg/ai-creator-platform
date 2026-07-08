# Caption Engine — Timeline-Native Captions (Phase C4)

The Caption Engine turns speech (a script plus its audio/duration) into
**captions that live natively in the Timeline IR**. Captions are *data*, not a
renderer special-case: the engine produces a validated, styled `CaptionTrack`,
and the renderer simply **lowers** that track to on-screen text. Nothing about
captions is hardcoded in the renderer.

```
script ──► timing source ──► CaptionTrack (native Timeline track) ──┐
 (audio)   (heuristic/ASR)     builder + style + animation          │
                                                                     ▼
                                          Renderer ──► MP4 (captions burned in)
                                              └──────► SRT + WebVTT + JSON + Timeline captions
```

This slots into the end-to-end pipeline between the Timeline IR and the
renderer:

```
Script ─► Voice ─► Avatar ─► Timeline IR ─► Caption Track ─► Renderer ─► playable MP4
                                                                       + SRT + WebVTT + JSON
```

## Architecture

Reuses the platform foundation (config, logging, benchmarking, audio I/O) and
the engine module pattern. The **frozen caption IR types live in
`reel_engine.interfaces`** — the single Timeline contract — so the Caption
Engine depends on the Reels Engine, never the reverse.

| Package | Responsibility |
|---|---|
| `caption_engine/providers/` | Timing sources: `TimingProvider` protocol + deterministic `HeuristicTimingProvider` (no ASR/GPU) |
| `caption_engine/timeline/` | `build_caption_track` — lowers a `Transcript` into the frozen `CaptionTrack` per caption *kind* |
| `caption_engine/styles/` | Reusable `CaptionStyle` presets (classic/modern/bold/minimal/youtube/instagram/tiktok) |
| `caption_engine/export/` | Subtitle export: SRT, WebVTT, JSON, Timeline captions |
| `caption_engine/config/` | `defaults.yaml` bound to a frozen `CaptionEngineConfig` |
| `caption_engine/benchmark/` | Deterministic generation/render/export benchmark (`BenchmarkCase`) |
| `caption_engine/scripts/` | `render_caption_demo`, `run_benchmark` CLIs |
| `caption_engine/engine.py` | `CaptionEngine` facade: `text (+audio/duration) → CaptionTrack` |
| `reel_engine/render/captions.py` | **Renderer-side lowering**: `CaptionTrack → CaptionDraw` ops (shared by both backends) |

The facade wires three pieces and nothing else:

```
timing provider  →  style resolution  →  builder
```

Because the default provider is a deterministic heuristic (length-proportional
word timing, no model), `CaptionEngine.generate(...)` is fully reproducible and
hermetic — the same `(text, duration)` always yields byte-identical captions.

## Timeline integration

Phase C4 extends the Timeline IR **additively** (schema `v1 → v2`); v1 projects
(no captions) load unchanged. All caption types are immutable
`@dataclass(frozen=True)`, timed in **absolute reel time**:

| Type | Meaning |
|---|---|
| `WordTiming` | One word + its absolute `[start_s, end_s]` window |
| `CaptionSegment` | One on-screen phrase/sentence, optionally carrying per-word timings |
| `CaptionStyle` | How captions look (font, colours, outline, shadow, box, position, safe margins, …) |
| `CaptionAnimation` | Simple per-caption animation (`none` / `fade` / `pop`) |
| `CaptionTrack` | Ordered segments + one shared style + animation, with a `kind` |
| `Timeline.caption_tracks` | New tuple field carrying the tracks |

**Supported caption kinds** (`CaptionTrack.kind`):

- `sentence` — one phrase on screen at a time (segment windows).
- `word` — one word at a time (needs per-word timings).
- `karaoke` — the full phrase is shown; each word highlights as it is spoken.
- `static` — the whole transcript collapsed into one card for the entire track.

**Synchronization is validated** by `reel_engine.timeline.validate` before any
render (explicit, all-at-once error messages):

- captions never exceed the reel/audio duration;
- segment timing is monotonic and non-overlapping in absolute time;
- word timings are monotonic and stay **inside** their segment;
- `word`/`karaoke` tracks must carry per-word timings;
- style fields are sane (valid RGB, known alignment/position, safe margins in range).

The track serializes losslessly through the existing Timeline JSON serde and is
covered by the content hash, so caption-bearing projects cache and resume like
any other.

## Renderer

The renderer was **extended, not redesigned**. One shared module,
`reel_engine/render/captions.py`, lowers a `CaptionTrack` into ordered,
absolutely-timed `CaptionDraw` operations (sentence → wrapped lines; word →
per-word; karaoke → a full-phrase base layer in `primary_color` plus a per-word
`highlight_color` overlay; `static` → one card). Positions and colours are
resolution-independent (fractions + RGB), so both backends place captions
identically.

- **`FFmpegRenderer`** burns captions into the master in **one `drawtext` pass**
  *before* export, so every aspect profile inherits them. Each `CaptionDraw`
  becomes a `drawtext` with an `enable='between(t,…)'` time gate and expression
  positioning against `w`/`h`/`text_w`. Supported controls: **position**
  (top/center/bottom), **font** (file + size), **outline** (`borderw`/
  `bordercolor`), **shadow** (`shadowx/y` + colour), **box** (colour + opacity),
  **color**, **alignment** (left/center/right), and **safe margins**.
- **`MockRenderer`** (hermetic, no FFmpeg) paints deterministic BGR caption
  *bands* placed by the same style rules — enough to assert *where*, *when*, and
  *what colour* a caption is, and to keep the hermetic test suite byte-for-byte
  reproducible.

Both backends are pure functions of the Timeline: same Timeline ⇒ same output.

## Styles

Seven reusable presets ship in `caption_engine/styles/presets.py`; each is pure
data and every field is overridable via config or per call:

| Preset | Character |
|---|---|
| `classic` | White text, black outline, bottom — safe default |
| `modern` | Lighter outline, soft shadow, roomy bottom margin |
| `bold` | Large uppercase, thick outline, high-impact |
| `minimal` | Small, no outline/shadow, understated |
| `youtube` | Semi-opaque box behind text, bottom |
| `instagram` | Centred, warm highlight, medium |
| `tiktok` | Large uppercase, centred, strong highlight (karaoke-friendly) |

Resolution order for a concrete style: **preset base → config `style` overrides
→ per-call overrides** (applied with `dataclasses.replace`).

## Subtitle export

`caption_engine.export.subtitles` provides pure, deterministic serializers over
a `CaptionTrack` (timestamps come straight from the segments, so exports are
always in sync with what the renderer draws):

| Format | Function | Notes |
|---|---|---|
| **SRT** | `to_srt` | One cue per segment; `word_level=True` for per-word cues |
| **WebVTT** | `to_webvtt` | `WEBVTT` header + numbered cues |
| **JSON** | `to_json` | Self-describing (segments + word timings + style name) |
| **Timeline captions** | `to_timeline_captions` | IR-native `CaptionTrack` JSON; round-trips via the Timeline serde |

`write_subtitles(track, out_dir)` writes `<stem>.srt/.vtt/.json/.captions.json`.

## Configuration

`caption_engine/config/defaults.yaml`, layered exactly like the other engines
(packaged defaults ← optional user file ← `AICP__captions__*` env ← explicit
overrides). Configuration, not code, selects:

```yaml
captions:
  kind: sentence          # sentence | word | karaoke | static
  preset: classic         # base style preset
  animation:
    kind: none            # none | fade | pop
    duration_s: 0.2       # lead-in/out length
  style:                  # overrides applied on top of the preset
    font_family: DejaVuSans
    font_size: 64
    primary_color: [255, 255, 255]
    highlight_color: [255, 215, 0]   # karaoke active-word colour
    outline_color: [0, 0, 0]
    outline_width: 4                  # stroke; 0 disables
    shadow: true
    shadow_offset: 2
    alignment: center
    position: bottom
    safe_margin_v: 0.12               # safe area (fraction of height)
    safe_margin_h: 0.06
    max_chars_per_line: 38
```

## Benchmark

`python -m caption_engine.scripts.run_benchmark` (hermetic mock by default,
`--renderer ffmpeg` for the real burn-in). Measures, per repetition:

- **caption generation** (`caption_gen_ms`),
- **render overhead** — render with vs without captions (`caption_render_overhead_ms`),
- **export time** (`export_ms`) and **subtitle export time** (`subtitle_export_ms`),
- **memory** (`rss_mb`) via the foundation resource monitor.

## Demo / validation

`python -m caption_engine.scripts.render_caption_demo` runs the full slice:

```
script → (speech WAV) → placeholder talking-head video → Timeline IR
       → Caption Track → Renderer → playable MP4  + SRT + WebVTT + JSON + Timeline captions
```

It validates the master is playable with the right shape/duration, exports are
readable, captions were burned in, timing fits the audio, `word`/`karaoke`
carry per-word timings, and every subtitle export parses (with the Timeline
captions round-tripping losslessly). Runs with `--renderer ffmpeg` (real MP4) or
`--renderer mock` (hermetic), across all four `--kind`s and seven `--preset`s.

## Limitations (v1)

Deliberately small and simple; later phases build on this foundation.

- **Animation is opacity-only.** `fade` ramps in/out; `pop` is a fast ramp-in
  that holds. No scale/slide/spring motion.
- **Karaoke layout uses estimated glyph metrics** (a per-character advance) to
  position words on one line, so highlighted words are placed approximately, not
  from true font kerning. Word wrapping is greedy by `max_chars_per_line`.
- **One timing provider** — the deterministic heuristic (length-proportional).
  Real ASR/forced-alignment is a drop-in behind the `TimingProvider` protocol
  but not implemented here.
- **Single active track** for the burned-in SRT sidecar / mock band painting;
  multiple simultaneous caption tracks render but the SRT sidecar uses the first.
- **No translation, styling per-word (beyond karaoke highlight), emoji, or RTL
  shaping.** Out of scope for C4.
- Explicitly **not** in this phase: B-roll, music, branding, templates, scene
  planner, script generator, AI editing, voice cloning (C5+).
```
