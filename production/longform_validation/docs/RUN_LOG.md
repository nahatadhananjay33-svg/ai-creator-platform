# Phase V2 — Long-form Voice Dataset Validation: run log

Channel: `https://www.youtube.com/@realestatewithtanshi` (Videos tab only —
Shorts, Instagram, Reels, and community posts excluded by the long-form
provider filter).

## STEP 1 — download (2026-07-14)

Command: `python -m production.longform_validation.run --skip-build`

| metric | value |
| --- | --- |
| Long-form discovered | 8 |
| Downloaded | 8 |
| Skipped (already present) | 0 |
| Failed | 0 |
| Hours on disk | 0.459 |
| Checksums verified | 8/8 OK |

Destination: `D:\AI_CREATOR_DATA\Tanshi\youtube_longform`
(941.6 MB across 8 mp4 files; `media.sqlite` / `media.csv` / `media.xlsx` /
`download.log` written alongside.)

Re-runs are incremental: already-verified files are skipped, partial
downloads resume via yt-dlp `continuedl`, and every file is re-hashable
against the recorded sha256 (`verify_checksums`).

## STEPS 2+3 — audio extraction + voice dataset build (2026-07-14)

Command: `python -m production.longform_validation.run`
(STEP 1 re-ran incrementally first: 8 skipped, checksums re-verified 8/8 OK.)

All 8 videos processed one-per-call through the existing Voice Dataset
Builder via `voice_pipeline.glue.run_pipeline` — no crashes, no extract
failures. Output: `D:\AI_CREATOR_DATA\Tanshi\youtube_voice_dataset`

| | |
| --- | --- |
| Accepted clips | 1 (`accepted/Or7HpGw9DIU.wav`, 63.8 MB) |
| Rejected clips | 7 |
| Metadata | `metadata/dataset.{sqlite,csv,xlsx}` (+ copies at the output root) |
| Reports | `reports/validation_report.txt`, `summary.json` |

Top rejection reasons: multiple speakers (4), SNR below threshold (3).
