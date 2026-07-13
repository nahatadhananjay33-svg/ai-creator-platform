# Voice Dataset Builder

Builds the highest-quality **speech dataset** from your *own* exported Instagram/YouTube
media — fully **local, deterministic, no cloud, no ML, no GPU**. It ingests media, extracts
audio, measures it, classifies it, scores quality, and accepts/rejects each clip into a
clean corpus with a `sqlite`/`csv`/`xlsx` index.

> Phase P1 scope: **dataset building only**. No voice cloning.

## Authorized use

Operate only on media you have legitimately exported or downloaded, or are otherwise
authorized to process (this is your own content). The builder reads **local files**; it does
**not** scrape platforms or bypass any platform protection or terms. Media acquisition is
abstracted behind a provider interface so a future importer (e.g. for a platform's official
data export) can be added — but only local media is processed here.

## Folder layout

```
production_assets/
  tanshi/
    voice/
      raw/
        instagram/     <- drop your exported Instagram media here
        youtube/       <- drop your exported YouTube media here
      extracted/       <- WAVs produced from each source
      accepted/        <- clips that passed
      rejected/        <- clips that failed (with a reason in the dataset)
      metadata/        <- dataset.sqlite / dataset.csv / dataset.xlsx
```

The builder creates this tree automatically. Supported inputs: WAV (passthrough, original
sample rate kept) and — when `ffmpeg` is installed — common audio/video (`.mp4 .mov .mkv
.webm .m4a .mp3 .aac .flac .ogg …`). WAV-only runs need no external binaries.

## Quickstart

```bash
# 1. put your exported media into raw/instagram and raw/youtube
# 2. run the builder
python -m production.voice_dataset.build
```

Options: `--base DIR` (default `./production_assets` or `$VOICE_DATASET_BASE`) and
`--creator NAME` (default `tanshi`).

Example run:

```
============================================
  Voice Dataset Summary
============================================
  Total videos    : 42
  Accepted        : 27
  Rejected        : 15
  Speech hours    : 3.812
  Average quality : good
============================================
```

## Pipeline

| Step | What it does | Notes |
|---|---|---|
| 1 Ingest | Discover media in `raw/instagram` + `raw/youtube` | deterministic sorted order; provider-based |
| 2 Extract | Produce a WAV per source | WAV passthrough keeps sample rate; else `ffmpeg -vn pcm_s16le` |
| 3 Metadata | duration, sample rate, channels, bitrate, silence %, speech duration, loudness, filename, source, platform | **measured** from decoded PCM |
| 4 Classify | talking_head / interview / podcast / long_form / short_reel / carousel_video / meme / music_only / unknown | heuristic decision tree over duration, platform, speech ratio, music, speakers |
| 5 Detect | speech / no-speech, multiple speakers, background music, noise estimate | energy-VAD + autocorrelation-pitch + gap-energy heuristics |
| 6 Score | excellent / good / fair / poor | SNR band minus penalties (loudness, silence, noise, music) |
| 7 Decide | accept / reject + reason | targets **clean single-speaker speech** |

### How measurements work (no ML)

- **Silence / speech**: per-frame RMS in dBFS; frames below `silence_floor_dbfs` (−40) are
  silence. Speech runs are smoothed (bridge <300 ms gaps, drop <150 ms blips).
- **Loudness**: integrated RMS in dBFS.
- **Noise floor / SNR**: 10th-percentile frame level is the noise floor; SNR = median speech
  level − noise floor.
- **Background music** *(heuristic)*: a large fraction of non-speech frames carrying sustained
  energy well above the noise floor suggests a music bed.
- **Multiple speakers** *(heuristic)*: autocorrelation f0 is estimated across voiced frames; a
  wide pitch spread (IQR ≥ `multi_speaker_f0_iqr_hz`) flags possible multiple speakers.

These heuristics are estimates, not classifier outputs — deterministic and reproducible, but
imperfect. Tune thresholds in [`config.py`](../production/voice_dataset/config.py).

### Acceptance

A clip is **accepted** only when it has enough clean single-speaker speech. It is **rejected**
(with the first matching reason) when: no speech · music only · insufficient speech
(< `min_speech_seconds`) · mostly silence · multiple speakers · background music · quality
below `good`. Multi-speaker and music-bedded audio are rejected even at high SNR because the
goal is a clean single-voice corpus.

## Outputs

`metadata/dataset.{sqlite,csv,xlsx}` share one schema (one row per source):

```
id, platform, source, filename, duration, speech_duration, classification, quality,
accepted, reason, audio_path, sample_rate, channels, bitrate, silence_pct, loudness_dbfs,
snr_db, has_speech, multi_speaker, has_music, noise_estimate
```

Accepted WAVs are copied to `accepted/`, rejected to `rejected/`. Datasets are rebuilt from
scratch each run (deterministic).

## Determinism & tests

No randomness, no network, no GPU. The same inputs + `Config` always produce the same dataset.

```bash
python -m pytest production/voice_dataset/tests -q
```

The suite is hermetic: it synthesises WAVs in-process (no ffmpeg, no media files) and an
autouse fixture blocks outbound sockets to guarantee it is offline.

## Architecture

```
production/voice_dataset/
  build.py       # CLI (python -m production.voice_dataset.build)
  pipeline.py    # orchestration (Steps 1-7 + file routing)
  providers/     # MediaProvider ABC + LocalFolderProvider (swappable acquisition)
  extract.py     # Step 2  (WAV passthrough / ffmpeg)
  analyze.py     # Steps 3 & 5 (DSP + heuristics)
  classify.py    # Step 4
  score.py       # Step 6
  decide.py      # Step 7
  storage.py     # sqlite / csv / xlsx
  summary.py     # run report
  config.py      # all thresholds (deterministic)
  models.py      # enums + dataclasses
```

## Requirements

Python ≥ 3.10, `numpy`, `openpyxl` (`uv pip install numpy openpyxl`). `ffmpeg` only if inputs
are not already WAV.
