# Branding & Theme Engine — Timeline-Native Branding (Phase C5)

The Branding Engine turns a **theme + brand facts** (creator, channel, website,
handles, logo) into **branding that lives natively in the Timeline IR**.
Branding is *data*, not a renderer special-case: the engine produces a validated
`BrandingTrack`, and the renderer simply **lowers** that track to overlays.
Logos, cards, lower thirds and watermarks are never hardcoded in the renderer.

```
theme + brand facts ──► BrandingTrack (native Timeline track) ──┐
 (themes/ + builder)      logo · watermark · intro · outro · LT  │
                                                                 ▼
                                     Renderer ──► MP4 (branding composited)
```

It slots into the end-to-end pipeline after captions:

```
Script ─► Voice ─► Avatar ─► Timeline IR ─► Caption Track ─► Branding Track ─► Renderer ─► playable MP4
```

## Architecture

Reuses the platform foundation (config, logging, benchmarking) and the engine
module pattern. The **frozen branding IR types live in
`reel_engine.interfaces`** — the single Timeline contract — so the Branding
Engine depends on the Reels Engine, never the reverse.

| Package | Responsibility |
|---|---|
| `branding_engine/themes/` | 10 reusable `Theme` presets (classic/minimal/corporate/modern/real_estate/finance/education/medical/dark/light) |
| `branding_engine/timeline/` | `build_branding_track` — composes a theme + brand facts + component toggles into a `BrandingTrack` |
| `branding_engine/assets/` | Packaged placeholder logo (`default_logo.png`, Pillow-generated RGBA) + a generator |
| `branding_engine/config/` | `defaults.yaml` bound to a frozen `BrandingEngineConfig` |
| `branding_engine/benchmark/` | Deterministic generation/render/export benchmark (`BenchmarkCase`) |
| `branding_engine/scripts/` | `render_branding_demo`, `run_benchmark` CLIs |
| `branding_engine/engine.py` | `BrandingEngine` facade: theme + brand facts -> `BrandingTrack` |
| `reel_engine/render/branding.py` | **Renderer-side lowering**: `BrandingTrack → BrandingElement` ops (shared by both backends) |

The facade wires two pieces and nothing else: `theme resolution → builder`. It
generates *data* (a branding track); rendering is a separate concern. No models,
no ASR, no I/O beyond resolving the logo path, so `generate(...)` is
reproducible and hermetic.

## Theme system

A `Theme` is a reusable visual identity — pure data the engine/renderer consume.
Every theme defines a **font**, **primary/secondary/text/background colours**, a
**logo placement + scale**, **safe margins**, a **lower-third look**, and
**intro/outro lengths**:

| Theme | Character |
|---|---|
| `classic` | Brand-blue accents, white text, standard safe area |
| `minimal` | Light, understated, tight margins, top-left logo |
| `corporate` | Navy + cyan, generous margins, longer outro |
| `modern` | Magenta + cyan, bold, punchy |
| `real_estate` | Warm gold on charcoal |
| `finance` | Green + gold, conservative |
| `education` | Orange + blue, friendly |
| `medical` | Teal on light, clean/clinical |
| `dark` | High-contrast on black |
| `light` | High-contrast on white |

Resolution order for a concrete theme: **preset base → config overrides →
per-call overrides** (applied with `dataclasses.replace`).

## Timeline integration

Phase C5 extends the Timeline IR **additively** (schema `v2 → v3`); v1/v2
projects (no branding) load unchanged. All branding types are immutable
`@dataclass(frozen=True)`:

| Type | Meaning |
|---|---|
| `Theme` | The reusable visual identity + component defaults |
| `Logo` | An image (or text-badge fallback) at a position/scale/opacity/window |
| `Watermark` | A persistent low-opacity text/image mark |
| `LowerThird` | A titled banner (name + role/handle) over a time window |
| `Intro` / `Outro` | Full-frame opening/closing cards |
| `BrandingElement` | A **resolved, absolutely-timed** overlay op — the generic thing the renderer consumes |
| `BrandingTrack` | A theme + its typed components — the native track (`Timeline.branding`) |

**Timing is resolved at lowering time** (`reel_engine.render.branding.resolve_branding`):
logo/watermark span the reel (unless bounded), lower thirds use their windows,
the intro card covers `[0, intro.duration_s]`, and the outro card covers
`[reel − outro.duration_s, reel]`. Elements are ordered bottom-to-top so the
cards cleanly cover everything during their windows.

