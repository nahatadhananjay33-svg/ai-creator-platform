# Workflow Engine — Deterministic Production Orchestrator (Phase C14)

The Workflow Engine is the **single execution layer** for the AI Creator Platform.
It composes every existing engine — AI Storyboard, Scene Planning, Voice, Avatar,
Assets, Media Intelligence, Editing, the Timeline IR, the Renderer, and Export —
into one deterministic, resumable, content-addressed pipeline.

It **changes no engine**. Every stage only calls existing public APIs, and:

- the **Timeline IR is unchanged**,
- the **renderer is unchanged**,
- editing still happens through the Editing Engine's immutable patches.

The workflow only *orchestrates*.

```
prompt ─► Storyboard ─► Scene Planning ─► Voice ─► Avatar ─► Assets
       ─► Media Intelligence ─► Editing ─► Timeline ─► Renderer ─► Export
```

## One idea

**Stages are immutable values, artifacts are content-addressed, and a stage is
re-executed only when the content of its inputs changes.** From that single rule
fall out resume, retry, and incremental rebuild — no special cases.

## Architecture

| Package | Responsibility |
|---|---|
| `workflow_engine/core/` | The engine-agnostic model: `Artifact`, `WorkflowStage`, `WorkflowContext`, `DependencyGraph`, `Workflow`/`WorkflowResult` |
| `workflow_engine/core/codecs.py` | Per-kind serializers so every artifact round-trips to disk (resume across processes) |
| `workflow_engine/execution/` | `WorkflowExecutor` (run/resume/retry/incremental), `RunJournal` (persisted state), `plan_incremental` (what-if) |
| `workflow_engine/stages/` | One immutable stage per existing engine + `build_default_workflow` (the DAG) |
| `workflow_engine/validation/` | `validate_workflow` / `validate_run` / `validate_resume` |
| `workflow_engine/benchmark/` | Hermetic startup / cache / throughput benchmark |
| `workflow_engine/engine.py` | `WorkflowEngine` — the facade (build, run, resume, rebuild, validate, plan) |

The Workflow Engine depends on the engines; **no engine depends on it**.

## The core model

- **`Artifact`** — an immutable, content-addressed stage output identified by
  `(name, kind, content_hash)`. Its live `value` is excluded from equality, so an
  artifact reloaded from disk on resume compares equal to the one that produced it.
  Kinds: `storyboard`, `project`, `timeline`, `json`, `file`, `fileset`.
- **`WorkflowStage`** — a frozen dataclass carrying only its wiring (`name` /
  `needs` / `produces`) and its own scalar parameters. It holds no engine
  instances and no mutable state; engines are constructed inside `run()`. Its
  `signature()` is a stable hash of its type + parameters.
- **`WorkflowContext`** — the artifact store passed to each stage. Stages read
  inputs via `value(name)` (decoded lazily from disk on a cold resume) and return
  new artifacts; they never mutate the context.
- **`Workflow`** — an immutable, validated bundle of stages + the induced
  `DependencyGraph`. **`WorkflowResult`** — one run's per-stage outcomes + final
  artifacts.

## Dependency graph

A workflow is a DAG; edges are the `needs` relation (stage → the stages it depends
on). The graph owns the algorithms:

- **`topological_order()`** — a *stable* order (ties broken by declaration index),
  so the same workflow always runs the same way;
- **`levels()`** — the DAG's antichains: stages in one level depend only on earlier
  levels, so they are mutually independent and **parallel-safe**;
- **`validate()`** — every dependency resolves and the graph is acyclic (a cycle or
  an unknown dependency is a construction-time error).

The default pipeline is not a straight line — after the storyboard, the
scene-plan / voice / asset branches are independent and rejoin at the render:

```
storyboard ─┬─► scene_plan ─► assets ─► media_intel ─► editing ─► timeline ─┐
            └─► voice ─► avatar ───────────────────────────────► render ◄──┘
                                                                    └─► export
```

## Stages (each wraps one existing engine)

