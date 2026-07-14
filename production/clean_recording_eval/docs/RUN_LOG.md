# Phase V3 — Clean Recording Quality Evaluation: run log

Source: new ~30-minute microphone recording (`IMG_1728 2.MOV`, iPhone
HEVC+AAC) from `C:\Users\ACER\Downloads`.

## STEP 1 — move + verify (2026-07-14)

Command: `python -m production.clean_recording_eval.run --recording "IMG_1728 2.MOV"`

| property | value |
| --- | --- |
| Filename | IMG_1728 2.MOV |
| Duration | 1810.1 s (30.2 min) |
| File size | 1247.3 MB |
| Sample rate | 48000 Hz |
| Channels | 2 |
| Audio bitrate | 102 kbps (aac) |
| sha256 | `360825c8dd2caa55cb9fb814056810bc51f8e2c472a765b3b96c0893c1d00b89` |

Moved (copy → re-hash → verify → delete source) to
`D:\AI_CREATOR_DATA\Tanshi\clean_recordings\raw\` — checksum verified, source
removed from Downloads only after the match, existing files never overwritten.

## STEP 2 — Voice Dataset Builder (unchanged thresholds)

The recording ran through the existing builder via the V2 per-file harness
into `D:\AI_CREATOR_DATA\Tanshi\clean_recordings\voice_dataset`
(`accepted/`, `rejected/`, `metadata/dataset.{sqlite,csv,xlsx}` + root copies).

Result: 1 clip total — **rejected: "multiple speakers"** (the f0-IQR
heuristic; see the evaluation report for the caveat). Measured properties of
the clip: quality **excellent**, SNR **33.8 dB**, noise **low**, speech
17.4 min of 30.2 min, loudness −31.3 dBFS, classification *podcast*.
