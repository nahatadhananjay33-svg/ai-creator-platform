# NOTEBOOK_VALIDATION — `notebooks/tanshi_voice_cloning_setup.ipynb`

Setup + validation only. **No training, no benchmarking, no dataset modification.**

## Intended use

1. Open the notebook in Colab → **Runtime → GPU** (optional for setup; required for
   future benchmarks) → **Run All**.
2. The **only line you ever edit** is `MODEL` in the Config cell.

## What the notebook does

| Cell | Purpose |
|---|---|
| Config | `MODEL` (validated against `AVAILABLE_MODELS`), repo URL/**BRANCH**, dataset folder name + optional path override, `VERIFY_MODE` |
| 1. Drive | `drive.mount` + a `remount()` helper (Colab's Drive FUSE drops under load) |
| 2. Repo + deps | clone/fetch/checkout `BRANCH`, `pip install numpy openpyxl tqdm soundfile`, `apt install ffmpeg` if missing, add repo to `sys.path` |
| 3. Dataset | auto-discovers `production_voice_dataset` under `MyDrive` (shallow-first, depth ≤ 4), or uses `DATASET_PATH_OVERRIDE`; prints per-subfolder counts |
| 4. Validation | python ≥3.9 · torch + CUDA/GPU · ffmpeg · repo import · manifest present · **dataset integrity vs the committed sha256 manifest** |
| 5. Ready | pass/fail banner + selected model, dataset path, repo commit |

## Modularity (objective 5)

Future benchmark phases require **only** changing `MODEL` and adding their own
benchmark cell. Nothing else is edited:

```python
MODEL = "f5-tts"     # <- the whole change
```

`AVAILABLE_MODELS` = `xtts-v2, f5-tts, styletts2, chatterbox, openvoice-v2, melotts,
kokoro, indic-parler, dia`. An invalid name fails fast in the Config cell.

## Validation performed (offline, on the dev machine)

| Check | Result |
|---|---|
| Valid `.ipynb` JSON | **PASS** (7 cells) |
| Every code cell compiles (`py_compile`) | **PASS** |
| Pure-Python cells (no `!`/magics) | **PASS** — portable and statically checkable |
| Accelerator metadata | GPU |
| Contains mount / clone / deps / auto-find / integrity-verify | **PASS** |
| Underlying `cloud_setup` module | **6/6 hermetic tests pass** (manifest build, verify, tamper detection) |
| Manifest it verifies against | generated from the **real** dataset: 1081 files, 685.11 MB, structure ✓, metadata ✓ |

## Live Colab validation — PASSED ✅ (2026-07-16)

A real **Run All** on Colab (Tesla T4 runtime) completed with **every check green**:

```
MODEL = xtts-v2
OK  Drive mounted
OK  repo /content/ai-creator-platform @ feat/cloud-setup (4a67508)
OK  ffmpeg: /usr/bin/ffmpeg
OK  dataset: /content/drive/MyDrive/Ai_creator/Voice_AI_Tanshi/production_voice_dataset
      accepted_segments  550 files
      rejected_segments  524 files
      metadata           4 files
OK  python              3.12.13
OK  torch               2.11.0+cu128 cuda=True
OK  gpu                 Tesla T4
OK  ffmpeg              /usr/bin/ffmpeg
OK  repo import         /content/ai-creator-platform
OK  manifest present    .../voice_dataset_manifest.json
OK  dataset integrity   1081/1081 files (missing 0, size-bad 0, hash-bad 0)

     accepted segments : 550
     accepted hours    : 1.327 (speech 1.108)
==========================================================
  ENVIRONMENT READY
==========================================================
```

Every previously-unproven item is now confirmed on real infrastructure:
`drive.mount`, dataset discovery, `git clone` of `BRANCH`, pip/apt installs,
torch+CUDA on GPU, manifest load, and dataset integrity.

Notes from the run:
- The user set `DATASET_PATH_OVERRIDE` to their actual path
  (`MyDrive/Ai_creator/Voice_AI_Tanshi/production_voice_dataset`). Auto-discovery
  would also have found it (depth 3 ≤ 4); the override just skips the search.
- `VERIFY_MODE = "quick"` → presence + exact size for all 1081 files. Use `"full"`
  for a one-time sha256 content proof.
- GPU is present (T4) though not required for setup.

## Known constraints

- `BRANCH` is `feat/cloud-setup` because **no feature branch is merged to `main`**
  and `main` lacks `production/*`. After merging, set `BRANCH = "main"`.
- `VERIFY_MODE = "quick"` by default (presence + size) since full sha256 over the
  Drive FUSE mount for 685 MB is slow. Use `"full"` for a one-time integrity proof.
- GPU is not needed for setup; it is checked and reported, not required.
