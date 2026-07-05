# Audio Pipeline Validation (Phase A3.8.5)

## Why

The avatar benchmark is driven by audio. When a scenario's WAV is missing, the
dataset manager can substitute a **220 Hz sine placeholder**
(`datasets/manager.py::generate_placeholder_assets`) so the pipeline still runs
end-to-end. That is fine for wiring tests, but driving **SadTalker** with a
constant tone produces meaningless lip-sync while still "succeeding". A3.8.5
makes the pipeline *verify the audio is real speech* and refuse to generate on
placeholder/invalid audio instead of silently continuing.

## The pipeline (what feeds the benchmark)

```
scenario.script_text  ->  Voice Engine (KokoroAdapter.synthesize)
                      ->  <scenario_id>.wav  (real speech, 16-bit PCM)
                      ->  SadTalker inference (driving audio)
                      ->  generated video
```

`avatar_engine/scripts/generate_scenario_audio.py` runs Kokoro for every
scenario and now **validates each WAV it writes**; if Kokoro raises or the
output is not real speech it reports the real error and marks the scenario
FAILED — it never writes a placeholder.

## Classifier

`voice_engine/metrics/speech_detection.py` (stdlib only — no numpy) reads a
16-bit PCM WAV and classifies it:

| Class | Meaning |
|---|---|
| `speech` | broadband, amplitude-modulated → usable driving audio |
| `tone` | near-pure sinusoid → **placeholder / synthetic filler** |
| `silent` | essentially no signal |
| `corrupted` | unreadable / not 16-bit PCM |
| `missing` | file absent |
| `empty` | zero audio frames |

**Discriminator:** the decisive signal is the **envelope coefficient of
variation** (short-time RMS modulation). Calibrated on real Kokoro output vs the
220 Hz placeholder:

- real speech: `env_cv` ≈ 0.87–1.03 (syllables + pauses)
- placeholder tone: `env_cv` ≈ 0.004–0.005 (flat envelope)

So a clip is a `tone` when a single frequency holds ≥ 55 % of the spectral
energy **and** the envelope is flat (`env_cv < 0.20`); `silent` when RMS
< −50 dBFS or ≥ 98 % of frames are below the silence floor; otherwise `speech`.

Reported per file: duration, sample rate, channels, file size, RMS/peak dBFS,
silence %, crest factor, zero-crossing rate, dominant frequency (+ top 3),
spectral flatness, tonal energy ratio, envelope cv.

> **Honesty note:** distinguishing *real* from *synthetic* speech acoustically
> is not reliable, so the classifier reports **speech vs tone vs silence vs
> corrupted** — whether speech came from Kokoro is provenance the pipeline
> tracks, not something guessed from the waveform.

## Running it

```bash
python -m avatar_engine.scripts.validate_audio          # all scenario audio
python -m avatar_engine.scripts.validate_audio --assets-dir path/to/wavs
```

Writes `avatar_engine/output/validation/audio_validation_report.{md,json}` and
exits non-zero if any scenario is not real speech (so it can gate a pipeline).

## Benchmark prerequisite (the gate)

`AvatarBenchmarkConfig.validate_audio` (default **True**). Before avatar
generation the benchmark validates every scenario's driving audio:

- **Real generation models** (adapters with `RUNS_IN_VENV=True`, e.g. SadTalker,
  LivePortrait) **skip** any scenario whose audio is a tone / silent / corrupted,
  recording the case SKIPPED with the exact reason. The model never runs on bad
  audio.
- If **every** scenario's audio is invalid, the run **stops** with a
  `BenchmarkError` before any generation.
- The **mock** adapter (a pipeline wiring double) is exempt — it legitimately
  runs on synthetic audio.
- Each run writes `audio_validation_report.md` into its run directory.

Set `validate_audio=False` only for deliberate wiring runs.

## Tests

`avatar_engine/tests/test_audio_validation.py` pins: real speech, placeholder
tone (220 Hz and 440 Hz), silent, corrupted, missing, empty; Kokoro
duration-mismatch; report generation; and the benchmark gate (all-tone stops,
tone scenarios skipped while speech runs, mock exempt, gate disabled).
