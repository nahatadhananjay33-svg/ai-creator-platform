# Scene & Storyboard Planning Engine — Deterministic (Phase C7)

The Scene Engine is the new **front of the pipeline**. It turns a finished
**script** into a **Storyboard** — an ordered plan of typed, timed scenes, each
carrying what to say (narration), when (timing), and how it should look (avatar /
asset / caption / branding slots) — and lowers that storyboard into the existing
Timeline IR that every downstream engine already produces and the renderer
already consumes.

It is **100% deterministic and rule-based**. There is **no GPT / Gemini / Claude,
no script generation, no AI scene planning, no asset retrieval, no music, no
scheduling, no editing** — those belong to later phases. The same `(script,
config)` always yields the same storyboard, byte for byte. Because the Storyboard
shape is frozen, a future **AI Script Engine** can emit the *same* format and
reuse the entire lowering + render path unchanged.

```
script.txt ──► segment ──► classify ──► time ──► plan visuals ──► Storyboard ──┐
 (sentences)   (rules)     (rules)      (est.)   (slots only)                   │
                                                                                ▼
                                     Storyboard ──► Timeline IR (scenes+captions)
                                                 ──► existing pipeline ──► MP4
```

It slots in **before** everything else, then reuses the rest of the platform:

```
Script ─► Storyboard ─► Scene Plan ─► Voice ─► Avatar ─► Timeline
       ─► Caption ─► Branding ─► Visual Assets ─► Renderer ─► playable MP4
```

The planner only **requests** visual assets (`AssetSlot`); it never touches the
filesystem or a network. The Visual Asset Engine satisfies those requests later
(the demo makes that hand-off concrete with local placeholders).

## Architecture

Reuses the platform foundation (config, logging, benchmarking, text utilities)
and the engine-module pattern. It depends on `reel_engine` (the Timeline IR) and
optionally the Asset/Branding engines for the demo — never the reverse.

| Package | Responsibility |
|---|---|
| `scene_engine/storyboard/` | The **frozen Storyboard IR** (`types.py`) + deterministic `serde` |
| `scene_engine/rules/` | `segmentation` (split), `classification` + `keywords` (scene type), `profiles` (per-type visual defaults) |
| `scene_engine/timing/` | `estimator` — word-count → speech estimate → contiguous absolute windows |
| `scene_engine/planner/` | `plan_storyboard` — composes the rules into a `Storyboard` |
| `scene_engine/timeline/` | `build_timeline` — lower a `Storyboard` to the Timeline IR (+ captions) |
| `scene_engine/config/` | `defaults.yaml` bound to a frozen `SceneEngineConfig` |
| `scene_engine/benchmark/` | Deterministic planning/timeline/throughput benchmark (`BenchmarkCase`) |
| `scene_engine/scripts/` | `render_scene_demo`, `run_benchmark` CLIs |
| `scene_engine/engine.py` | `SceneEngine` facade: script → Storyboard → Timeline |

## The Storyboard IR

Everything is an immutable `@dataclass(frozen=True)` with tuple collections,
exactly like the Timeline IR — *plan data*, not rendered pixels and not retrieved
assets. A `schema_version` travels with each storyboard so a persisted plan can
be validated/migrated later.

