# Phase V4 — Intelligent Production Voice Dataset Builder: run log

Command: `python -m production.segment_dataset.run` (2026-07-15)
Full console output: `D:\AI_CREATOR_DATA\Tanshi\production_voice_dataset\reports\run_output.txt`

## Sources

| kind | root | files |
| --- | --- | --- |
| clean_mic | `D:\AI_CREATOR_DATA\Tanshi\clean_recordings\raw` | 1 |
| raw_phone | `D:\AI_CREATOR_DATA\Tanshi\raw_videos` | 594 |
| youtube | `D:\AI_CREATOR_DATA\Tanshi\youtube_longform` | 8 |
| instagram | `production_assets\tanshi\media\instagram` | 0 (none downloaded — no credentials) |

603 files processed in a single resumable pass. 29 raw phone videos failed
extraction with "Output file does not contain any stream" — they have **no
audio track** (the same 29 that failed in Phase V1); isolated per-file and
listed in `reports/crashed_files.json`. 29 more produced zero speech segments
(silent audio). 545 recordings contributed segments.

## Result (STEP 8)

| | |
| --- | --- |
| Segments evaluated | 986 |
| Accepted | **462 (46.9%) — 1.153 h** (0.961 h measured speech) |
| Rejected | 524 (53.1%) — 0.693 h |
| Avg SNR (accepted) | **31.39 dB** |
| Avg loudness | −23.0 dBFS |
| Avg segment duration | 9.0 s |
| Noise floors (accepted) | −55.8 dBFS avg; low 227 / moderate 203 / high 32 |

Per source: clean_mic 114 segments / 22.1 min (avg SNR 36.3) — the file
Phase V3 rejected outright; raw_phone 290 / 32.7 min (31.3 dB); youtube
58 / 14.4 min (22.1 dB).

Inspection (STEP 9, seed 20260714): accepted sample 50/50 duration-in-band,
50/50 files exist, 50/50 speech-ratio ≥ 0.5.

**Verdict (STEP 11): YES — 1.15 h ≥ 1.0 h target at 31.4 dB ≥ 18 dB.**
Compared with the whole-file phases (V1+V2+V3 combined ≈ 0.148 h accepted),
segment-level extraction recovered **~7.8× more usable speech**.
