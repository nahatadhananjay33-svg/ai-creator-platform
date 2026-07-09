# Intelligent Asset Retrieval — Provider-Based Resolution (Phase C9)

Phase C9 upgrades the Asset Engine so the typed `AssetSlot` *requests* emitted by
the Scene Planner (C7) are **automatically satisfied** by configurable providers,
ranked deterministically, and assembled into the same Timeline-native
`AssetTrack` the renderer already consumes.

**The Timeline IR is unchanged. The renderer is unchanged.** C9 only extends the
asset *providers* and adds the retrieval pipeline around them.

It is **100% deterministic and rule-based**. There is **no AI image/video
generation, no stock-media API, no downloads, no AI ranking** — those are later
phases. The same `(catalog, slots, config)` always resolves to the same assets.

```
AssetSlot ─► build_query ─► Provider Manager ─► Candidate Assets
          ─► Ranking (deterministic) ─► Selection ─► AssetSpec
          ─► AssetTrack ─► existing Renderer ─► MP4
```

It slots into the pipeline between the Scene Planner and the renderer, reusing
everything downstream:

```
Script ─► Storyboard (AssetSlots) ─► Asset Resolver ─► AssetTrack
       ─► Timeline ─► Renderer ─► playable MP4
```

## Architecture

Reuses the platform foundation (config, logging, benchmarking) and the C6 asset
builder/layout. New sub-packages under `asset_engine/`:

| Package | Responsibility |
|---|---|
| `asset_engine/catalog/` | `AssetCatalog` metadata index (from a directory / JSON manifest / explicit entries) + the shared value types `AssetQuery`, `AssetCandidate`, `CatalogEntry` |
| `asset_engine/providers/` | The `CandidateProvider` interface + `LocalLibraryProvider`, `FileSystemProvider`, `MockProvider`; **future** stubs (`StockMediaProvider`, `AIImageProvider`, `AIVideoProvider`) |
| `asset_engine/ranking/` | Deterministic weighted scorer (`RankWeights`, `rank_candidates`) |
| `asset_engine/resolver/` | `build_query` (slot → query), `ProviderManager` (gather + dedup), `AssetResolver` (query → candidates → rank → select) |
| `asset_engine/engine.py` | `AssetEngine.resolve_slots` — slots → validated `AssetTrack` |
| `asset_engine/benchmark/resolver.py` | Catalog-load / lookup / ranking / selection / memory benchmark |

The `AssetTrack` / `AssetClip` / layout types still live in
`reel_engine.interfaces` — the retrieval layer only *produces* them.

## Provider architecture

A **candidate provider** answers "which local assets could satisfy this query?"
via one method:

```python
class CandidateProvider(Protocol):
    name: str
    def search(self, query: AssetQuery, *, limit: int = 8) -> list[AssetCandidate]: ...
```

Phase C9 ships three deterministic, offline providers:

| Provider | Source |
|---|---|
| `LocalLibraryProvider` | a curated, pre-indexed `AssetCatalog` (the local asset library) |
| `FileSystemProvider` | a raw folder scanned into a catalog on construction |
| `MockProvider` | deterministic synthetic candidates (no files) — for hermetic tests |

The **`ProviderManager`** queries an *ordered* list of providers and returns the
union, de-duplicated by file path (earlier provider wins → order is priority).
Adding a new source later is a one-line registration; nothing downstream changes.

### Future providers (designed, not implemented)

`asset_engine/providers/future.py` defines the extension seam for later phases —
each implements the **same** `CandidateProvider` interface but raises
`NotImplementedError`:

- `StockMediaProvider` — a licensed stock library/API,
- `AIImageProvider` — generate a still with an image model,
- `AIVideoProvider` — generate B-roll with a video model.

They exist to pin the contract; **C9 does not implement them** (no AI generation,
no stock APIs).

## Catalog

`AssetCatalog` is a deterministic in-memory index of local assets — images,
videos, icons, screenshots, charts (and the other image-like kinds). Three
builders:

- `from_entries(entries)` — explicit `CatalogEntry` list (tests).
- `from_manifest(path)` — a JSON manifest (`[{path, kind, tags, width, height,
  duration_s}, …]`) — reproducible, no probing.
- `from_directory(root)` — scan a folder: **kind** from the parent folder name
  (`charts/` → `chart`) or the extension; **tags** tokenized from the filename;
  **image dimensions** via Pillow; **video** dimensions/duration via ffprobe when
  `probe_videos=True`.

`catalog.search(kind=…)` returns every entry in the same coarse family (image vs
video) in a stable order; ranking narrows from there.

## Ranking (deterministic scoring)

Each candidate is scored against the query by a fixed weighted sum of five
interpretable components, each normalised to `[0, 1]`:

| Component | Meaning | Default weight |
|---|---|---|
| **type** | exact kind (1.0), same family / image-like (0.5), still↔video (0.0) | `3.0` |
| **aspect** | closeness of the candidate aspect ratio to the slot region's | `1.5` |
| **duration** | for video, whether the clip covers the slot (stills always 1.0) | `1.0` |
| **tags** | fraction of the query's hint tags the candidate carries | `2.0` |
| **resolution** | whether the candidate has enough pixels for the region | `1.0` |

