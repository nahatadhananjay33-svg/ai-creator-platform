# Visual Asset Engine — Timeline-Native B-roll (Phase C6)

The Visual Asset Engine makes **visual assets (B-roll) a first-class citizen of
the Timeline**. Assets are *data*, not a renderer special-case: the engine
resolves local files into a validated `AssetTrack`, and the renderer simply
**lowers** that track to overlays. No AI generation, no AI search, no downloads,
no stock providers, no scene planning — Phase C6 is *only* about Timeline-native
visual assets.

```
asset specs ──► provider (local file) ──► AssetTrack (native Timeline track) ──┐
 (paths/kinds)   layout + config defaults    clips: layout · placement · crop  │
                                             · animation · z-order             ▼
                                          Renderer ──► MP4 (assets composited)
```

It slots into the pipeline after branding:

```
Script ─► Voice ─► Avatar ─► Timeline ─► Caption Track ─► Branding Track
       ─► Visual Asset Track ─► Renderer ─► playable MP4
```

Compositing order (bottom → top): **base video → visual assets → captions →
branding**.

## Architecture

Reuses the platform foundation (config, logging, benchmarking) and the engine
module pattern. The **frozen asset IR types live in `reel_engine.interfaces`** —
the single Timeline contract — so the Visual Asset Engine depends on the Reels
Engine, never the reverse.

| Package | Responsibility |
|---|---|
| `asset_engine/providers/` | `LocalAssetProvider` (resolve local files, infer kind — no downloads/stock/AI) + deterministic placeholder generators |
| `asset_engine/layout/` | Authoring helpers for the 8 layouts (geometry resolves render-side) |
| `asset_engine/timeline/` | `build_asset_track` — specs + config → validated `AssetTrack` |
| `asset_engine/config/` | `defaults.yaml` bound to a frozen `AssetEngineConfig` |
| `asset_engine/benchmark/` | Deterministic loading/render/export benchmark (`BenchmarkCase`) |
| `asset_engine/scripts/` | `render_asset_demo`, `run_benchmark` CLIs |
| `asset_engine/engine.py` | `AssetEngine` facade: asset specs → `AssetTrack` |
| `reel_engine/render/assets.py` | **Renderer-side lowering**: layout→placement, animation state, z-order (shared by both backends) |

## Timeline integration

Phase C6 extends the Timeline IR **additively** (schema `v3 → v4`); v1..v3
projects load unchanged. All asset types are immutable `@dataclass(frozen=True)`,
timed in **absolute reel time**:

| Type | Meaning |
|---|---|
| `AssetCrop` | Source crop as fractions (`x,y,w,h`) |
| `AssetPlacement` | Destination rectangle (fractions) + fit (`contain`/`cover`/`stretch`) |
| `AssetLayout` | High-level layout (+ corner/side/scale/margin) that resolves to a placement |
| `AssetAnimation` | Simple enter/exit effect + duration |
| `AssetTransition` | Clip in-transition (`cut`/`cross_dissolve`) |
| `AssetClip` | One asset: kind, source, window, layout/placement, crop, animations, opacity, `z_index` |
| `AssetTrack` | An ordered set of clips (may overlap; layered by `z_index`) → `Timeline.asset_tracks` |

**Validation** (`reel_engine.timeline.validate`, explicit all-at-once errors):
valid kind/layout/fit/animation/transition, **source present (no missing
assets)**, windows inside the reel, opacity in range, and placement/crop
rectangles inside the frame.

## Supported asset types

`image`, `video`, `screenshot`, `chart`, `document`, `map`, `icon`,
`illustration`. Only `video` decodes as video; the rest are static images (the
label is a semantic hint, not a different render path). All are **local files** —
the kind is inferred from the extension unless given.

## Layouts

Eight layouts resolve to a destination rectangle (`reel_engine.render.assets.
resolve_layout`):

| Layout | Geometry |
|---|---|
| `full_screen` | Whole frame, cover |
| `background_replacement` | Whole frame, cover (behind higher-z assets) |
| `picture_in_picture` | `scale`×`scale` box in a `corner`, inset by `margin`, cover |
| `floating_card` | Like PIP but `contain` (whole asset shown) |
| `split_screen` | One half (`side`), cover |
| `side_by_side` | One half with inset margins, contain |
| `top_banner` / `bottom_banner` | Full-width band (25% height), cover |

An explicit `AssetPlacement` on a clip overrides its layout.

## Rendering

The renderer was **extended, not redesigned**. `reel_engine/render/assets.py`
resolves each clip's placement + a per-time animation state; both backends
consume it.

