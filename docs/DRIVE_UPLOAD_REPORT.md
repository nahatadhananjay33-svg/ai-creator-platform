# DRIVE_UPLOAD_REPORT — Production Voice Dataset

## STATUS: UPLOAD COMPLETE AND VERIFIED ✅ (2026-07-16)

Verified by a live Colab **Run All** of `notebooks/tanshi_voice_cloning_setup.ipynb`,
which mounted the owning Drive account and checked the uploaded copy against the
committed manifest.

| Result | Value |
|---|---|
| Uploaded path | `/content/drive/MyDrive/Ai_creator/Voice_AI_Tanshi/production_voice_dataset` |
| **Files verified** | **1081 / 1081** |
| Missing | **0** |
| Size mismatches (truncated/partial) | **0** |
| Hash mismatches | 0 *(see caveat)* |
| accepted_segments | **550** |
| rejected_segments | **524** |
| metadata files | 4 |
| Accepted hours | **1.327** (speech 1.108) |
| Repo commit verified against | `4a67508` (`feat/cloud-setup`) |

**Caveat — what was actually proven:** the run used `VERIFY_MODE = "quick"`, which
checks **presence + exact byte size** for every file. That conclusively rules out
missing and truncated/partial uploads (the realistic failure modes), but it does
**not** re-hash content, so `hash-bad 0` is trivially true rather than a content
proof. For a one-time sha256 content verification, set `VERIFY_MODE = "full"` and
re-run the validation cell (slower over the Drive mount).

Directory structure was preserved exactly (`accepted_segments/`,
`rejected_segments/`, `metadata/`, `reports/`, `VOICE_DATASET_REPORT.md`).

---

### Historical record (how this was reached)

## Destination (confirmed 2026-07-16 via the Drive API)

| | |
|---|---|
| Folder | **`Voice_AI_Tanshi`** |
| ID | `1a5tjFn1_RsihQ5fQ8zQOBaZHtQ9eHeaF` |
| Owner | `nahatadhananjay33@gmail.com` |
| Created | 2026-07-16 08:58 UTC |
| Current contents | **empty (0 children)** |
| Expected final path | `MyDrive/Voice_AI_Tanshi/production_voice_dataset/` |

## Why the upload has not been performed by the assistant

1. **This machine has no bulk-upload path to Drive** — no Drive desktop client and no
   `rclone`/authenticated Drive CLI is configured here.
2. **The Drive connector cannot write to this folder.** Its metadata reports
   `canAddChildren: false`, and it exposes no bulk binary-upload capability — it
   reads/creates document-type files, it cannot push 1081 binaries / 685 MB.

The upload therefore has to be done from your side (one drag-drop). **I will not
fabricate an upload report.** Once the files are there, verification is automated
(below) and I can confirm it from here.

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

- **Drive web (simplest)** — open
  <https://drive.google.com/drive/folders/1a5tjFn1_RsihQ5fQ8zQOBaZHtQ9eHeaF> and drag
  the **`production_voice_dataset` folder itself** from
  `D:\AI_CREATOR_DATA\Tanshi\` into it. Chrome preserves the subfolder tree. 685 MB is
  a single, uneventful upload.
- **Google Drive for desktop** — copy the folder into your synced Drive path.
- **rclone** (fastest, resumable):
  `rclone copy "D:\AI_CREATOR_DATA\Tanshi\production_voice_dataset" "gdrive:Voice_AI_Tanshi/production_voice_dataset" -P`

Result must be `MyDrive/Voice_AI_Tanshi/production_voice_dataset/{accepted_segments,
rejected_segments,metadata,reports}` — i.e. drop the folder in, don't unpack it.

## Why the assistant cannot verify the upload from the dev machine

Established 2026-07-16 by direct API probing:

| Probe | Result | Meaning |
|---|---|---|
| `get_file_metadata('1a5tj…')` | **works** — returns `Voice_AI_Tanshi`, owner `nahatadhananjay33@gmail.com` | folder reachable **by ID/link only** |
| `search: title = 'Voice_AI_Tanshi'` | **empty** | folder is **not in the connector account's search corpus** |
| `search: parentId = '1a5tj…'` | **empty** | **children cannot be enumerated** — this is *not* evidence of a failed upload |
| `search: sharedWithMe = true` | returns many files | the connector **is** authenticated and search works generally |

The Drive connector is authenticated as a **different Google account** than the folder's
owner (the folder was uploaded from the `/u/2/` account). A link-shared folder owned by
another account is not indexed into this account's search corpus, so its contents cannot
be listed. **An empty listing here therefore proves nothing about the upload.**

Two ways to resolve:

1. **Verify on Colab (recommended, already built).** The setup notebook mounts *your*
   Drive as the owning account and verifies every file against the manifest. Run All and
   read the "dataset integrity" row. Authenticate with the account that owns
   `Voice_AI_Tanshi`.
2. Share `Voice_AI_Tanshi` with the connector's account, after which it can be enumerated
   and verified from here.

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