| Stage | Produces | Reuses | Notes |
|---|---|---|---|
| `storyboard` | `storyboard` | `ScriptEngine.generate_storyboard` | prompt → validated `AIStoryboard` |
| `scene_plan` | `scene_plan` | `EditingEngine.plan_scene_storyboard` (Scene Engine) | deterministic plan summary |
| `voice` | `voice` | `VoiceEngine.generate` (mock adapter) | one WAV per scene, hermetic |
| `avatar` | `avatar` | — | deterministic avatar **plan** (see Limitations) |
| `assets` | `assets` | `AssetRegistry` (C13) | the available-asset catalog |
| `media_intel` | `media_plan` | `MediaIntelligenceEngine.plan` | media decisions → JSON patch specs |
| `editing` | `project` | `EditingEngine.apply` (immutable patches) | applies media + explicit edits |
| `timeline` | `timeline` | `EditingEngine.build_timeline` | lowers to the **existing** Timeline IR |
| `render` | `master` | `reel_engine.render.get_renderer` | master + exports in one pass |
| `export` | `exports` | `reel_engine.render.probe_media` | validate + package the renditions |

Every stage's `run()` only invokes existing public APIs; no engine logic is
duplicated in the workflow.

## Artifacts

Artifacts are the unit of data flow and the unit of caching. Each is content-hashed
by *what actually determines its output*, deliberately excluding volatile detail so
the cache is correct even when a backend's bytes are not bit-reproducible:

- a **project** hashes by its storyboard + presentation (not its revision counter);
- a **timeline** hashes by the engine's own `timeline_content_hash`;
- a **master** hashes by *renderer + timeline hash + profiles* (not the encoded
  video bytes, which a codec need not reproduce bit-for-bit).

Every artifact is serializable: structured ones round-trip through the owning
engine's JSON serializer (`storyboard` / `project` / `timeline`), plain JSON ones
verbatim, and file/fileset ones are addressed by path. That is what makes a resume
in a **fresh process** transparent to downstream stages.

## Resume

Every run owns a directory with one `journal.json` recording, per stage: its input
hash, its signature, its status, and a codec payload ref for each artifact.
Re-invoking with the same `run_id` **resumes**: a stage is reused whenever the
journal holds a prior success with the same input hash *and* its artifact payloads
still exist on disk. An interrupted or failed run continues from where it stopped;
a stage whose upstream failed is left `PENDING` (never run on missing inputs).

`validate_resume` asserts the invariant directly: resuming a completed run executes
nothing and reproduces every artifact's content hash.

## Incremental execution

Each stage's **input hash** folds together its signature and the content hashes of
its input artifacts:

```
input_hash = H( stage.signature(),  { input_artifact.content_hash },  salt )
```

Because that depends on the *content* of upstream outputs, the cache is transitive:

- an unchanged input ⇒ identical input hash ⇒ **reuse** the cached outputs;
- a changed input ⇒ different input hash ⇒ **re-run**, and its new output hash
  cascades to re-run exactly the affected downstream subtree — *rebuild downstream
  only*.

Content addressing is smarter than a naïve "dirty ⇒ rebuild everything below":
if a re-run happens to produce the **same** output (an idempotent change upstream),
its content hash is unchanged and the cascade stops there.

`plan_incremental(workflow, journal)` exposes this as a **what-if**: it classifies
every stage as *reuse*, *rebuild*, or *new* before running anything, by comparing
each stage's current signature to the journal. Each stage's signature is scoped to
exactly what it consumes (e.g. scene planning depends on the storyboard +
creator/channel, not the theme), so the prediction matches the actual run exactly.

```python
from workflow_engine import WorkflowEngine, Presentation

engine = WorkflowEngine()
wf = engine.build("Why investing in real estate early is beneficial",
                  template="real_estate", presentation=Presentation(theme="modern"))
engine.run(wf, run_id="job")                         # cold: all stages execute

wf2 = engine.build("...same prompt...", presentation=Presentation(theme="finance"))
plan = engine.incremental_plan(wf2, run_id="job")    # predict, without running
#   plan.will_run == {"editing", "timeline", "render", "export"}
#   plan.reuse    == {"storyboard", "scene_plan", "voice", "avatar", "assets", "media_intel"}
engine.run(wf2, run_id="job")                        # rebuilds only the downstream subtree
```

