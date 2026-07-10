# Performance — Local Generation Speed & Resource Use (Phase C17)

This document describes the **local performance optimizations** applied to the reel
generation pipeline. The goal of Phase C17 is narrow and honest:

> **Make the same reel generate faster and with lower peak RAM — without changing a
> single output byte, and with quality still PASS.**

It is a **single-user, local-only** effort (VS Code + Google Colab). There is **no
cloud, no distributed rendering, no Kubernetes, no batching, and no new models**. We
only optimize the pipeline that already exists.

```
Storyboard ─► Scene ─► Voice ─► Avatar ─► Assets ─► Media Intel ─► Editing ─► Timeline ─► Render ─► Export ─► Quality
        └──────────────────────── every stage cached on unchanged input ────────────────────────┘
```

The overriding invariant across all of the below: **output is identical**. Each
optimization either reuses work that would produce the same bytes, or frees memory
that is no longer needed — never anything that alters the rendered master, the
exports, or the quality verdict.

---

## 1. Model reuse — don't reload weights

A single [`VoiceEngine`](../voice_engine/engine.py) already reuses its adapters
across calls via its own `_engines` cache, but that cache **dies with the instance**.
A second `VoiceEngine` (a second reel in the same process, or a forced re-render)
would reload the same multi-hundred-MB weights from scratch.

Phase C17 adds a tiny **process-global adapter cache** in
[`voice_engine/adapters/registry.py`](../voice_engine/adapters/registry.py):

- `get_or_create_adapter(id, device, config)` returns a **cached, already-loaded**
  adapter when one exists, else creates and caches it;
- the cache key is `(adapter_id, device, config)` — differently-configured engines
  **never** share an adapter, so reuse can't leak the wrong weights;
- `unload_model` calls `forget_cached_adapter` so an explicit unload really frees RAM;
- `clear_adapter_cache()` / `cached_adapter_count()` support test hygiene and manual
  freeing.

**Why it's safe:** the same weights produce the same audio. Only the redundant reload
is avoided. Loaded models are reused whenever possible, across engine instances.

---

## 2. Workflow cache — reuse completed stages

The Workflow Engine's incremental executor (Phase C14) already **content-hashes each
stage's inputs** and reuses a completed stage's output when the input hash is
unchanged. Phase C17 leans on this rather than reinventing it.

- Each stage records an `input_hash`; on re-run, an unchanged hash is a **cache hit**
  (`StageStatus.CACHED`) that costs ~0 s — the artifact is not regenerated.
- Regenerating the **same** reel therefore re-executes **nothing**: all ten stages are
  reused and only the (cheap, deliberately re-run) quality gate does any work.

This is the single biggest win on a warm run — see the profiler numbers below.

---

## 3. Content Library cache — no duplicate assets or exports

`ContentPool.add()` in [`content_library/pools.py`](../content_library/pools.py)
previously **always copied** the source file, so adding the same asset — or the same
export rendition from two projects — wrote duplicate bytes on disk.

Phase C17 makes the pool **content-addressed**:

- `add(..., dedup=True)` (default): when an item with the **same content hash** already
  exists, the new item **references the stored file** instead of copying a second
  identical one (`meta.dedup_of` records which item it shares);
- `find_by_hash(hash)` looks up a stored item by content hash;
- `remove()` is **reference-counted**: a shared (deduped) file is deleted only when its
  **last** referrer is removed.

The first occurrence keeps its filename and behaviour; only redundant copies are
avoided. Pass `dedup=False` to force a private copy.

---

## 4. Renderer optimization — fewer temp files, fewer passes

The **mock** renderer ([`reel_engine/render/mock_renderer.py`](../reel_engine/render/mock_renderer.py)):