| Type | Meaning |
|---|---|
| `Storyboard` | Ordered `scenes` + title + pace; duration/word-count/type-mix are **derived** (never stored, can't drift) |
| `ScenePlan` | One beat: `scene_type` + `narration` + `timing` + `visual` |
| `SceneType` | Closed enum of the 11 deterministic classes (below) |
| `NarrationPlan` | Spoken `text`, `word_count`, segmented `sentences` |
| `TimingPlan` | Absolute `start_s`/`end_s`, `speech_duration_s`, transitions |
| `VisualPlan` | `background` hint + the four slots below |
| `AvatarSlot` | Whether/how the talking head appears (`full_screen` / `picture_in_picture`) |
| `AssetSlot` | A **request** for one visual asset (kind, hint, layout, window) — never a file |
| `CaptionSlot` | Caption intent (kind + style preset + window) |
| `BrandingSlot` | Branding intent (logo, intro/outro, lower-third) |

## Scene classification (deterministic, rules only)

Each scene is assigned one `SceneType` from its narration text and position, by
ordered keyword/pattern lookups in `rules/keywords.py` — no model, no randomness.
The 11 types: **Hook, Talking Head, Explanation, Image Insert, Video Insert,
Comparison, Bullet List, Chart, Quote, Call To Action, Outro**.

Precedence (first match wins):

1. **Call To Action** (strongest explicit intent — "subscribe", "link in bio")
2. **Hook** (the first scene, unless it was a pure CTA)
3. **Quote** (a quoted span of 3+ words, or "as the saying goes")
4. **Comparison** ("versus", "compared to", "whereas")
5. **Chart** (chart/data keywords, or a numeric statistic like `65%`, `3 million`)
6. **Bullet List** (bullet markers, or "first / second / three ways")
7. **Video Insert** ("watch this clip", "here is some footage")
8. **Image Insert** (image / map / screenshot / document keywords)
9. **Outro** (the last scene, when nothing stronger fired)
10. **Explanation / Talking Head** (default — by length, `explanation_min_words`)

Image inserts are further **refined** to `map` / `screenshot` / `document` by
keyword to give the Asset Engine a better later hint.

## Scene splitting (deterministic, no language model)

`rules/segmentation.py` groups whole sentences into scenes, in order:

1. **Manual markers** — a line that is only `---` / `===` / `[scene]` / `# scene`
   forces a hard break (author override).
2. **Paragraph boundaries** — a blank line separates paragraphs; a scene never
   spans one.
3. **Sentence boundaries** — sentences (shared splitter) are atomic; a scene is
   always a whole number of sentences (never split mid-sentence).
4. **Max words / max duration** — sentences accumulate until adding the next would
   exceed `max_words_per_scene` **or** estimated speech would exceed
   `max_scene_duration_s`; then a new scene starts. A single oversize sentence
   becomes its own scene (rule 3 beats rule 4).
5. **Min-words merge** — a fragment below `min_words_per_scene` folds into its
   neighbour so no scene is a stray word or two.

## Timing

At planning time the audio does not exist yet, so durations are **estimated** from
word count at a configured pace:

```
speech_s = clamp(word_count / wpm * 60, speech_min_s, speech_max_s)
scene_s  = max(speech_s, min_scene_duration_s, preferred floor for CTA/outro)
```

Scenes are then laid **end-to-end in absolute reel time** with a configurable
transition gap (default `0.0` = hard cut), which guarantees **no overlaps and no
gaps** by construction (`start_s[i] == end_s[i-1] + transition_s`).

**Reusing real timing:** `plan_timings(..., known_durations=...)` accepts a map of
`scene index → measured seconds` (e.g. from the Voice Engine once audio exists),
overriding the estimate for those scenes while everything else stays estimated —
how the planner "reuses existing timing data whenever possible".

## Visual planning

Per-scene-type **profiles** (`rules/profiles.py`) decide the default look: is the
avatar on screen and how, which asset kinds the scene requests, their layout, and
a solid background hint (a deterministic stand-in until real footage lands). The
planner reads the profile, refines asset kinds by keyword, and emits
`AssetSlot`s — **requests only**. Comparison scenes get two side-by-side halves.
No files are touched.

## Timeline integration

`timeline/build_timeline` lowers a `Storyboard` into the **existing, frozen**
`reel_engine` Timeline IR — the renderer is **not modified**:

- one solid-card `Scene` per scene plan (scene-type background + label), a fully
  renderable stand-in for avatar/B-roll footage;
- a native `CaptionTrack` built straight from the plan — one segment per narrated
  scene, spanning that scene's exact `[start_s, end_s]`. Because the windows come
  from the same `TimingPlan`, captions are guaranteed aligned, monotonic,
  non-overlapping, and inside the reel.

Asset slots are intentionally **not** lowered here (that would be retrieval);
`asset_slot_windows(storyboard)` exposes them for a downstream Asset Engine (or
the demo) to satisfy. The lowered timeline passes the shared Timeline validator.

## Configuration

`scene_engine/config/defaults.yaml`, layered like every engine (packaged defaults
← user file ← `AICP__scene__*` env ← explicit overrides). Nothing here can turn
planning non-deterministic.

| Key | Default | Meaning |
|---|---|---|
| `words_per_minute` | `150.0` | narration pace for the speech estimate |
| `speech_min_s` / `speech_max_s` | `0.8` / `30.0` | clamp on estimated speech |
| `transition_s` | `0.0` | gap between scenes (`0.0` = hard cut, no overlap) |
| `max_scene_duration_s` | `8.0` | split once estimated speech exceeds this |
| `min_scene_duration_s` | `1.5` | pad a scene window up to this floor |
| `max_words_per_scene` | `30` | split once a scene reaches this many words |
| `min_words_per_scene` | `3` | merge a shorter trailing fragment back |
| `explanation_min_words` | `24` | at/above → `EXPLANATION`, else `TALKING_HEAD` |
| `preferred_cta_duration_s` | `3.0` | pad a call-to-action scene to at least this |
| `preferred_outro_duration_s` | `3.0` | pad an outro scene to at least this |
| `preferred_avatar_pct` | `0.6` | soft target: avatar-on-screen fraction (reporting) |
| `preferred_talking_head_pct` | `0.5` | soft target: talking-head/explanation fraction |
| `preferred_broll_pct` | `0.35` | soft target: B-roll fraction |
| `default_asset_layout` / `pip_layout` / `comparison_layout` | `full_screen` / `picture_in_picture` / `side_by_side` | preferred layouts |
| `caption_kind` / `caption_preset` | `sentence` / `clean` | caption defaults |

## Usage

```python
from scene_engine import SceneEngine

engine = SceneEngine()
storyboard = engine.plan(script, title="My reel", creator="Alex", channel="Daily")
timeline   = engine.build_timeline(storyboard)      # validated Timeline IR
# or in one call:
storyboard, timeline = engine.plan_timeline(script, title="My reel")
```

## Demo & validation

```
python -m scene_engine.scripts.render_scene_demo                  # ffmpeg MP4
python -m scene_engine.scripts.render_scene_demo --renderer mock  # hermetic proxy
python -m scene_engine.scripts.render_scene_demo --no-assets      # captions only
```

From a ~40-second script the demo plans a storyboard, lowers it, satisfies the
planned asset slots with local placeholders (the Asset Engine hand-off), stacks a
branding track, and renders a playable MP4 + `reel_9x16` / `square_1x1` exports.
Before any render, it asserts the **backend-independent** plan invariants:
correct scene count, sequential ordering, per-scene timing (floors honoured),
**no gaps / no overlaps**, aligned captions, the planned asset-slot count, a clean
Timeline-validator pass, and that replanning the same script is **byte-identical**.

## Benchmark

```
python -m scene_engine.scripts.run_benchmark
```

Measures planning time, scene-generation time, timeline-generation time,
throughput (scenes/sec, words/sec), and peak memory over a fixed, repeated
script. Pure CPU and fully hermetic — no renderer, FFmpeg, GPU, or model.

## Regression tests

`scene_engine/tests/` — fully hermetic and deterministic (no renderer, ffmpeg,
GPU, model, network). Covers segmentation, classification, timing, the storyboard
IR + serde, timeline generation, configuration, validation, the facade, and the
benchmark smoke path. Every built timeline is run through the shared Timeline
validator, so the engine can never emit an unrenderable plan.

```
python -m pytest scene_engine/tests/ -q
```

## Limitations (Phase C7 scope)

- **Deterministic only** — classification is ordered keyword rules, not semantics;
  an unusual phrasing may fall to the length-based default. This is by design.
- **Estimated timing** — durations come from word count until real audio exists;
  feed `known_durations` to replace the estimate per scene.
- **Slots, not assets** — the planner *requests* visuals; it never retrieves,
  generates, or edits them. No music, no scheduling, no editing UI.
- **Solid-card stand-ins** — lowering emits labelled colour cards for scenes (like
  the C5/C6 demos); real avatar/B-roll footage is layered by later engines.

## Future AI integration points

The Storyboard shape is frozen precisely so AI can slot in **without touching the
lowering or render path**:

- **AI Script Engine** — generates the script *and/or* emits a `Storyboard`
  directly (same dataclasses), replacing only the rule-based planner.
- **AI scene planning** — a model could propose `SceneType`s / splits; it would
  still produce the same `ScenePlan` objects, validated the same way.
- **Asset Engine (AI search/generation)** — satisfies the planner's `AssetSlot`
  requests with retrieved or generated media (kind, hint, layout, window are the
  contract already emitted here).
- **Music / scheduling / editing** — consume the finished Storyboard + Timeline;
  none of them change the planner.