- **`FFmpegRenderer`** composites assets in **one `filter_complex` pass** before
  captions/branding (so exports inherit them): each asset is cropped
  (`crop`), scaled/fitted (`contain` letterbox / `cover` scale+crop / `stretch`),
  given opacity + fade, and overlaid at its rectangle in z-order. Images are
  looped to the reel length; videos are looped and PTS-shifted into reel time.
  Supported: **image & video overlays, scaling, letterboxing, cropping,
  opacity, layer ordering, safe margins, timing, and asset lifetime**.
- **`MockRenderer`** (hermetic, no FFmpeg) paints a deterministic solid box per
  clip (`asset_mock_color`) at the resolved geometry — enough to assert layout,
  layering, timing, and animation, and to keep the suite byte-for-byte
  reproducible.

## Animation

Simple, deterministic, opacity/offset/scale only (no keyframe editor):
`fade_in`, `fade_out`, `slide_left`, `slide_right`, `scale`, and `cross_dissolve`
(a fade against what's underneath). `asset_anim_state(clip, t)` returns
`(alpha, x_off, y_off, scale)` — the mock applies it exactly; FFmpeg maps fades
to the `fade` filter and slides to a time-dependent `overlay` x expression
(`scale` is approximated by a fade in the FFmpeg path).

## Configuration

`asset_engine/config/defaults.yaml`, layered like the other engines (packaged
defaults ← optional user file ← `AICP__assets__*` env ← explicit overrides):

```yaml
assets:
  default_layout: full_screen
  default_duration_s: 3.0
  overlay_opacity: 1.0
  safe_margin_v: 0.06
  safe_margin_h: 0.05
  picture_in_picture: {scale: 0.30, corner: bottom_right, margin: 0.05}
  animation: {kind_in: fade_in, kind_out: fade_out, duration_s: 0.4}
  transition: cut
```

## Benchmark

`python -m asset_engine.scripts.run_benchmark` (hermetic mock by default,
`--renderer ffmpeg` for the real composite). Measures, per repetition: **asset
loading** (`asset_load_ms`), **timeline generation** (`timeline_gen_ms`), **render
overhead** — render with vs without assets (`asset_render_overhead_ms`),
**export** (`export_ms`), **memory** (`rss_mb`), and **FPS** (`render_fps`).

## Demo / validation

`python -m asset_engine.scripts.render_asset_demo` runs the full slice:

```
script → (WAV) → talking-head video → Timeline → Caption Track → Branding Track
       → Visual Asset Track → Renderer → playable MP4 + exports
```

The B-roll plan is: image B-roll (full screen) → PIP (over it, layered) →
split-screen video → video B-roll (full screen). It validates the master/exports
are playable with correct aspect ratios, then runs a **backend-independent
hermetic mock pixel check** confirming: **asset timing**, **correct layering**,
**picture-in-picture position** (inset, no clipping), and **split-screen
position**. Runs with `--renderer ffmpeg` (real MP4) or `--renderer mock`
(hermetic).

## Limitations (v1)

Deliberately small; later phases build on this.

- **No AI**: no generation, no search, no auto scene planning — the caller
  supplies concrete local files and timing.
- **No downloads / no stock providers** — `LocalAssetProvider` only.
- **Animation is opacity/offset/scale**; `scale`/exit-slide are exact in the
  mock but approximated by fades in the FFmpeg path. No keyframe editor.
- **`background_replacement` renders as a full-frame cover** (no subject
  segmentation/matting).
- **Mock assets are solid boxes** (no image/font rasterisation) — for hermetic
  verification; the FFmpeg backend renders the real media.
- **No audio from video B-roll** — asset video contributes visuals only; the
  reel's audio is the scene/voice track.

## Future AI integration points

The architecture leaves clean seams for later phases (C7+), with no changes to
the IR or renderer required:

- **Asset search / stock providers** — implement the `AssetProvider` protocol
  (e.g. a stock-API or vector-search provider) behind `AssetEngine`; it still
  yields the same `AssetTrack`.
- **AI image/video generation** — a generative provider that writes a local file
  and returns an `AssetRef` plugs in exactly where `LocalAssetProvider` does.
- **Automatic scene planning** — a planner can emit `AssetSpec`s (which asset,
  which layout, when) from a script/transcript; the builder and renderer are
  unchanged.
- **Smart cropping / saliency** — populate `AssetCrop` from a saliency model; the
  renderer already honours it.
- **Learned layouts / transitions** — extend `ASSET_LAYOUTS` / `ASSET_ANIMATIONS`
  and their resolvers; existing timelines keep working (additive).
```
