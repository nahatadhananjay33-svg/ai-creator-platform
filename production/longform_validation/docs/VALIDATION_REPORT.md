# Phase V2 — Long-form Voice Dataset Validation Report

**Date:** 2026-07-14
**Question:** Are the long-form YouTube videos from `@realestatewithtanshi`
suitable for production voice cloning?
**Modules reused unmodified:** `production.media_acquisition` (download engine
+ YouTube provider), `production.voice_dataset` (builder, original thresholds),
`production.voice_pipeline.glue` (folder pipeline). No voice model was trained.

Full raw console output: `D:\AI_CREATOR_DATA\Tanshi\youtube_voice_dataset\reports\validation_report.txt`

---

## STEP 1 — download

8 long-form videos discovered on the Videos tab (Shorts, Instagram, Reels,
community posts excluded). 8/8 downloaded to
`D:\AI_CREATOR_DATA\Tanshi\youtube_longform` (941.6 MB, 0.459 h), 0 failed,
sha256 checksums verified 8/8. Re-runs skip verified files and resume
partial downloads.

## STEPS 2+3 — extraction + dataset build

All 8 videos ran through the existing Voice Dataset Builder (unchanged
thresholds) into `D:\AI_CREATOR_DATA\Tanshi\youtube_voice_dataset`
(`accepted/`, `rejected/`, `metadata/dataset.{sqlite,csv,xlsx}`).

## STEP 4 — statistics (YouTube long-form dataset)

| metric | value |
| --- | --- |
| Total videos | 8 |
| Total audio duration | 0.458 h |
| Accepted clips | 1 |
| Rejected clips | 7 |
| Accepted speech hours | 0.073 |
| Rejected speech hours | 0.341 |
| Average quality (accepted) | good |

Top rejection reasons: multiple speakers (4); SNR below threshold (3:
7.7 dB poor, 17.1 dB fair, 18.9 dB fair).

## STEP 5 — random inspection (seeded; every clip shown — dataset smaller than 30/30)

**Accepted (1):**

| filename | dur (s) | quality | reason |
| --- | --- | --- | --- |
| Or7HpGw9DIU.mp4 | 348.5 | good | clean speech - quality good - snr 20.5 dB |

**Rejected (7):**

| filename | dur (s) | quality | reason |
| --- | --- | --- | --- |
| 40IK-ssaEn8.mp4 | 189.5 | poor | multiple speakers |
| _G6O3rO_NnU.mp4 | 128.9 | poor | multiple speakers |
| v5X9L_0-6-s.mp4 | 190.0 | poor | quality poor below threshold (snr 7.7 dB) |
| lwNvDtT3Vrs.mp4 | 183.6 | good | multiple speakers |
| hyO9meJVTv0.mp4 | 242.5 | fair | quality fair below threshold (snr 18.9 dB) |
| VFjefygpm0E.mp4 | 173.6 | poor | multiple speakers |
| dLmwd_Iyzaw.mp4 | 192.6 | fair | quality fair below threshold (snr 17.1 dB) |

## STEP 6 — comparison

| metric | Raw Video Dataset | YouTube Long-form |
| --- | --- | --- |
| Accepted clips | 24 | 1 |
| Accepted speech hours | 0.075 | 0.073 |
| Average SNR (dB) | 28.23 | 20.47 |
| Average clip duration (s) | 14.3 | 348.5 |
| Quality score (0–3) | 2.71 | 2.00 |

Voice-cloning suitability (assessment bands: sufficient ≥ 1.00 h accepted
speech, usable ≥ 0.25 h, min avg SNR 18 dB, min quality rank good):

- Raw videos: **high quality but too little speech** (0.075 h)
- YouTube long-form: **high quality but too little speech** (0.073 h)

## STEP 7 — final recommendation

> **B) Use YouTube videos together with the clean recordings.**

Supporting measurements:

- YouTube long-form contributes 0.073 h of accepted speech at avg SNR
  20.5 dB / quality *good* — it passes the quality bar but is far below the
  1.0 h sufficiency band on its own, so **A is ruled out**.
- The clean recordings alone hold only 0.075 h of accepted speech; discarding
  a quality-passing source that nearly doubles usable speech (0.073 h → 0.148 h
  combined) is not justified, so **C is ruled out**.
- Combined, both sources still total ≈ 0.148 h — well short of the ~1 h
  typically wanted for production cloning. **Neither source, nor both
  together, currently reaches production volume.**

### Caveats / next actions (outside V2 scope)

- 4 of 7 YouTube rejections are "multiple speakers" — the known heuristic
  (f0-IQR spread) that over-rejects solo speech with varied intonation; one of
  those clips otherwise measured *good* quality (lwNvDtT3Vrs, SNR OK). A review
  of that heuristic (open issue from Phase V1) could recover up to ~0.2 h more.
- The accepted YouTube clip averages 348 s vs 14 s for raw clips — long-form
  video is a much denser speech source per accepted item; more long-form
  uploads would raise volume fastest.
