# Media Intelligence & Asset Management Engine (Phase C13)

A deterministic media-intelligence layer that sits **between** the AI Storyboard
Engine and the Editing Engine. It selects, validates, ranks, recommends, caches,
and replaces the media a `ReelProject` uses — and it produces **media decisions
only**. Every actionable decision becomes an immutable `Patch` applied through the
Editing Engine; nothing here modifies the Timeline IR, the renderer, or the
Editing Engine.

```
AI Storyboard ─► Media Intelligence (registry / search / recommend / consistency)
              ─► immutable patches ─► Editing Engine ─► Timeline ─► renderer ─► MP4
```

## Architectural constraints (enforced)

- **Timeline IR, renderer, and Editing Engine are unchanged.** git shows zero
  edits under `reel_engine/`, `editing_engine/`, or `creator_studio/`.
- **Media Intelligence produces decisions, not mutations.** It never mutates a
  `ReelProject` (`test_media_engine_never_mutates_the_project`).
- **All media replacements are immutable patches.** A B-roll recommendation →
  `ReplaceAssetPatch`; a music recommendation → `MusicPatch`. They route through
  the Editing Engine like any other edit.
- **Deterministic architecture preserved.** No model, no network, no randomness;
  the same inputs always yield the same decisions and the same rendered bytes.
- **A mock provider exists for every external AI/media service** (Pexels, Pixabay,
  Unsplash, Shutterstock, Stability AI, Runway); the real providers are pinned as
  `NotImplementedError` stubs.
- **Reuses the existing Phase C9 retrieval/ranking pipeline** rather than
  duplicating it (`AssetCandidate` / `AssetQuery` / `rank_candidates`).

## Architecture

| Module | Responsibility |
|---|---|
| `media_intelligence/registry.py` | `AssetRegistry` — central catalog, stable content-hash IDs, metadata (kind, duration, aspect, source, license, tags), validation, stats; a `CandidateProvider` view |
| `media_intelligence/search.py` | `AssetSearchEngine` — deterministic semantic search + relevance ranking |
| `media_intelligence/recommend.py` | `AssetRecommendationEngine` — per-scene B-roll, alternatives, confidence, explanations, `to_patch()` |
| `media_intelligence/providers.py` | `MediaProvider` seam — deterministic mocks + future service stubs |
| `media_intelligence/consistency.py` | `ConsistencyEngine` — repeated people/colours/logos/styles, inconsistency flags, score |
| `media_intelligence/music.py` | `MusicRecommender` — soundtrack from tone/pacing/duration → `MusicPatch` |
| `media_intelligence/voice.py` | `VoiceRecommender` — narrator voices, multi-language, metadata only |
| `media_intelligence/cache.py` | `AssetCache` — deterministic decision cache + statistics |
| `media_intelligence/studio.py` | `MediaStudioController` — Creator Studio integration (browse / accept / reject) |
| `media_intelligence/engine.py` | `MediaIntelligenceEngine` — the facade + `MediaPlan` |

## The nine components

**1. Asset Registry** — `AssetRegistry` catalogues `RegisteredAsset`s by a **stable
ID** (`make_asset_id` = a content hash of kind + uri + dimensions + duration, so the
same asset always registers to the same ID). Each carries metadata (duration,
aspect ratio, source, license, tags). `validate()` flags unknown licenses and
missing dimensions/durations; `stats()` summarises contents. It exposes itself as
a C9 `CandidateProvider` so the existing ranker searches it unchanged.

**2. Asset Search Engine** — `AssetSearchEngine` runs deterministic *semantic*
search: free text is tokenised into tags and scored with the existing C9 weighted
ranker (type / aspect / duration / tags / resolution). Results carry a normalised
`relevance ∈ [0,1]`; ties break on the stable candidate ID.

**3. Asset Recommendation Engine** — `AssetRecommendationEngine` recommends B-roll
per scene: it derives a query from the scene's narration keywords + declared/
inferred kind + duration, ranks the registry, and returns a primary pick plus
**alternatives**, a **confidence** score, and a plain-language **explanation**. A
recommendation is advisory — `to_patch()` yields the `ReplaceAssetPatch`.

**4. Media Provider Interface** — `MediaProvider` is the C9 `CandidateProvider`
contract, reused verbatim. This phase ships deterministic `MockMediaProvider`s
(one per service via `mock_provider_for`); generative mocks flag their candidates
`generated`. The real providers (`PexelsProvider`, …, `RunwayProvider`) are stubs
that raise `NotImplementedError` — wiring a real one later is a one-line
registration with the existing `ProviderManager`.

**5. Consistency Engine** — `ConsistencyEngine.analyze` reads registry metadata
(`dominant_color`, `style`, `subject`, `brand`) across the scene→asset assignment
and flags a fragmented palette, mixed styles, a recurring person shown in clashing
styles, or a foreign brand/logo. It returns a `ConsistencyReport` with findings and
a `consistency_score`. Metadata-only, deterministic, no pixels decoded.

**6. Music Recommendation** — `MusicRecommender` maps the storyboard **tone**,
**pacing** (words/second), and **duration** to one of the existing procedural
soundtracks with a fixed scoring table. → `MusicPatch`.

**7. Voice Recommendation** — `VoiceRecommender` recommends a narrator from a
deterministic catalogue spanning English, Hindi, Hinglish, and Bengali, matched to
tone/style. **Metadata only** — no renderer change, no patch (the `ReelProject`
has no voice field in this phase).

**8. Asset Cache** — `AssetCache` is a deterministic key→value store with
hit/miss/put statistics; keys are content hashes of decision inputs, so identical
inputs always hit the same entry (stable reuse). Search and recommendation results
are cached through it.

**9. Creator Studio Integration** — `MediaStudioController` wraps a `StudioSession`
(by composition — the Studio is unmodified). A creator browses `RecommendationCard`s
with confidence, `accept`s a scene (applies a `ReplaceAssetPatch` via the session's
existing `replace_asset` command), `reject`s one (no edit), or `accept_music`s (a
`MusicPatch`). Accepted picks feed a live `consistency()` check.

## Demo

```
python -m media_intelligence.scripts.render_media_demo                  # real MP4 (ffmpeg)
python -m media_intelligence.scripts.render_media_demo --renderer mock  # hermetic proxy
```

Builds a deterministic registry, searches/ranks assets, recommends B-roll + music +
voice (with confidence and explanations), applies the recommendations as immutable
patches through the Creator Studio, checks project-wide consistency, and **exports
an updated playable reel** through the existing renderer. Exit `0` on success.

## Regression tests

`media_intelligence/tests/` — fully hermetic and deterministic (mock providers, a
synthetic in-memory registry, the mock renderer; no ffmpeg/network/GPU/files).
Cover the registry (stable IDs, validation, stats), search ranking, recommendations
(confidence/explanations/patches/determinism), the provider seam (mocks +
`NotImplementedError` stubs), the consistency engine (palette/style/subject/brand
flags), music/voice recommendation, the cache, the Studio integration, and the
end-to-end recommend → patch → render loop with byte-identical replay.

## Limitations (Phase C13 scope)

- **Decisions, not downloads** — recommendations pick from the registry and encode
  the choice as a kind/layout patch; resolving a specific file into the render is
  the existing Asset Engine's job at build time.
- **Metadata-only consistency** — coherence is judged from descriptive metadata,
  not pixel analysis (deterministic by design).
- **Mock providers only** — no production AI providers, no online asset downloads,
  no cloud storage, no collaboration in this phase.
- **Voice is metadata-only** — no voice field on the project and no renderer change.