## Validation

- **`validate_workflow`** (static) — the graph is a DAG (no unknown deps, no
  cycles), a stable ordering exists, no artifact has two producers, and no produced
  artifact is an orphan (never consumed and not a declared output).
- **`validate_run`** (post-run) — no failed or blocked stages, every declared
  artifact of a satisfied stage is present (no missing artifacts), and the store
  holds no undeclared (orphan) artifacts.
- **`validate_resume`** (active) — resume correctness: a resume of a completed run
  reuses every stage and reproduces identical artifact hashes.

## Benchmark

```
python -m workflow_engine.scripts.run_benchmark
```

Measures startup (build + validate), per-stage execution, cache hits (warm resume)
vs misses (cold run), incremental rebuild, peak RSS, and overall throughput
(stages/s). Hermetic — mock voice + mock renderer, no GPU/model/ffmpeg/network.

## Demo

```
python -m workflow_engine.scripts.workflow_demo                  # hermetic (mock)
python -m workflow_engine.scripts.workflow_demo --renderer ffmpeg  # real MP4
```

Runs the full `prompt → export` pipeline and verifies: every stage executes and
the run validates; resume re-executes nothing and preserves every artifact hash;
changing one presentation setting rebuilds only the affected downstream stages
(and the incremental planner predicts it exactly); and the master + platform
exports exist and probe cleanly.

## Tests

`workflow_engine/tests/` — fully hermetic and deterministic (tiny in-memory stages
for the executor; the real mock pipeline for the engine stages). No GPU, no APIs.
Cover: the dependency graph (ordering, levels, cycles, unknown deps), artifact +
codec round-trips, resume (including cold-process), retry (success within attempts,
failure blocks downstream, resume-after-fix), incremental execution (rebuild
downstream only, planner-matches-actual), cache correctness, artifact validation,
and parallel-safe scheduling (permuting independent stages yields identical hashes).

## Limitations (Phase C14 scope)

- **Avatar plan, not avatar video** — the Avatar Engine currently ships research
  infrastructure only (no production generation API, Phase A3), so the `avatar`
  stage produces a deterministic per-scene avatar **plan** (the exact input a future
  Avatar Engine production API will consume) rather than invoking a talking-head
  model. Wiring that model in is a stage swap, no workflow change.
- **Narration is a produced artifact** — the `voice` stage synthesizes per-scene
  narration WAVs; folding them into the scene audio track is a scene/renderer
  concern left unchanged here (the workflow composes; it does not modify engines).
- **Cross-run reproducibility of media tracks** — the procedural-music track embeds
  its generated-WAV file paths, so the `timeline`/`master` hashes are stable within
  a run id (resume) but not across independent run directories; every other artifact
  is fully content-reproducible.
- **Single-process execution** — stages in a `levels()` antichain are proven
  parallel-safe, but the executor runs them sequentially for determinism; the seam
  for a scheduler is below.

## Future distributed execution

The model was built so a distributed scheduler can drop in without touching a stage:

- **Immutable stages + content-addressed artifacts** — a stage is a pure value; its
  output depends only on its input hashes. Stages can therefore run on any worker,
  and a shared content-addressed artifact store turns the per-run journal into a
  global cache (reuse across runs and machines).
- **`levels()` is the schedule** — each antichain is a set of independent tasks a
  scheduler can fan out across workers; the executor's sequential loop is the only
  piece a distributed backend replaces.
- **The journal is the coordination point** — input hashes and payload refs are
  already the currency a work queue needs to dedupe, resume, and shard.
- **Retry / resume are already first-class** — a worker crash is just a resume; a
  transient failure is just a retry.

None of this changes the Timeline IR, the renderer, or any engine. Publishing,
scheduling, cloud execution, distributed rendering, analytics, and deployment are
explicitly **out of scope** for Phase C14.
