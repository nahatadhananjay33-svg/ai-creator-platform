# VOICE_DATASET_REPORT — Phase V4 production dataset

## Source contribution

| source | files | segments | accepted | accepted min | avg SNR (dB) |
| --- | --- | --- | --- | --- | --- |
| clean_mic | 1 | 166 | 114 | 22.1 | 36.3 |
| raw_phone | 536 | 694 | 290 | 32.7 | 31.3 |
| youtube | 8 | 126 | 58 | 14.4 | 22.1 |

## Dataset totals

- Source recordings: 545
- Segments: 986 — **accepted 462
  (46.9%)**, rejected 524
  (53.1%)
- Accepted hours: **1.153** (speech
  0.961); rejected hours: 0.693
- Average SNR (accepted): **31.39 dB**
- Average loudness (accepted): -23.00 dBFS
- Average segment duration: 9.0 s
- Background noise (accepted segments): avg floor
  -55.8 dBFS; distribution high: 32, low: 227, moderate: 203

## Top rejection reasons

- no speech detected (68)
- segment too short (2.0s speech < 3s) (15)
- segment too short (2.1s speech < 3s) (14)
- segment too short (0.8s speech < 3s) (14)
- segment too short (2.2s speech < 3s) (14)
- segment too short (1.6s speech < 3s) (13)
- segment too short (2.9s speech < 3s) (13)
- segment too short (2.6s speech < 3s) (13)

## Inspection verification (seeded random sample)

- Accepted sample: duration-in-band 50/50,
  files exist 50/50, speech-ratio ok
  50/50
- Rejected sample: files exist 50/50

## Estimated production readiness

**YES - the dataset is sufficient for production voice cloning.**

1.15 h of accepted segments at avg SNR 31.4 dB meets the >= 1.0 h / >= 18 dB target.

No additional recording required.

---

## Context vs the whole-file phases (V1-V3)

| | whole-file (V1+V2+V3 combined) | segment-level (V4) |
| --- | --- | --- |
| Accepted usable speech | ≈ 0.148 h | **1.153 h (~7.8×)** |
| Clean mic recording | 0 min (rejected whole) | 22.1 min at SNR 36.3 dB |
| Speaker policy | whole-file f0-IQR bool (55 Hz) | per-segment confidence, reject only ≥ 0.8 |
| Noise policy | quality-rank penalties | reject only when SNR shows masking (< 18 dB) |

Why it worked: 5-20 s segments bound natural pitch spread, so the
multi-speaker signal became meaningful (accepted-sample confidences are
mostly ≤ 0.3, while genuinely overlapping clips still reject at ≥ 0.8);
per-segment SNR against the source recording's noise floor keeps clear
speech in noisy rooms while dropping genuinely masked passages; and the
"too short"/"no speech" rejections now discard only slivers, not recordings.

Dataset location: `D:\AI_CREATOR_DATA\Tanshi\production_voice_dataset`
(`accepted_segments/` 462 WAVs, `rejected_segments/`, `metadata/dataset.{sqlite,csv,xlsx}`).
No voice model was trained (out of V4 scope).
