# Phase V4.1 — Incremental Expansion: run log

Command: `python -m production.segment_dataset.expansion` (2026-07-15)
Full console output: `D:\AI_CREATOR_DATA\Tanshi\new_voice_dataset\reports\expansion_report.txt`

## STEPS 1-3 — ZIP ingest

| | |
| --- | --- |
| ZIPs found in Downloads | 3 (`New_videos_for_voice_clone-20260714T190834Z-1-00{1,2,3}.zip`) |
| Total size | 6.22 GB |
| Moved (sha256-verified, never overwrite) | 3 → `D:\AI_CREATOR_DATA\Tanshi\new_raw_videos\zips` |
| Extracted (atomic per ZIP, resumable) | 3 → `...\new_raw_videos\extracted` |

## STEP 4 — media scan

104 videos, 0.346 h (20.8 min), 6.21 GB, all `.mov`.

## STEP 5 — EXISTING V4 builder over the new videos only

Output `D:\AI_CREATOR_DATA\Tanshi\new_voice_dataset`; zero crashes; resume-capable.

| | |
| --- | --- |
| Segments evaluated | 201 |
| Accepted | 88 (43.8%) — **0.174 h** at avg SNR **26.09 dB** |
| Rejected | 113 (56.2%) — top reasons: no speech (13), too-short slivers, 3 SNR-masked |

## Pre-merge finding

The V4 production dataset itself contains **2 pre-existing duplicate segment
pairs** — the raw dump has byte-identical source videos
(`IMG_2909 (1).MOV` ≡ `IMG_2909.MOV`, `IMG_1828 2.MOV` ≡ `IMG_1828.MOV`).
Per the "existing dataset unchanged except additions" constraint they stay;
V4.1's validation verifies the MERGE introduces no duplicates (added segments
are sha256-unique and absent from the pre-merge accepted set), and reports
the pre-existing pairs as a note.
