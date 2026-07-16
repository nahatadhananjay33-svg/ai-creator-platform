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

## NOT yet validated — requires a live Colab run

I cannot execute Colab from this machine, so these are unproven until you Run All:

- `drive.mount` / auto-discovery against your actual Drive layout
- `git clone` of `BRANCH` on Colab
- `apt`/`pip` installs on the Colab image
- torch/CUDA detection on a GPU runtime
- **the dataset integrity check will FAIL until the dataset is uploaded** (see
  `DRIVE_UPLOAD_REPORT.md`) — that is expected, not a notebook defect

**Please Run All once and paste the output**; I'll confirm each check and fix anything
that misbehaves.

## Known constraints

- `BRANCH` is `feat/cloud-setup` because **no feature branch is merged to `main`**
  and `main` lacks `production/*`. After merging, set `BRANCH = "main"`.
- `VERIFY_MODE = "quick"` by default (presence + size) since full sha256 over the
  Drive FUSE mount for 685 MB is slow. Use `"full"` for a one-time integrity proof.
- GPU is not needed for setup; it is checked and reported, not required.
