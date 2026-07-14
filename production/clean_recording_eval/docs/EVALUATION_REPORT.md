# Phase V3 — Clean Recording Quality Evaluation Report

**Date:** 2026-07-14
**Question:** Is the new 30-minute microphone recording (`IMG_1728 2.MOV`)
suitable as a standalone voice-cloning dataset?
**Modules reused unmodified:** `production.voice_dataset` (builder, original
thresholds), `production.voice_pipeline.glue`, `production.media_acquisition`
(sha256), `production.longform_validation` (per-file harness + stats). No
voice model was trained.

Full raw console output:
`D:\AI_CREATOR_DATA\Tanshi\clean_recordings\voice_dataset\reports\evaluation_report.txt`

---

## STEP 1 — ingest

Moved with verification (sha256 `360825c8…d00b89`) to
`D:\AI_CREATOR_DATA\Tanshi\clean_recordings\raw`. 30.2 min, 1247.3 MB,
48 kHz stereo AAC.

## STEP 2 — Voice Dataset Builder (unchanged thresholds)

Output: `D:\AI_CREATOR_DATA\Tanshi\clean_recordings\voice_dataset`
(`accepted/`, `rejected/`, `metadata/dataset.{sqlite,csv,xlsx}`).

## STEP 3 — statistics

| metric | value |
| --- | --- |
| Total clips | 1 |
| Accepted clips | 0 |
| Rejected clips | 1 |
| Accepted speech minutes | 0.0 |
| Rejected speech minutes | 17.4 |
| Average clip duration | 1810.1 s |
| Average SNR (accepted) | n/a (0 accepted) |
| Average quality (accepted) | n/a |
| Top rejection reason | multiple speakers (1) |

## STEP 4 — inspection (dataset smaller than 20/20 — every clip shown)

| filename | dur (s) | quality | SNR (dB) | verdict |
| --- | --- | --- | --- | --- |
| IMG_1728 2.MOV | 1810.1 | excellent | 33.8 | rejected: multiple speakers |

Underlying measurements of that one clip: noise **low**, loudness
−31.3 dBFS, speech 1042 s / 1810 s (57.6%), no music bed, classified
*podcast* (a >30-min single file).

## STEP 5 — comparison

| metric | Raw phone recordings | Clean mic recording |
| --- | --- | --- |
| Acceptance rate (%) | 4.0 | 0.0 |
| Speech hours (accepted) | 0.075 | 0.000 |
| Average SNR (dB, accepted) | 28.23 | n/a — clip itself measured 33.8 |
| Average clip quality (0–3) | 2.71 | n/a — clip itself rated excellent (3) |
| Average speech duration (s) | 11.3 | n/a |

## STEP 6 — Voice Cloning Readiness Score (deterministic, from measured values)

| component | score /100 |
| --- | --- |
| Recording quality (SNR 33.8 dB) | 100.0 |
| Noise level (floor: low) | 100.0 |
| Speech consistency (57.6% speech) | 58.6 |
| Single-speaker confidence (heuristic flagged) | 25.0 |
| Pronunciation consistency (proxy: loudness −31.3 dBFS, quieter than ideal) | 45.9 |
| Microphone quality (48 kHz) | 100.0 |
| Naturalness (proxy: no music, human pausing) | 100.0 |
| **OVERALL** | **77.1** |

## STEP 7 — final recommendation (as measured, thresholds unchanged)

> **C) Record additional clean speech before training.**

Supporting measurements:

- Under the builder's unchanged thresholds the dataset contains **zero
  accepted speech** (0.000 h vs the 1.0 h sufficiency band and the 0.25 h
  usable band) — **A and B are ruled out on measured acceptance alone.**
- The single clip was rejected solely by the **multi-speaker f0-IQR
  heuristic** — the same known over-rejection flagged in Phases V1 and V2,
  now tripping on 30 continuous minutes of one speaker's natural pitch
  variation. No other gate failed.
- Everything actually acoustic about the recording is the **best of any
  source measured so far**: SNR 33.8 dB (raw-video accepted average: 28.2;
  YouTube long-form: 20.5), noise floor *low*, quality *excellent*, 48 kHz —
  readiness 77.1/100 with the heuristic penalty included.

### Interpretation and next actions (outside V3 scope)

1. **The microphone and room are validated.** Recording quality is not the
   problem; volume of *accepted* speech is, and the sole blocker is a
   documented heuristic limitation, not audible quality.
2. Recording **more clean speech in shorter takes** (e.g. 3–10 min segments)
   serves recommendation C directly and also reduces the per-file f0 spread
   the heuristic reacts to.
3. Independently, reviewing the multi-speaker heuristic for long solo
   recordings (open issue since V1) would likely convert this same file into
   ~17 speech-minutes of *excellent* accepted data — but that is a threshold
   change and deliberately out of V3 scope.
