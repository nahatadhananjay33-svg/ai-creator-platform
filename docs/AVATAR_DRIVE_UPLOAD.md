# AVATAR_DRIVE_UPLOAD — Production Avatar Dataset → Google Drive

**Status: UPLOAD NOT PERFORMED — blocked on the destination.** The task says the
Google Drive folder "will be provided"; no folder link has been supplied yet, and
this machine has no bulk-upload path to Drive (no Drive for Desktop, no `rclone`,
no authenticated Drive CLI; the available Drive connector cannot push 16.7 GB of
binaries). Everything needed to upload and verify is prepared below.

## What to upload

| | |
|---|---|
| Source | `D:\AI_CREATOR_DATA\Tanshi\avatar_dataset` |
| Upload scope | **1133 files / 16.7 GB** — `accepted/` (461 clips), `thumbnails/`, `reports/`, `dataset.{sqlite,csv,xlsx}` |
| Excluded (evaluation byproducts, ~9.4 GB) | `rejected/`, `cropped_src/`, `_recovery/` — not needed for training; add them only if you want a full archive |
| Dataset state | 461 accepted clips · 61.0 min · readiness 95/100 · provenance 394 original + 67 incremental |

**Preserve the directory structure** — upload the `avatar_dataset` folder itself
(not its contents loose). The training notebook auto-discovers it by folder name
anywhere under `MyDrive` (or set `DATASET_PATH` explicitly in its CONFIG cell).

## How to upload (choose one)

- **Drive web** — drag the `avatar_dataset` folder into the target Drive folder in
  Chrome (subfolders are preserved). At 16.7 GB expect roughly 1–3 h on a typical
  uplink; the browser must stay open.
- **Google Drive for Desktop** — install, then copy the folder into the synced
  drive; sync continues in the background and survives reboots. (Recommended for
  a 16.7 GB transfer.)
- **rclone** (fastest, resumable, verifiable):
  `rclone copy "D:\AI_CREATOR_DATA\Tanshi\avatar_dataset" "gdrive:<target>/avatar_dataset" -P --transfers 4`

Note: free-tier Drive is 15 GB — the training scope alone is 16.7 GB, so the
account needs ≥ 20 GB free (Google One or workspace storage).

## Verification (automated — no trust required)

Every file's sha256 is committed in
`production/cloud_setup/manifest/avatar_dataset_manifest.json` (+ `.csv`).

- **In Colab:** `notebooks/tanshi_avatar_training.ipynb` cell 5 verifies the
  mounted copy automatically — quick (presence+size) by default, set
  `FULL_HASH_VERIFY = True` to re-hash all 16.7 GB.
- **From any shell with the repo:**

```bash
python -m production.cloud_setup.verify_upload \
  --manifest production/cloud_setup/manifest/avatar_dataset_manifest.json \
  --target "/content/drive/MyDrive/<target>/avatar_dataset" \
  --report docs/avatar_upload_verification.json        # add --quick for fast mode
```

`ok: true` requires all 1133 files present with matching sizes (and hashes in
full mode).

## Regenerating the manifest

Only if the dataset legitimately changes in a future phase (it is frozen now):
`python -m production.cloud_setup.prepare_avatar` (add `--include-all` to cover
the excluded byproduct folders).

## To finish the upload objective

Provide the Drive folder link (or upload with the steps above and share the
path), and the verification can be run to produce a real per-file report.