**Validation** (`reel_engine.timeline.validate`, explicit all-at-once errors):
valid positions (9-grid + `bottom` band), opacity/scale in range, safe margins
in `[0, 0.5)`, valid RGB, non-empty titles, component windows inside the reel,
and **intro + outro fit within the reel duration**. The track serializes
losslessly through the Timeline JSON serde and is covered by the content hash.

## Renderer

The renderer was **extended, not redesigned**. `resolve_branding` produces the
`BrandingElement` list; both backends consume it.

- **`FFmpegRenderer`** composites branding in **one `filter_complex` pass** after
  captions and *before* export (so every profile inherits it): image logos/
  watermarks are `overlay`-ed (scaled to a width fraction, alpha applied via
  `colorchannelmixer`); intro/outro cards are full-frame `drawbox` fills; lower
  thirds are a `drawbox` band + `drawtext`; text badges/watermarks are
  `drawtext`. Position expressions use `W`/`H`/overlay dims, so they are correct
  at any resolution. Supported: **logo, intro, outro, watermark, lower thirds,
  safe margins, opacity, position, scale, timing**.
- **`MockRenderer`** (hermetic, no FFmpeg) paints deterministic boxes placed by
  the same position + safe-margin rules — enough to assert *where*, *when*, and
  *what colour* branding is, and to keep the hermetic suite byte-for-byte
  reproducible.

Both backends are pure functions of the Timeline: same Timeline ⇒ same output.
Compositing order is **base video → captions → branding** (branding on top;
cards cover captions during their windows).

## Configuration

`branding_engine/config/defaults.yaml`, layered like the other engines (packaged
defaults ← optional user file ← `AICP__branding__*` env ← explicit overrides):

```yaml
branding:
  theme: classic
  creator: "Creator Name"
  channel: "My Channel"
  website: "example.com"
  social: ["@mychannel"]
  logo: null                    # path to a logo PNG; null -> text badge
  primary_color: null           # theme overrides (any subset)
  watermark_opacity: null
  safe_margin_v: null
  components:                    # which components appear
    intro: true
    outro: true
    logo: true
    watermark: true
    lower_third: true
  intro: {title: null, subtitle: null, duration_s: null}
  outro: {title: null, subtitle: null, duration_s: null}
  lower_third: {title: null, subtitle: null, start_s: 1.0, duration_s: 3.0}
```

## Benchmark

`python -m branding_engine.scripts.run_benchmark` (hermetic mock by default,
`--renderer ffmpeg` for the real composite). Measures, per repetition:
**startup**, **branding generation** (`branding_gen_ms`), **render overhead** —
render with vs without branding (`branding_render_overhead_ms`), **export**
(`export_ms`), and **memory** (`rss_mb`).

## Demo / validation

`python -m branding_engine.scripts.render_branding_demo` runs the full slice:

```
script → (speech WAV) → talking-head video → Timeline IR
       → Caption Track → Branding Track → Renderer → playable MP4 + exports
```

It validates the master/exports are playable and branding was composited, then
runs a **backend-independent hermetic mock pixel check** confirming: **logo
visible**, **intro shown**, **outro shown**, **lower thirds correct**,
**watermark correct**, and **safe margins respected**. Runs with `--renderer
ffmpeg` (real MP4) or `--renderer mock` (hermetic), across all 10 `--theme`s.

## Limitations (v1)

Deliberately small and simple; later phases build on this foundation.

- **No animation** on branding elements — cards/lower-thirds/logos appear and
  disappear as hard cuts (captions carry the fade/pop animation in C4).
- **Text layout is single-line** (drawtext); long titles are not wrapped, and
  text badges use font-independent glyphs — approximate, not kerned.
- **Logo/watermark are image overlays or solid placeholders** — the mock backend
  cannot rasterise the image or fonts, so it paints solid boxes (deterministic,
  for verification); the FFmpeg backend renders the real image + text.
- **One branding track per timeline**, one lower third from the builder (the IR
  supports several `lower_thirds`, but the facade emits one).
- **No transitions between the intro/outro card and the body** (hard cut).
- Explicitly **not** in this phase: background music, B-roll, scene planner,
  script generation, a templates marketplace, AI branding, or an editing UI
  (C6+).
```
