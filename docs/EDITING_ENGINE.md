# Review & Editing Engine — Human-in-the-Loop (Phase C11)

The Editing Engine defines the **editable model** a future Creator Studio will
drive. It lets a user modify AI-generated content **without rebuilding the whole
reel**: edits are **immutable patch operations** over a `ReelProject`, each
patch validates before it applies, and a project is lowered to the **existing**
Timeline IR by reusing every downstream engine.

**There is no graphical UI here** (that is the next phase). And crucially:

- the **Timeline IR is unchanged**,
- the **renderer is unchanged**,
- editing is implemented as **immutable patch operations** — a patch never
  mutates its input; it returns a new project.

```
prompt ─► AI Storyboard ─► Review ─► Patch Set ─► Scene Engine ─► Timeline ─► Renderer ─► MP4
```

## Architecture

Reuses the platform foundation (logging, benchmarking) and the entire existing
pipeline. It depends on the AI/Scene/Caption/Branding/Music/Asset engines — never
the reverse.

| Package | Responsibility |
|---|---|
| `editing_engine/project.py` | `ReelProject` — the immutable editable document (AI storyboard + presentation settings) |
| `editing_engine/patches/` | The immutable `Patch` base + the 10 edit operations |
| `editing_engine/validation/` | `apply_patch` (validate → apply → validate result) + `PatchError` |
| `editing_engine/history/` | `EditHistory` — append-only patches, undo/redo, deterministic replay |
| `editing_engine/review/` | `review_project` — the deterministic review step (findings + suggestions) |
| `editing_engine/incremental.py` | `plan_incremental` — scene-diff via the existing Timeline hashes |
| `editing_engine/engine.py` | `EditingEngine` facade (new project, apply, review, build, incremental) |
| `editing_engine/benchmark/` | Deterministic patch/regeneration/validation benchmark |

## The editable model

A `ReelProject` is an immutable snapshot of an editable reel:

- **content** — an `AIStoryboard` (from C10): the scenes and their narration,
- **presentation** — a branding `theme`, a music `soundtrack`, a caption `kind`
  + `preset`, and the frame `width`/`height`/`fps`,
- **revision** — bumped by every applied patch, so two projects are always
  distinguishable.

Every mutation (`with_scenes`, `with_settings`) returns a **new** project; the
input is never touched.

## Patch architecture

Every edit is an immutable `@dataclass(frozen=True)` `Patch`. A patch is a pure
value that:

1. **validates** itself against a project — `patch.validate(project)` returns a
   problem list (empty == applicable); the valid value sets (themes, soundtracks,
   caption kinds/styles, asset kinds/layouts, scene types) are pulled from the
   engines that own them, so a patch can never set a value a downstream engine
   would reject;
2. **applies** — `patch.apply(project)` returns a **new** project.

`apply_patch(patch, project)` is the single safe entry point: validate the patch,
apply it, then re-validate the resulting project's content (raising `PatchError`
on any problem).

| Patch | Operation |
|---|---|
| `InsertScenePatch` | insert a scene at an index |
| `DeleteScenePatch` | delete a scene (a reel keeps ≥ 1 scene) |
| `MoveScenePatch` | reorder — move a scene to a new index |
| `ReplaceNarrationPatch` | replace a scene's narration |
| `ReplaceAssetPatch` | change a scene's suggested asset kind / layout |
| `DurationPatch` | adjust a scene's estimated duration |
| `ThemePatch` | change the branding theme |
| `MusicPatch` | change the music track |
| `CaptionPatch` | change the caption kind / style |
| `RegenerateScenePatch` | regenerate one scene's narration **through the existing AI Storyboard provider interface** (deterministic with the mock provider) |

## Review workflow

`review_project(project)` is the deterministic human-in-the-loop inspection step
(`AI Storyboard → Review → Patch Set`). It surfaces findings — a missing hook or
call-to-action, over-long or too-thin scenes, and any structural problems from
the shared validator — each with an optional concrete suggested patch. No AI, no
I/O: the same project always yields the same review. The typical loop is
**review → choose patches → apply → re-review**.

## History

Because patches are immutable and each application yields a new project, an edit
history is just an ordered list of `(patch, resulting snapshot)`. `EditHistory`:

- `apply(patch)` — validate + apply, record it (clears the redo stack),
- `undo()` / `redo()` — linear undo/redo,
- `replay()` — re-apply every recorded patch from the base; for deterministic
  patches (all of them with the mock provider) this reproduces the current state
  exactly — the reproducible audit trail a Creator Studio needs,
- `log()` — a human-readable one-line summary per patch.

