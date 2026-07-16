# DRIVE_UPLOAD_REPORT — Production Voice Dataset

**Status: UPLOAD NOT PERFORMED — blocked.** Everything needed to upload and verify
is prepared; the upload itself is pending two things (below).

## Why the upload has not happened

1. **No Drive folder link provided.** The task says *"I will provide a Google Drive
   folder link"* — it hasn't been supplied yet, so there is no destination.
2. **This machine cannot bulk-upload to Drive.** There is no Drive desktop client,
   `rclone`, or authenticated Drive CLI configured here, and the available Drive
   connector has no bulk binary-upload capability (it can create/read files, not
   push 1081 binaries / 685 MB). I will not fake an upload report.

## What to upload

| | |
|---|---|
| Source | `D:\AI_CREATOR_DATA\Tanshi\production_voice_dataset` |
| Files | **1081** |
| Size | **685.11 MB** |
| Structure | `accepted_segments/` (550 wav) · `rejected_segments/` (524 wav) · `metadata/` (dataset.sqlite/csv/xlsx, processed_sources.json) · `reports/` · `VOICE_DATASET_REPORT.md` |

**Preserve the directory structure exactly** — upload the `production_voice_dataset`
folder itself (not its contents loose), so the tree under it is unchanged. The
notebook auto-discovers it by folder name anywhere under `MyDrive`.

## How to upload (choose one)

- **Drive web** — drag the `production_voice_dataset` folder into the target folder.
  Chrome preserves subfolders. 685 MB is a single, uneventful upload.
- **Google Drive for desktop** — copy the folder into your synced Drive path.
- **rclone** (fastest, resumable):
  `rclone copy "D:\AI_CREATOR_DATA\Tanshi\production_voice_dataset" "gdrive:<target>/production_voice_dataset" -P`

## Verification (this is the important part — automated)

Every file's sha256 is committed in
`production/cloud_setup/manifest/voice_dataset_manifest.json`. After uploading,
verification is one command — **no trust required**:

**On Colab** (the setup notebook does this automatically in its validation cell):

```python
from production.cloud_setup.manifest import load_manifest, verify_against
man = load_manifest("production/cloud_setup/manifest/voice_dataset_manifest.json")
verify_against(man, "/content/drive/MyDrive/<target>/production_voice_dataset", quick=False)
```

**Or from a shell:**

```bash
python -m production.cloud_setup.verify_upload \
  --target "/content/drive/MyDrive/<target>/production_voice_dataset" \
  --report docs/upload_verification.json          # add --quick for presence+size only
```

Result semantics:

| Field | Meaning |
|---|---|
| `verified` | files matching the manifest exactly |
| `missing_count` | files that never arrived |
| `size_mismatch_count` | truncated / partial uploads |
| `hash_mismatch_count` | corrupted content (full mode only) |
| `ok` | **true only if all 1081 files match** |

`--quick` checks presence + size (fast over the Drive FUSE mount); the default full
mode re-hashes every file and will catch silent corruption.

## To finish this objective

Send me the **Drive folder link** (or upload it yourself using the steps above and
tell me the path). Then I will run the verification and replace this section with a
real, per-file upload report — pass/fail counts and any bad files named.
