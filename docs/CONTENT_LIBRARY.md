# Content Library — Local, Single-User Content Store (Phase C15)

The Content Library is a lightweight place to keep your creative work on disk. It
manages **projects** (a prompt + its generated reel) and shared content **pools**
(assets, voices, avatars, music, brand kits, exports), with deterministic search
and one-call generation through the Workflow Engine.

It is deliberately small and local:

- **single-user**, **local-only** — no cloud, no database server, no authentication,
  no multi-user support;
- storage is **just folders + JSON** — portable between VS Code and Google Colab,
  and a backup is a folder copy;
- everything is **deterministic** — an injectable clock makes manifests reproducible.

## Folder layout

Everything lives under one library root (default `content_library/data/`):

```
content_library/data/
  index.json                 library-wide project index (fast, deterministic search)
  projects/
    <project_id>/
      project.json           the immutable ProjectRecord manifest
      run/                   the Workflow Engine run directory for this project
        journal.json           workflow run state (resume/incremental cache)
        storyboard.json        the AI storyboard
        render/master.avi      the rendered master (+ per-profile exports)
        …                      voice WAVs, timeline JSON, etc.
  assets/                    shared media (files)   ─┐
  voices/                    narrator profiles        │  content pools:
  avatars/                   avatar plans             │  <pool>/registry.json
  music/                     music beds               │  + <pool>/files/…
  brands/                    brand kits (metadata)    │
  exports/                   published deliverables  ─┘
  cache/                     library scratch
```

A project is a **self-contained bundle**: its manifest and its entire workflow run
live under `projects/<id>/`, so a project can be copied, zipped, or moved on its own.

## Project model

A `ProjectRecord` is an immutable manifest. Like every document on the platform it
is never mutated in place — an update returns a new record with a bumped
`modified_at` — so a saved project is a stable, reproducible snapshot.

| Field | Meaning |
|---|---|
| `project_id` | deterministic, readable id: `<title-slug>-<6 hex of title\|prompt>` |
| `title` | human title |
| `prompt` | the generation prompt |
| `template` | the storyboard template ("type") |
| `tags` | free-form tags (deduped) |
| `status` | `draft` → `rendered` → `exported` → `archived` |
| `presentation` | reel settings (theme / soundtrack / caption / dimensions / brand facts) |
| `storyboard` | compact summary + a `ref` to `run/storyboard.json` |
| `workflow_state` | the last run: run id, renderer, profiles, ok, per-stage status |
| `outputs` | `OutputRef`s for the master + each export (path, content hash, dims) |
| `created_at` / `modified_at` | ISO timestamps (from the library clock) |

Times are supplied by an injectable clock (`ContentLibrary(clock=…)`), so tests and
benchmarks are fully deterministic — a fixed clock yields byte-identical manifests.

```python
from content_library import ContentLibrary
from workflow_engine import Presentation

lib = ContentLibrary("content_library/data")
project = lib.create_project(
    "Investing Early Reel",
    prompt="Why investing in real estate early is beneficial",
    template="real_estate", tags=("finance", "property"),
    presentation=Presentation(theme="finance", soundtrack="upbeat").to_dict())
```

## Search

Search is **purely deterministic and rule-based** — no vector database, no
embeddings. A single `index.json` holds a compact summary of every project, and
queries filter + stably sort those summaries:

```python
lib.search(title="real")                     # case-insensitive substring
lib.search(tag="property")                    # tag membership
lib.search(tags=("property", "luxury"))       # all tags (AND)
lib.search(template="real_estate")            # by type
lib.search(status="rendered")                 # by status
lib.search(created_after="2026-01-01",        # ISO date ranges (inclusive)
           modified_before="2026-02-01")
lib.search(tag="finance", sort="title")       # combine filters + choose a sort
```

Sorts (`modified_desc` default, `created_*`, `title`, `id`) are total orders — ties
always break by `project_id`, so the same query always returns the same order. The
index is maintained on every save/delete and self-heals: if `index.json` is missing
it is rebuilt from the manifests (`lib.rebuild_index()`).