## Incremental rendering

After an edit, most scenes are usually unchanged, so re-rendering the whole reel
is wasteful. `plan_incremental(old_timeline, new_timeline)` computes, from two
timelines, **which scenes actually changed** — by reusing the existing Timeline
**per-scene content hashes** (`reel_engine.timeline.hashing.scene_content_hash`):

| Field | Meaning |
|---|---|
| `changed` | new-scene indices that differ from the same-position old scene (must re-render) |
| `reused` | new-scene indices byte-identical at the same position (skip) |
| `cacheable` | new-scene indices whose hash exists **anywhere** in the old timeline (a moved scene's render can be reused) |
| `overlays_changed` | a caption/branding/music/asset change requiring re-compositing even when no scene changed |
| `reuse_fraction` | fraction of new scenes whose render can be reused |

It **does not modify the renderer or the Timeline IR** — it produces a plan a
future renderer (or Creator Studio) can consume to re-render only the changed
scenes. Note the deterministic Scene Engine re-classifies scenes by content +
position, so an edit that moves narration around genuinely changes the scene
plan — the plan reports the **honest** diff, not a naive positional shuffle.

## Configuration & usage

```python
from editing_engine import EditingEngine, ReplaceNarrationPatch, ThemePatch

engine = EditingEngine()
project = engine.new_project("Why investing in real estate early is beneficial",
                             template="real_estate")

# review, then edit with an undoable history
history = engine.history(project)
history.apply(ReplaceNarrationPatch(1, "A punchier second scene."))
history.apply(ThemePatch("finance"))
edited = history.current            # or history.undo() / history.redo()

# lower the edited project to the existing Timeline IR (reusing every engine)
scene_sb, timeline = engine.build_timeline(edited)

# what changed? (only-render-diffs)
_, base_tl = engine.build_timeline(project)
plan = engine.incremental_plan(base_tl, timeline)   # changed / reused / cacheable
```

## Demo & validation

```
python -m editing_engine.scripts.render_edit_demo                  # ffmpeg MP4
python -m editing_engine.scripts.render_edit_demo --renderer mock  # hermetic proxy
```

The demo generates a reel, reviews it, applies a representative patch set
(content + structural + presentation + AI-regeneration edits) **validating the
Timeline after every patch**, computes the incremental plan, and renders an
**updated** playable MP4 + `reel_9x16`/`square_1x1` exports. It verifies: the
timeline validates after every patch, the edit history replays byte-identically
(deterministic), the incremental plan reports real scene reuse, and the base +
updated masters and exports are playable.

## Benchmark

```
python -m editing_engine.scripts.run_benchmark
```

Measures patch application, incremental regeneration (project → Timeline),
timeline validation, the incremental-plan diff, and memory over a fixed patch set.
Hermetic (MockProvider) — no AI, GPU, ffmpeg, or network.

## Regression tests

`editing_engine/tests/` — fully hermetic and deterministic (MockProvider only).
Cover all 10 patch types (immutability, revision bump, base untouched),
patch/project validation, the edit history (undo/redo/replay determinism), the
review step, the incremental plan, and the facade — including that the Timeline
**validates after every patch**.

## Limitations (Phase C11 scope)

- **Model, not UI** — this phase defines the editable model + patch semantics; the
  graphical Creator Studio is the next phase.
- **Timeline IR & renderer untouched** — the incremental plan tells a renderer
  what it *could* skip; wiring per-scene render caching into the renderer is a
  later, separate change.
- **Real-provider regeneration isn't replay-stable** — `RegenerateScenePatch` is
  deterministic with the mock provider (replayable history); a live LLM
  re-generates on apply.
- **Presentation edits are overlay-level** — a theme/music/caption change is
  flagged `overlays_changed` (re-composite) but changes no scene hash.

## Future Creator Studio integration

The editable model was built so a UI can drop on top without new engine work:

- **Direct manipulation → patches** — every UI gesture (drag to reorder, edit a
  caption, pick a theme) maps to exactly one patch; the Studio never mutates
  state directly, it emits patches.
- **Undo/redo & autosave** — `EditHistory` already provides linear undo/redo and
  a replayable log; persisting the base project + patch list is a complete,
  reproducible save format.
- **Live preview** — `incremental_plan` tells the Studio which scenes to re-render
  for a preview, so edits feel instant.
- **Review panel** — `review_project` findings + suggested patches drive a
  "suggestions" panel with one-click fixes.
- **Collaboration** — because patches are immutable values, they can be
  serialized, transmitted, and re-ordered/merged for multi-user editing later.

None of these change the Timeline IR or the renderer.
