# Batch Reel Generator (Phase C20)

An optional productivity layer over Version 1.0 that generates **many reels, one
at a time**, by reusing `creator.run` exactly as-is. It adds a queue, progress,
resume, and a batch report — nothing else.

> **Single-user and local by design.** No parallelism, no cloud, no distributed
> rendering, no scheduling, no publishing, no analytics. Reels run **sequentially**.

```
batch file (CSV/JSON/YAML)
   → for each reel, one at a time:
        creator.run  (Prompt → Workflow → Quality → Upload Metadata)
   → batch_report.json + batch_summary.md
```

---

## Quick start

```bash
# generate the 5 bundled sample reels
python -m batch_runner.run batch_runner/examples/sample_reels.yaml

# your own batch, into a chosen workspace
python -m batch_runner.run reels.csv --workspace ./my_workspace

# layer a shared base config under every reel
python -m batch_runner.run reels.yaml --config my_channel.yaml

# print only the final summary
python -m batch_runner.run reels.csv --quiet
```

Exit codes: **0** all reels passed · **2** one or more reels failed · **1** a
user/environment mistake (shown as a plain message, no traceback).

---

## Input formats

Each entry needs a **prompt**. `template` and `output` are optional; `output` is
the reel's folder name and its identity for resume/de-duplication (it defaults to
a slug of the prompt and **must be unique** across the batch). Extra fields —
`renderer`, `profiles`, `language`, `creator`, `channel`, `quality_gate` — are
per-reel overrides.

### CSV

```csv
prompt,template,output,renderer,profiles
Why saving matters,finance,saving,mock,reel_9x16 square_1x1
Stage your home to sell,real_estate,staging,mock,reel_9x16
```

### JSON

```json
[
  {"prompt": "Why saving matters", "template": "finance", "output": "saving"},
  {"prompt": "Stage your home", "template": "real_estate",
   "overrides": {"generation": {"language": "hi"}}}
]
```

### YAML

```yaml
reels:
  - prompt: "Why saving matters"
    template: finance
    output: saving
  - prompt: "Stage your home"
    template: real_estate
    language: hi           # flat override, nests under generation
```

JSON/YAML may also pass an explicit nested `overrides` mapping shaped exactly
like [`creator/config.yaml`](../../creator/config.yaml) (`generation` /
`branding` / `quality` / `paths`).

---

## What happens per reel

For each entry the runner builds a `CreatorConfig` (the base `--config` ← the
entry's overrides, with the batch workspace as the default `paths.root`) and
calls `creator.run` unchanged: **Prompt → Workflow → Quality → Upload Metadata**.
Each reel lands in the shared workspace:

```
<workspace>/
  projects/<output>/    the full Workflow Engine run
  exports/<output>/     master renditions + metadata.json + upload_preview.md
  logs/<output>.log     captured output for that reel
  batch/
    state.json          resume state (saved after every reel)
    batch_report.json   machine-readable report
    batch_summary.md    human-readable summary
```

---

## Progress

Each reel prints a line as it starts and finishes, with running totals:

```
[2/5] ▶  generating "finance-mistakes" …
      ✓ finance-mistakes  PASS  4.6s  |  done 2/5  ok 2  failed 0  remaining 3  elapsed 17.5s  ETA ~26.2s
```

The ETA extrapolates from the average time of the reels actually run so far.

---

## Failure handling

If a reel errors or fails its quality gate, the error is **logged**
(`logs/<output>.log` and the report) and the batch **continues** with the next
reel. Nothing aborts the run; the final summary lists every failure with its
reason.

---

## Resume

State is saved after **every** reel. Re-running the same command **skips reels
already completed** and continues from the first unfinished one; a previously
**failed** reel is retried. This makes an interrupted batch safe to simply
re-run — completed reels are never regenerated (no duplicates).

---

## Reports

- **`batch_report.json`** — total, passed, failed, skipped, `ok`, elapsed,
  per-reel outcomes (status / code / error / duration / output), and generation
  times (total + average over the reels run this batch).
- **`batch_summary.md`** — the same, human-readable: a totals line, a per-reel
  table, and a failures section linking each reel's log.

---

## Validate it

```bash
python -m batch_runner.scripts.validate_batch
```

Generates 5 sample reels hermetically (mock renderer, temp workspace),
simulating an interruption after 3 and resuming, and asserts: all completed,
quality PASS + metadata, no duplicates, resume works, and reports written.

---

## Scope

In scope: one user, one machine (VS Code or Colab), reels generated **one at a
time**, with resume. Explicitly **out of scope** (future enhancements): parallel
execution, cloud workers, distributed rendering, scheduling, publishing, and
analytics.
