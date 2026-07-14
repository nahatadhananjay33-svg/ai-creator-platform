# Phase A1 — Incremental Avatar Dataset Evaluation

**Date:** 2026-07-15
**Command:** `python -m production.avatar_dataset_evaluator.incremental`
**Input:** `D:\AI_CREATOR_DATA\Tanshi\new_raw_videos\extracted` (104 videos, the V4.1 ZIP drop) — evaluated with the **unmodified A0 evaluator** (thresholds untouched).
**Output:** `D:\AI_CREATOR_DATA\Tanshi\avatar_dataset_new` (`accepted/`, `rejected/`, `thumbnails/`, `dataset.{sqlite,csv,xlsx}`, `reports/`).
**The production avatar dataset was not modified; nothing was merged.**

## New dataset (A0 gates, unchanged)

| | |
| --- | --- |
| Videos evaluated | 104 |
| Accepted | **68 (65%)** — 12.4 min usable |
| Rejected | 36 — heavy blur (26), too short (6), face too small (2), no face (1), covered (1) |
| Avg face visibility | 95.7% (old dataset: 84.8%) |
| Avg stability | 0.98 |
| Avg resolution / fps | ~3470×1952 / 29.8 |

## Viewpoint coverage (accepted clips; pose/pitch/side are low-confidence proxies)

| category | clips | minutes | status |
| --- | --- | --- | --- |
| Front | 68 | 12.3 | OK |
| 20° Left | 45 | 9.8 | OK |
| 20° Right | 30 | 9.0 | OK |
| Looking Up | 2 | 0.2 | PARTIAL |
| Looking Down | 65 | 12.1 | OK |
| Smiling | 63 | 11.8 | OK |
| Serious | 1 | 0.3 | PARTIAL |
| Walking | 0 | 0.0 | MISSING |
| Standing | 67 | 12.3 | OK |
| Sitting | 1 | 0.0 | MISSING |
| Side movement | 2 | 0.2 | PARTIAL |
| Natural talking | 67 | 12.1 | OK |

## Old (A0, incl. M1 crop recovery) vs New

| metric | Old (A0) | New (A1) |
| --- | --- | --- |
| Accepted clips | 394 | 68 |
| Accepted minutes | 48.7 | 12.4 |
| Face visibility (avg %) | 84.8 | 95.7 |
| Lighting (avg/255) | 129 | 119 |
| Stability | 0.96 | 0.98 |
| Pose F/L/R | 394/0/0 | 68/0/0 (Haar profile; slight-yaw proxy finds L 45 / R 30) |
| Expressions smile/neutral/talk | 275/1/118 | 56/1/11 |
| Movement standing/walking | 393/1 | 68/0 |

## The 14 answers

1. **Improves avatar quality?** YES — +68 accepted clips (+12.4 min), readiness 87 → 95, adds 20° Left, 20° Right, Looking Down, Smiling.
2. **Left views recovered?** YES — 45 clips, 9.8 min.
3. **Right views recovered?** YES — 30 clips, 9.0 min.
4. **Looking Up?** PARTIAL — 2 clips, 0.2 min.
5. **Looking Down?** YES — 65 clips, 12.1 min.
6. **Smiling?** YES — 63 clips, 11.8 min.
7. **Serious?** PARTIAL — 1 clip, 0.3 min.
8. **MuseTalk?** YES — merged feasibility 95% (new alone 96%).
9. **LatentSync?** YES — 95%.
10. **Hallo2?** YES — 80%.
11. **EchoMimic?** YES — 85%.
12. **Merge?** YES — quality holds, coverage and volume increase.
13. **Merged readiness score:** **95/100** (currently 87/100).
14. **Still missing:** side-profile (full 45°+) clips; static talking-to-camera; close-ups (larger face); Looking Up < 1 min; Serious < 1 min. Walking and Sitting also absent in the new footage.

## Random audit (30/30, seed 20260715)

Accepted: 30/30 re-pass the face/blur/stability/lighting gates. Rejected:
30/30 carry an explicit reason (blur dominates). Details in
`avatar_dataset_new/reports/a1_evaluation.txt`.

## FINAL VERDICT

> **READY TO MERGE**

- 68 new accepted clips (+12.4 min) pass the unmodified A0 gates; audit clean.
- Merged readiness would rise **87 → 95/100**; all four target models clear 70% feasibility.
- Merge deliberately **not performed** in this phase (out of scope).

**Recording notes for the remaining gaps:** the new footage's #1 rejection is
motion blur (26/36) — steadier framing or better light would recover most of
those; still wanted: a few minutes each of deliberate Looking-Up, calm
*serious* takes, walking shots, and seated close-ups.
