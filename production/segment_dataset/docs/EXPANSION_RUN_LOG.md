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

## STEP 6 — merge (SHA256-deduped)

All 88 new accepted segments were unique against the 462 existing accepted
WAVs — **88 added, 0 duplicates skipped**. Only accepted segments merged;
the new run's rejected segments remain in `new_voice_dataset` for audit.

## STEP 7 — comparison

| metric | Old (V4) | New (V4.1) | Merged |
| --- | --- | --- | --- |
| Accepted clips | 462 | 88 | **550** |
| Accepted hours | 1.153 | 0.174 | **1.327** |
| Average SNR (dB) | 31.39 | 26.09 | 30.54 |
| Average loudness (dBFS) | −23.00 | −17.68 | −22.15 |
| Average duration (s) | 9.0 | 7.1 | 8.7 |
| Recovery (accepted %) | 46.9 | 43.8 | 51.2 |

Quality (merged): excellent 349, good 155, fair 45, poor 1.
Net increase: **+0.174 h (+88 clips)**.

## STEP 8 — audit (seed 20260714)

30 newly accepted: duration-in-band 30/30, files exist 30/30,
speech-ratio ≥ 0.5 30/30. 30 newly rejected: files exist 30/30, reasons
spot-checked (no-speech slivers, too-short, SNR-masked).

## STEP 9 — final production summary

**1.153 h existing + 0.174 h new = 1.327 h final** — 611 recordings,
1074 segments evaluated, 550 accepted at avg SNR 30.54 dB, avg quality
excellent-leaning (349/550 excellent).
**YES — sufficient for production voice cloning** (≥ 1.0 h @ ≥ 18 dB).

## Validation

All 8 checks passed: existing dataset unchanged except additions; merge
introduced no sha256 duplicates; ids sequential; sqlite/csv/xlsx row-
consistent; all accepted files exist; random audit passed.

## Pre-merge finding

The V4 production dataset itself contains **2 pre-existing duplicate segment
pairs** — the raw dump has byte-identical source videos
(`IMG_2909 (1).MOV` ≡ `IMG_2909.MOV`, `IMG_1828 2.MOV` ≡ `IMG_1828.MOV`).
Per the "existing dataset unchanged except additions" constraint they stay;
V4.1's validation verifies the MERGE introduces no duplicates (added segments
are sha256-unique and absent from the pre-merge accepted set), and reports
the pre-existing pairs as a note.
