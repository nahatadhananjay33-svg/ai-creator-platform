# AI Creator Platform — Version 1.0 (Phase C19)

Version 1.0 is the point where the platform becomes **usable by a brand-new
single user**. Everything built through Phase C18 already worked; C19 is the
polish that puts it behind **one command, one config file, and one workspace**,
with clean errors and a task-first README.

> **The whole promise, in one line:**
> a brand-new user can clone the repo, install it, run `python -m creator.run`,
> pass the quality check, and get upload-ready metadata — with no cloud, no
> accounts, and no GPU.

```
Prompt  →  Workflow  →  Quality  →  Upload Metadata  →  Finished
```

---

## 1. What Version 1.0 is (and is not)

| It **is** | It is **not** |
|---|---|
| single-user, local | multi-user / SaaS |
| VS Code + Google Colab | cloud-deployed |
| one reel per command | batch generation |
| files you upload yourself | automatic publishing |
| deterministic + hermetic by default | analytics / dashboards |

No new engines and no new AI features were added in C19 — it is a **usability
layer** (`creator/`) over the engines that already exist.

---

## 2. The single command

```bash
python -m creator.run --prompt "5 tips for first-time home buyers" --template real_estate
```

`creator.run` owns no generation logic. It composes four existing subsystems and
lands the result in a standardized place:

| Step | Subsystem | Entry point reused | Result |
|---|---|---|---|
| Prompt → Workflow | Workflow Engine | `WorkflowEngine.produce` | a rendered reel (10-stage DAG) |
| Quality | Quality Engine | `check_workflow_result` | PASS / FAIL + per-check report |
| Upload Metadata | Upload Assistant | `generate_upload_assets` | `metadata.json` + `upload_preview.md` |
| Finished | `creator.run` | — | renditions bundled into `workspace/exports/<slug>` |

Exit codes: **0** generated + passed + written · **2** quality FAIL / empty
output · **1** a user/environment mistake (shown as a plain message).

---

## 3. The pipeline it drives

The Workflow Engine runs a deterministic 10-stage DAG (independent branches run
in parallel):

```
storyboard → scene_plan → assets → media_intel → editing → timeline → render → export
          ↘ voice → avatar ─────────────────────────────↗
```

| Stage | Engine | Role |
|---|---|---|
| storyboard | Script Engine | prompt → validated storyboard |
| scene_plan | Scene Engine | scenes + timing |
| voice | Voice Engine | per-scene narration |
| avatar | Avatar Engine | deterministic avatar plan |
| assets | Asset Engine | asset registry |
| media_intel | Media Intelligence | content-driven editing patches |
| editing | Editing Engine | apply patches → immutable project |
| timeline | Editing Engine | project → Timeline IR (branding + music) |
| render | Reel Engine | Timeline → master + export profiles |
| export | Reel Engine | validated per-platform renditions |

**Renderers.** `mock` = deterministic, dependency-free proxy video (no GPU, no
FFmpeg, no network) — the default, and what the whole test suite uses. `ffmpeg`
= real `.mp4` files, requires FFmpeg on PATH.

---

## 4. The quality gate

After rendering, the Quality Engine returns a single **PASS/FAIL** from
deterministic checks (video present & playable, audio present & duration-matched,
export resolution matches each profile, duration within limits; avatar/voice/
music are advisory warnings). With `quality.gate: true` (the default) a FAIL
stops the command **before** any upload metadata is written.

---

## 5. Upload-ready output

For a passing reel the Upload Assistant writes, into `workspace/exports/<slug>/`:

- **`metadata.json`** — machine-readable YouTube title/description, Instagram/
  Facebook/LinkedIn captions, hashtags, thumbnail text, suggested filename.
- **`upload_preview.md`** — the same content as copy-paste-ready blocks per
  platform.

`creator.run` then copies the finished renditions next to them, so the entire
upload bundle — video(s) + captions — lives in **one folder**.

---

## 6. Configuration

One documented file, [`creator/config.yaml`](../creator/config.yaml), holds
every option a single user touches, grouped as `generation`, `branding`,
`quality`, and `paths`. It is loaded through the platform's standard layered
loader, so precedence is (lowest → highest):

1. packaged defaults → 2. a `--config <file>` → 3. `AICP__<section>__<key>` env
vars → 4. explicit CLI flags.

The per-engine `defaults.yaml` files remain the advanced layer beneath and are
never required for normal use.

---

## 7. The standardized workspace

Every run writes into one predictable place (created on demand, git-ignored):

```
workspace/
  projects/   full Workflow Engine run per reel
  exports/    finished renditions + upload metadata (your deliverable)
  cache/      reusable intermediate artifacts (safe to delete)
  assets/  voices/  avatars/  music/    your input material
  logs/       per-run logs
```

---

## 8. Errors

Common mistakes fail fast with a plain `Error:`/`Hint:` and **no traceback**:
empty prompt, unknown template, unknown/empty export profile, missing FFmpeg for
the `ffmpeg` renderer, and a missing/unparseable `--config` file are all
validated up front (`creator.errors.CreatorError`). Unexpected errors still
surface fully under `--verbose`.

---

## 9. Determinism & testing

- The same prompt reuses the same `projects/<slug>` folder; runs are
  content-addressed and reproducible.
- `creator/` ships **27 hermetic tests** (mock renderer into `tmp_path`; no GPU,
  FFmpeg, network, or APIs), covering config layering, workspace layout, error
  handling, pre-flight validation, and the full end-to-end happy path.
- The full platform suite (**750+ tests**) stays green; run it with `pytest`.

---

## 10. The complete platform at a glance

| Layer | Package | Responsibility |
|---|---|---|
| **Front door** | `creator/` | single command, config, workspace, errors |
| Orchestration | `workflow_engine/` | deterministic prompt → export DAG |
| Content | `script_engine/`, `scene_engine/` | storyboard + scene plan |
| Media | `voice_engine/`, `avatar_engine/`, `asset_engine/`, `media_intelligence/` | narration, avatar, assets, editing intelligence |
| Composition | `editing_engine/`, `caption_engine/`, `branding_engine/`, `music_engine/` | timeline, captions, branding, music |
| Render | `reel_engine/` | mock + FFmpeg renderers, export profiles |
| Ship | `quality_engine/`, `upload_engine/` | quality gate, upload metadata |
| Storage | `content_library/` | local single-user project + content store |
| Base | `foundation/` | config, logging, caching, paths, exceptions |

---

## 11. Beyond Version 1.0

Intentionally left for later, and explicitly **not** part of v1.0: batch
generation, cloud deployment, automatic publishing, and analytics. The v1.0
architecture — a thin command over composable, deterministic engines — is the
foundation those enhancements would build on.