`rank_candidates` sorts best-first with a `candidate_id` tie-break, so the order
is **total and stable**. `ScoreBreakdown` exposes every component for
transparency. Weights are configurable (`assets.resolver.weights`).

## Resolution

For each `AssetSlot` the resolver:

1. **builds a query** — kind, hint tags, the region's target aspect + minimum
   pixels (from the layout + frame), and (for video) the slot duration;
2. **gathers candidates** from every provider via the manager;
3. **ranks** them;
4. **selects** the best **same-family** candidate whose score clears
   `min_score` (a still is never chosen for a video slot, or vice versa).

`AssetEngine.resolve_slots(slots, library_dir=…)` runs this for every slot and
assembles a validated `AssetTrack`, honouring each slot's layout, window, and
z-order (sided layouts like `side_by_side` alternate halves so a comparison pair
doesn't overlap). In **strict** mode an unsatisfied *required* slot raises
`AssetResolutionError` — enforcing the "no missing assets" invariant.

## Configuration

`asset_engine/config/defaults.yaml` (`assets.resolver`), layered like every
engine (`AICP__assets__*` env / user file / overrides):

| Key | Default | Meaning |
|---|---|---|
| `library_dir` | `null` | local library root (or pass `library_dir=` at call time) |
| `per_provider_limit` | `16` | max candidates each provider returns per query |
| `min_score` | `0.0` | reject a selection scoring below this (0 = accept best match) |
| `weights.{type,aspect,duration,tags,resolution}` | `3/1.5/1/2/1` | ranking weights |

## Usage

```python
from asset_engine import AssetEngine

# slots come from the Scene Planner: storyboard.all_asset_slots
track, resolutions = AssetEngine().resolve_slots(
    slots, frame_width=1080, frame_height=1920, library_dir="/my/asset/library")

import dataclasses
timeline = dataclasses.replace(timeline, asset_tracks=(track,))  # native track, renderer unchanged
```

Each `Resolution` records the pick *and* the full ranking, so you can see **why**
an asset was chosen.

## Demo & validation

```
python -m asset_engine.scripts.render_resolver_demo                  # ffmpeg MP4
python -m asset_engine.scripts.render_resolver_demo --renderer mock  # hermetic proxy
```

The demo plans a storyboard from a script, generates a local catalog (an ideal
portrait match per slot plus wrong-aspect / off-topic distractors), and
auto-satisfies **every** `AssetSlot` from it. It verifies: no missing assets,
correct timing (clip window == slot window), correct layouts (clip layout == slot
layout), that ranking chose the ideal over the distractors, deterministic
resolution, a clean Timeline validation, and a playable master + exports.

## Benchmark

```
python -m asset_engine.scripts.run_resolver_benchmark
```

Measures catalog loading, per-slot lookup, ranking, selection throughput, and
peak memory over a generated local library. Pure CPU, hermetic — no renderer,
ffmpeg, GPU, or network.

## Regression tests

`asset_engine/tests/test_resolver.py` (+ `test_resolver_benchmark.py`) — fully
hermetic and deterministic. Cover the catalog (all three builders + tokenizing),
the providers (incl. the future stubs raising `NotImplementedError`), ranking
(exact-kind wins, the still/video divide, determinism), the query builder, the
resolver (same-family only, `min_score`, dedup), and the `resolve_slots` facade
(valid track, strict no-missing, sided-layout halves, determinism).

## Limitations (Phase C9 scope)

- **Local, deterministic retrieval only** — providers resolve from a local
  catalog / filesystem; no stock APIs, no downloads, no AI generation, no AI
  ranking.
- **Ranking is heuristic** — a fixed weighted sum, not semantic matching; tag
  overlap is exact-token, not synonyms/embeddings (by design — reproducible).
- **Video metadata needs ffprobe** — image dimensions come from Pillow; video
  dimensions/duration require `from_directory(probe_videos=True)` or a manifest.
- **No generation / editing / scheduling** — the resolver only *selects* among
  assets that already exist locally.

## Future AI provider extension

The pipeline was built so new sources need **no change** to the resolver, ranker,
catalog, or renderer — only a new `CandidateProvider` registered with the
`ProviderManager`:

- **Stock media** — `StockMediaProvider.search` returns licensed candidates (with
  attribution in `AssetCandidate.meta`); ranking and selection are identical.
- **AI image generation** — `AIImageProvider.search` generates a matching still,
  writes it locally, and returns it as a candidate.
- **AI video generation** — `AIVideoProvider.search` generates matching B-roll the
  same way.
- **AI / semantic ranking** — a future ranker can replace the weighted sum behind
  the same `rank_candidates` contract; the resolver is agnostic to how scores are
  produced.

Each is a drop-in behind the existing interface — the seam is already there and
tested.