- **releases the master frame list** (the render's largest allocation) as soon as it is
  written, *before* building any export renditions — so peak is **one** frame list, not
  the master's plus an export's;
- **frees each export rendition's frames + scale cache** before the next one is built;
- the three overlay passes (captions / branding / music) already **no-op passthrough**
  (return the same list) when their track is absent, so an absent track costs no
  full-frame copy. A regression test pins this so it can't creep back.

The **ffmpeg** backend already skips absent-track filter passes and cleans up every
intermediate file. Merging its remaining filter passes is **intentionally not done** —
it would change the encoded bytes, violating the output-identical invariant.

---

## 5. Memory optimization — lower peak RAM

The same changes as §4, viewed through the memory lens: temporary objects are released
the moment they are no longer needed, and duplicate copies are avoided (the passthrough
overlays return the *same* list rather than a copy). Combined with the model-reuse cache
(§1), which avoids holding two copies of the same weights, peak RAM is the largest
single working set — not the sum of everything the run ever touched.

---

## 6. Timing report

[`workflow_engine/timing.py`](../workflow_engine/timing.py) turns a completed
`WorkflowResult` into a small, readable **per-stage timing report**. It is **pure
presentation** over data the run already produced — it has no clock of its own, runs
nothing, and mutates nothing. Cached stages are shown as `(cached)`; an optional extra
row (e.g. the post-render Quality check) can be appended so one report covers the whole
generation.

```
Workflow Timing
===============

  Storyboard             0.03 s
  Voice                  2.57 s
  Avatar                 0.00 s
  Timeline               0.42 s
  Render                 4.14 s
  Export                 0.91 s
  Quality                0.15 s   (measured)
  ------------------------------
  Total                  8.24 s
```

`WorkflowTiming` also exposes `total_s`, `executed_s` (time in stages that actually
ran), `n_reused`, and `to_dict()` for JSON.

---

## CLI — profile + validate

```
python -m workflow_engine.scripts.profile_workflow                     # hermetic (mock)
python -m workflow_engine.scripts.profile_workflow --renderer ffmpeg   # real MP4
python -m workflow_engine.scripts.profile_workflow --json              # also emit JSON
```

The profiler generates the **same reel twice** and prints a timing report for each run,
then checks the three performance guarantees. It is **hermetic by default** (mock
storyboard/voice + mock renderer): **no GPU, no ffmpeg, no network**.

Exit codes: `0` = all guarantees held, `2` = a guarantee failed, `1` = usage/environment
error.

### What it validates

1. **Second run faster** — the warm run reuses completed stages from the workflow cache;
2. **Output identical** — the master + every export are compared **byte-for-byte**
   (SHA-256) between the cold and warm runs;
3. **Quality still PASS** — the C16 Quality Checker returns PASS on both runs.

### Representative run (mock, hermetic)

```
Run 1 — cold (all stages execute)     Total  8.24 s   quality: PASS
Run 2 — warm (cache reuses stages)    Total  0.18 s   quality: PASS

Performance guarantees:
  [OK] second run faster (8.24s -> 0.18s, 46.9x; 10 stages reused)
  [OK] output identical (3 files, byte-for-byte)
  [OK] quality still PASS
```

Absolute numbers vary by machine; the **ordering** (warm < cold), the **byte-identical
output**, and the **PASS verdict** are the guarantees.

---

## Tests

All Phase C17 tests are **hermetic** and require **no GPU** and no ffmpeg:

| Area | Test |
|---|---|
| Timing report | [`workflow_engine/tests/test_timing.py`](../workflow_engine/tests/test_timing.py) |
| Model reuse | [`voice_engine/tests/test_model_reuse.py`](../voice_engine/tests/test_model_reuse.py) |
| Content Library dedup | [`content_library/tests/test_pool_dedup.py`](../content_library/tests/test_pool_dedup.py) |
| Renderer memory | [`reel_engine/tests/test_render_memory.py`](../reel_engine/tests/test_render_memory.py) |

---

## Out of scope (deliberately)

Phase C17 optimizes only the existing local pipeline. It does **not** add batch
generation, publishing, analytics, cloud execution, distributed rendering, Kubernetes,
or new AI models. Anything that would change the rendered bytes (e.g. merging the ffmpeg
filter passes) is left out on purpose.
