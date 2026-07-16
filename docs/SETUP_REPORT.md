# SETUP_REPORT — Production Voice Cloning · Cloud Setup

Phase: cloud setup automation. **No training, no benchmarking, no dataset changes.**
Generated from a real run on 2026-07-15.

## 1. Git repository state — PASS

| Check | Result |
|---|---|
| Working tree | **clean** (no uncommitted changes) |
| Branch at audit | `feat/avatar-dataset-evaluator` @ `a99194c` |
| Sync with origin | **0 ahead / 0 behind** |
| All local branches | **10/10 synced with GitHub** (`main`, `feat/voice-dataset-builder`, `feat/media-acquisition`, `feat/colab-voice-pipeline`, `feat/longform-voice-validation`, `feat/clean-recording-eval`, `feat/segment-dataset`, `feat/segment-dataset-expansion`, `feat/avatar-dataset-evaluator`, `infra/colab-resilience`) |
| Pushed this phase | `feat/cloud-setup` (new) |

Nothing needed pushing — the repo was already fully synced.

> **Note (reproducibility caveat):** none of the feature branches are merged into
> `main`; `main` contains the original engines but no `production/*` modules. The
> setup notebook therefore clones an explicit `BRANCH` (`feat/cloud-setup`). If you
> merge the branches, update `BRANCH = "main"` in the notebook's Config cell.

## 2. Production dataset validation — PASS

Source (read-only): `D:\AI_CREATOR_DATA\Tanshi\production_voice_dataset`

**Structure** — all expected directories and metadata present:
`accepted_segments/`, `rejected_segments/`, `metadata/`, `reports/`,
`metadata/dataset.{sqlite,csv,xlsx}`.

**Metadata cross-check against disk:**

| Metric | Value |
|---|---|
| sqlite rows | 1074 |
| accepted (metadata) | **550** |
| accepted (on disk) | **550** ✓ match |
| rejected (on disk) | 524 |
| metadata rows missing a wav | **0** |
| wavs with no metadata row | **0** |
| Accepted duration | **1.327 h** |
| Accepted speech | **1.108 h** |
| Quality mix | 349 excellent · 155 good · 45 fair · 1 poor |

**Checksums / manifest:** sha256 computed for **all 1081 files** (**685.11 MB**).

- `production/cloud_setup/manifest/voice_dataset_manifest.json`
- `production/cloud_setup/manifest/voice_dataset_manifest.csv`

Both are committed, so the notebook can verify any uploaded copy after cloning.

> The dataset's own `VOICE_DATASET_REPORT.md` still shows Phase-V4 numbers
> (462 accepted); the current V4.1 dataset is 550 accepted. The report is stale but
> the dataset and its metadata are internally consistent — left untouched per the
> "do not modify the dataset" constraint.

## 3. Tooling added (read-only over the dataset)

```
production/cloud_setup/
  manifest.py        validate_structure · validate_metadata · sha256 manifest · verify_against
  prepare.py         CLI: validate + checksum -> manifest        (python -m production.cloud_setup.prepare)
  verify_upload.py   CLI: verify an uploaded copy vs manifest    (--target <dir> [--quick])
  manifest/          committed manifest (JSON + CSV)
  tests/             6 hermetic tests
```

## 4. Colab notebook

`notebooks/tanshi_voice_cloning_setup.ipynb` — see `NOTEBOOK_VALIDATION.md`.

## 5. Status

| Objective | Status |
|---|---|
| 1. Git clean + synced | **DONE** |
| 2. Validate + checksum + manifest | **DONE** |
| 3. Drive upload + verify | **BLOCKED** — awaiting the Drive folder link (see `DRIVE_UPLOAD_REPORT.md`) |
| 4. Production Colab notebook | **DONE** |
| 5. Modular (model-name only) | **DONE** |
| 6. Reports | **DONE** |