## Content pools

Besides projects, the library manages shared content pools — each a folder plus a
`registry.json` of immutable `PoolItem`s. An item may carry a file (copied into the
pool and content-hashed) or be metadata-only (a brand kit, a voice profile):

```python
lib.assets.add("Brand Logo", source="logo.png", kind="image", tags=("brand",))
lib.brands.add("Finance Dark Kit", kind="brand_kit",
               meta={"theme": "finance", "soundtrack": "upbeat"})   # metadata only
lib.voices.add("Narrator EN", kind="voice_profile", meta={"model": "mock"})

lib.assets.search(tag="brand")                # deterministic per-pool search
```

Pools: `assets`, `voices`, `avatars`, `music`, `brands`, `exports`.

## Workflow integration

The library runs a project's full `prompt → export` pipeline through the **C14
Workflow Engine**, without changing any workflow logic — it simply constructs a
`WorkflowEngine` **rooted at the project's own directory**, so every artifact lands
in `projects/<id>/run/`:

```python
outcome = lib.generate(project.project_id, renderer="mock")   # or "ffmpeg"
outcome.record.status        # "rendered"
outcome.record.outputs       # master + exports (paths relative to the project dir)
outcome.result               # the standard WorkflowResult
```

Because the run directory is **stable** (a real project directory, not a scratch
temp dir), reloading a project and re-rendering it **reuses the cached run and
reproduces byte-identical outputs**:

```python
reloaded = lib.load(project.project_id)       # save → reload round-trips exactly
again = lib.rerender(project.project_id)       # resumes: every stage cached
# → the master + exports are byte-for-byte identical to the first render
```

A forced re-render (`lib.generate(pid, force=("render",))`) re-runs the renderer and
still preserves each output's content hash (its logical identity); with the
deterministic mock renderer the bytes are identical too. This is the guarantee the
validation demo checks end to end:

```
python -m content_library.scripts.library_demo                  # hermetic (mock)
python -m content_library.scripts.library_demo --renderer ffmpeg  # real MP4
```

    create project → generate reel → save → reload → re-render → verify identical

## Benchmark

```
python -m content_library.scripts.run_benchmark --n-projects 250
```

Measures project **save**, **load**, **search**, and **metadata indexing** over N
synthetic projects (plus throughput and RSS). Hermetic — local JSON only, no
workflow generation, GPU, ffmpeg, or network.

## Tests

`content_library/tests/` — fully hermetic and deterministic (a counter clock; the
mock voice adapter + mock renderer for the one integration test). No GPU, no APIs.
Cover the model/serde, library CRUD, search + index (rebuild + self-heal), the
content pools, and the workflow integration's identical-output guarantee.

## Backup strategy

Because the whole library is **plain local files**, backup and portability are
trivial and need no tooling:

- **Back up** — copy or archive the library root: `cp -r content_library/data backup/`
  or `zip -r library.zip content_library/data`. `index.json` and every
  `registry.json` are regenerable (`lib.rebuild_index()`), so a backup of just the
  `projects/`, `assets/`, … folders is sufficient; the indexes rebuild on next open.
- **Move a single project** — a project is self-contained under `projects/<id>/`;
  copy that one directory into another library's `projects/` and run
  `rebuild_index()`.
- **VS Code ⇄ Colab** — the library is a portable folder tree; sync it with the
  repo, Google Drive, or a zip. Paths inside manifests are **relative to the project
  directory**, so a moved library still resolves its outputs.
- **Version control** — the library runtime data (`content_library/data/`,
  `demo_data/`) is git-ignored (it is regenerable); commit source, not generated
  media. For history of the *manifests* specifically, they are small JSON and can be
  committed to a separate content repo if desired.
- **Integrity** — every output and file-backed pool item records a `content_hash`,
  so a backup can be verified against the manifest after restore.

## Scope (Phase C15)

In scope: local project + content management, deterministic search, and Workflow
Engine integration with reproducible outputs. **Out of scope** (later phases): batch
generation, cloud sync, publishing, analytics, and deployment.
