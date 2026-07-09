# Creator Studio — Deterministic Visual Editor (Phase C12)

The Creator Studio is the first graphical editor for the AI Creator Platform. It
is an **interface layer only**, built on top of the Editing Engine (Phase C11).
It contains **no business logic** that already lives in the engine — every user
gesture becomes an immutable `Patch` routed through `EditingEngine.apply_patch`,
and the project is lowered to the **existing** Timeline IR and rendered by the
**existing** renderer.

```
open ─► storyboard / timeline ─► edit (immutable patches) ─► incremental plan ─► preview ─► export
```

## Architectural rules (enforced)

- **The Editing Engine is the single source of truth.** The Studio never
  reimplements an edit — it constructs a `Patch` and asks the engine to apply it.
- **The UI never mutates a `ReelProject`.** Projects are frozen; every edit
  returns a NEW project via the engine, so the Studio only swaps the reference it
  holds. (`test_session_never_mutates_the_project_object`.)
- **The Timeline IR is unchanged.** The Studio lowers projects with
  `EditingEngine.build_timeline` and reads the resulting IR; it adds no fields.
- **The renderer is unchanged.** Preview/export call the existing `mock` / `ffmpeg`
  backends verbatim.
- **Every edit is a `Patch`.** Each edit command returns a `CommandResult` naming
  the patch it applied; validation failures are surfaced, not swallowed.
- **Fully deterministic.** The same command sequence yields the same views and the
  same rendered bytes (`test_full_view_is_deterministic`).

## Architecture

Depends on the Editing Engine and, through it, the whole existing pipeline — never
the reverse.

| Module | Responsibility |
|---|---|
| `creator_studio/session.py` | `StudioSession` — the UI controller: state (selection, playhead, caption toggle, last preview) + commands for every user action |
| `creator_studio/viewmodels.py` | Frozen, presentation-only view models — one per panel + `StudioView` (whole screen) |
| `creator_studio/panels.py` | Pure builders that project engine state into view models (no mutation, no I/O) |
| `creator_studio/project_io.py` | Project Manager persistence — save/open a `ReelProject` (revision preserved) |
| `creator_studio/export.py` | Thin adapter over the existing renderer (`mock`/`ffmpeg`) |
| `creator_studio/scripts/` | The end-to-end validation demo |

The controller holds an `EditHistory` (from the engine) as its edit model, a
selected scene index, a playhead, a caption-visibility flag, and a cached last
render. `session.view()` returns a `StudioView` — a deterministic snapshot of the
entire screen a front-end renders.

## The panels (required components)

**1. Project Manager** — `StudioSession.new(prompt, …)`, `.open(path)`, `.save(path)`.
`ProjectInfo` carries the title, the **current revision** indicator, the baseline
revision, dimensions, and a dirty flag. Persistence (`project_io.py`) serializes
the editable model (AI storyboard + presentation settings + revision) with stable
field order; open restores it exactly.

**2. Storyboard Panel** — `StoryboardPanel` is the scene list with selection.
Commands: `insert_scene`, `delete_scene`, `move_scene` (drag-and-drop reorder),
`select_scene`. Each maps to exactly one patch (`InsertScenePatch`,
`DeleteScenePatch`, `MoveScenePatch`).

**3. Timeline View** — `TimelinePanel` renders visual scene bars with absolute
start/end/duration, a playhead, and per-bar incremental status (reused vs
regenerated). Navigation: `seek`, `seek_scene`, `next_scene`, `prev_scene`.

**4. Inspector Panel** — `InspectorPanel` exposes the selected scene's narration /
duration / asset and the reel-wide theme / music / caption style, plus the exact
valid option lists (pulled from the owning engines). Commands: `set_narration`,
`set_duration`, `replace_asset`, `set_theme`, `set_music`, `set_caption`,
`toggle_captions`, `regenerate_scene`.

**5. Preview Player** — `session.preview()` renders the current project with the
session renderer and caches it; `PreviewPanel` carries the media path, per-scene
seek offsets, and pure playback state (`play`/`pause`/`seek`). An edit invalidates
a stale preview (`ready` flips false).

**6. Patch Integration** — every edit command builds the corresponding immutable
patch and routes it through `EditHistory.apply` → `EditingEngine.apply_patch`. A
`PatchError` is caught and returned as `CommandResult(ok=False, problems=…)` with
the session state **left untouched**.

**7. Incremental Regeneration** — `IncrementalPanel` shows the plan from the
Editing Engine's `incremental_plan`: which scenes are **reused** vs **regenerated**,
the reuse fraction, `overlays_changed`, and **cache statistics** (hits / misses /
cacheable). The timeline bars are highlighted to match
(`test_incremental_scene_status_aligns_with_timeline_bars`).

**8. History** — `HistoryPanel` is the patch timeline; `undo`/`redo` delegate to
`EditHistory`; `replay()` deterministically re-applies every patch from the base.

**9. Export** — `session.export(path, renderer, export_profiles)` lowers the
latest revision and renders it through the **existing** renderer (no modification),
emitting a master + platform exports. A bare stem gets the backend's container
suffix (`.mp4` for ffmpeg, `.avi` for the mock proxy).

## Caption visibility vs caption style

The caption **style** (kind + preset) is a real project edit — a `CaptionPatch`
(`set_caption`). Caption **visibility** (`toggle_captions`) is *not* a project
edit: the editable model always carries a caption `kind` (there is no
"captions off" value in the source-of-truth model), so the toggle simply omits the
native caption track when the Studio hands the Timeline to the renderer. It changes
the rendered output but never the `ReelProject` — no patch, no revision bump
(`test_caption_visibility_toggle_is_not_a_project_edit`). This is a legitimate
compositing choice at the point the Timeline meets the renderer; the Timeline IR
and renderer are unchanged.

## Demo

```
python -m creator_studio.scripts.render_studio_demo                  # real MP4 (ffmpeg)
python -m creator_studio.scripts.render_studio_demo --renderer mock  # hermetic proxy
```

Opens a project, prints the storyboard + timeline, reviews, applies a
representative patch set (validating the Timeline after each), prints the
incremental plan + cache stats, saves/opens a round-trip, then previews and
**exports an updated reel** through the existing renderer. Exit `0` on success.

## Regression tests

`creator_studio/tests/` — fully hermetic and deterministic (MockProvider + the
mock renderer; no ffmpeg/network/GPU). Cover: project open/save round-trips, all
six panels, patch generation + validation surfacing, undo/redo, the incremental
plan visualization (bars aligned to the plan), preview invalidation, export
through the existing renderer, whole-`view()` determinism, the invariant that the
Studio never mutates a project, and the `prompt → review → edit → preview → export`
loop with the Timeline validated after every command.

## Limitations (Phase C12 scope)

- **Prototype interface layer** — view models, not pixels. It produces the exact,
  deterministic panel state a web/desktop front-end renders; wiring those to a
  specific GUI toolkit is downstream.
- **Incremental plan is advisory** — it reports what a renderer *could* reuse; the
  renderer still re-renders the whole reel (per-scene render caching in the
  renderer is a separate, later change, exactly as in C11).
- **Real-provider regeneration isn't replay-stable** — `regenerate_scene` is
  deterministic with the mock provider (replayable history); a live LLM
  re-generates on apply.
- **Out of scope by design** — no collaboration, cloud sync, AI co-editing,
  plugins, or asset marketplaces in this phase.
