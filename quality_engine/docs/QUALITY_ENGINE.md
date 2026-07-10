# Quality Engine — Simple Local Reel QA (Phase C16)

The Quality Engine is a small **quality gate that runs after rendering**. Given a
rendered reel it produces a single **PASS / FAIL** verdict plus a per-check report,
so the pipeline can refuse to ship a broken reel.

It is deliberately simple and honest:

- **single-user, local-only** — no cloud, no database, no network, no auth;
- **deterministic** — a fixed rule per check, so the *same* rendered reel always
  yields the *same* report. **No AI, no ML, no scoring** of any kind;
- **read-only** — it changes **no** renderer, **no** Timeline, **no** engine. It
  only *reads* the files a render produced and the Timeline it was rendered from.

```
Workflow Engine ─► Render ─► Export ─► Quality Check ─► PASS | FAIL
```

## What it checks

| Check | Kind | Rule |
|---|---|---|
| **Video file exists** | required | the master file is on disk |
| **Video playable** | required | the master decodes to ≥1 frame with real dimensions |
| **Audio detected** | required | an audio stream (muxed) or a WAV sidecar is present |
| **Audio duration matches video** | required | `\|audio − video\|` ≤ tolerance (muxed audio passes by construction) |
| **Export resolution correct** | required | master aspect matches the Timeline; each export aspect matches its profile |
| **Duration within limits** | required | reel length is within the configured min/max |
| **Avatar present** | advisory | an enabled avatar plan with ≥1 clip |
| **Voice present** | advisory | narration clips exist, or the audio is non-silent |
| **Captions generated** | advisory | the Timeline has a caption track (or a non-empty SRT sidecar) |
| **Branding present** | advisory | the Timeline carries branding elements |
| **Music present** | advisory | the Timeline carries a music bed |

**Required** checks gate: a violation is a `FAIL`. **Advisory** checks never fail the
gate — a missing optional element is a `WARN` (or `SKIP` when it cannot be judged),
so a minimal but valid reel still passes while missing pieces are surfaced.

`overall = FAIL if any check FAILED, else PASS`.

### Why content presence comes from the Timeline

Captions / branding / music presence is read from the declarative
[`Timeline`](../../reel_engine/interfaces/types.py), **not** by scraping the video.
That makes those checks identical for both renderers: the `mock` backend writes an
aspect-preserving raw-AVI proxy plus WAV/SRT sidecars, while the `ffmpeg` backend
muxes audio and burns captions/branding into the MP4. When no Timeline is supplied
(standalone `--master` mode) the checks fall back to the sidecars they can see, or
`SKIP`.

### Resolution: aspect is the invariant

The mock renderer writes a downscaled proxy (longest side capped by
`render.mock_max_dim`) that **preserves aspect ratio exactly**, so the resolution
check compares *aspect ratios* (`9:16`, `1:1`, `16:9`) rather than exact pixels —
the invariant that holds for both backends. Set `expected_width`/`expected_height`
in [`QualityConfig`](../checker/config.py) to additionally pin exact master dims
(useful for a real MP4).

## How probing works (hermetic)

`inspect_reel` reads the reel's actual files using only:

- the **stdlib** raw-AVI / WAV readers (`read_raw_avi`, `read_wav`) — the path the
  mock renderer's output takes, needing **no ffmpeg, numpy, or network**; and
- the existing **`ffprobe`** wrapper (`probe_media`) — the fallback for real MP4s,
  reached only when the master is not a stdlib-readable raw-AVI.

So the whole test suite runs with zero external tools, while a real MP4 still gets
probed correctly. Probing never raises to the caller: any failure is captured into
`ReelInspection.errors` and surfaces as a failed check.

## Usage

### CLI

```bash
# generate a reel through the Workflow Engine (mock, hermetic) and check it:
python -m quality_engine.scripts.check_reel

# check an already-rendered master (sidecars auto-detected):
python -m quality_engine.scripts.check_reel --master path/to/master.avi
python -m quality_engine.scripts.check_reel --master out.mp4 --timeline timeline.json

# JSON report, custom limits:
python -m quality_engine.scripts.check_reel --json --min-duration 5 --max-duration 60
```

Exit codes: **0 = PASS**, **2 = FAIL**, **1 = usage/environment error**.

Example report:

```
QUALITY REPORT
==============

Overall: PASS

Checks
  ✓ Video file exists
  ✓ Video playable
  ✓ Audio detected
  ✓ Audio duration matches video
  ✓ Avatar present
  ✓ Voice present
  ✓ Captions generated
  ✓ Branding present
  ✓ Music present
  ✓ Export resolution correct
  ✓ Duration within limits

Warnings
  None
```

### Library API

```python
from quality_engine import QualityChecker, ReelArtifacts

# from a RenderResult:
artifacts = ReelArtifacts.from_render_result(result, timeline=timeline,
                                             voice_clips=voice_wavs, avatar=avatar_plan)
report = QualityChecker().check(artifacts)
print(report.render_text())
assert report.ok
```

### Workflow Engine gate

```python
from workflow_engine import WorkflowEngine
from quality_engine import check_workflow_result

result = WorkflowEngine(root="run").run(workflow, run_id="run")
report = check_workflow_result(result)     # reads master + timeline + voice + avatar
if not report.ok:
    raise SystemExit(report.render_text())
```

`check_workflow_result` reads only the artifacts the run already produced — it
modifies nothing. A trimmed pipeline (missing timeline / voice / avatar) simply
degrades the affected checks to warnings/skips rather than raising.

## Layout

```
quality_engine/
  __init__.py            public API
  checker/
    report.py            CheckStatus / CheckResult / QualityReport (+ text/JSON)
    model.py             ReelArtifacts (what to check) + ReelInspection (measured)
    config.py            QualityConfig thresholds/limits
    inspect.py           inspect_reel — deterministic file probing
    checks.py            the eleven fixed checks
    engine.py            QualityChecker facade
  workflow_link.py       check_workflow_result — quality-gate a WorkflowResult
  scripts/check_reel.py  the CLI
  tests/                 hermetic deterministic tests (no GPU/ffmpeg/APIs)
  docs/QUALITY_ENGINE.md this document
```

## Configuration

[`QualityConfig`](../checker/config.py) (all optional):

| Field | Default | Meaning |
|---|---|---|
| `min_duration_s` | `3.0` | shortest allowed reel |
| `max_duration_s` | `90.0` | longest allowed reel |
| `audio_sync_tolerance_s` | `0.5` | allowed audio↔video duration gap |
| `expected_width` / `expected_height` | `None` | pin exact master dims (else aspect vs Timeline) |

## Scope (and what is intentionally out)

This phase is *simple local QA only*. It deliberately does **not** include AI
scoring, viewer-engagement prediction, SEO scoring, publishing, or analytics —
those belong to later phases. The Quality Engine answers exactly one question:
*is this rendered reel structurally sound enough to ship?*
