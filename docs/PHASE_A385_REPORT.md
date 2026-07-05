# Phase A3.8.5 Report — Audio Pipeline Validation & Baseline Verification

**Date:** 2026-07-06 · **Scope:** verify the audio feeding the avatar benchmark
is **real speech**, not the 220 Hz placeholder tone. No changes to avatar
models, SadTalker inference, or the benchmark architecture — only a validation
layer + a pre-generation gate.

## The concern (confirmed real)

When a scenario's driving WAV is missing, the dataset manager substitutes a
**220 Hz sine placeholder** (`generate_placeholder_assets`), and the avatar
benchmark ran with `allow_placeholder_assets=True` — so if Kokoro audio was
absent, SadTalker could be driven by a constant tone while the run still
"succeeded". A3.8.5 makes that impossible to happen silently.

## Pipeline traced

```
scenario.script_text -> KokoroAdapter.synthesize -> <id>.wav -> SadTalker -> video
```

## What was added

- **Classifier** `voice_engine/metrics/speech_detection.py` (stdlib only):
  reads a 16-bit PCM WAV and returns `speech | tone | silent | corrupted |
  missing | empty` plus a full waveform summary (duration, sample rate, RMS,
  peak, silence %, crest factor, ZCR, dominant frequency + top 3, spectral
  flatness, tonal energy ratio, envelope cv). Reuses `compute_audio_stats`; adds
  a Goertzel-based spectrum.
- **Calibrated** on the 10 real Kokoro assets vs the 220 Hz/440 Hz placeholders
  and silence. Decisive discriminator: **envelope coefficient of variation** —
  real speech 0.87–1.03, placeholder tone ~0.005. All 10 real clips classify as
  `speech`; both tones as `tone`; silence as `silent`.
- **Kokoro validation**: `generate_scenario_audio.py` validates every WAV it
  writes; on Kokoro error or non-speech output it reports the real error and
  marks the scenario FAILED — **never** writes a placeholder.
- **Benchmark gate** (`AvatarBenchmarkConfig.validate_audio`, default True):
  before generation the orchestrator validates each scenario's audio; real
  models (`RUNS_IN_VENV`) **skip** tone/silent/corrupted scenarios with the
  exact reason, and if **all** audio is invalid the run **stops**
  (`BenchmarkError`). The mock wiring double is exempt. Each run also emits
  `audio_validation_report.md`.
- **Report script** `avatar_engine/scripts/validate_audio.py` →
  `audio_validation_report.{md,json}` (source script, speech Yes/No, placeholder
  Yes/No, dominant frequency, silence %, duration, RMS, file size, waveform
  summary). Non-zero exit if any file isn't speech.
- **Notebook**: added step 9b (validate driving audio) before the benchmark.
- **Docs**: `avatar_engine/docs/AUDIO_VALIDATION.md`.

## Verification

- 14 new tests (`avatar_engine/tests/test_audio_validation.py`): real speech,
  placeholder tone (220/440 Hz), silent, corrupted, missing, empty, Kokoro
  duration mismatch, report writing, and the gate (all-tone stops, tone skipped
  while speech runs, mock exempt, gate off).
- Full suite green: **222 tests** (`python -m pytest -q`).
- On the dev host, `validate_audio` classifies all 10 real Kokoro assets as
  `speech`; a normal benchmark run logs `real_speech=2 invalid=0` and emits the
  audio report.

## Success criteria → status

| Criterion | Status |
|---|---|
| Every generated WAV is validated | ✅ classifier + script + in-benchmark gate |
| Placeholder tones detected automatically | ✅ 220/440 Hz → `tone` (envelope cv) |
| Benchmarks never continue with invalid audio | ✅ real models skip bad audio; all-invalid stops the run |
| Kokoro failures reported clearly | ✅ real error surfaced; no placeholder written |
| Only real speech reaches avatar generation | ✅ gate on `RUNS_IN_VENV` adapters |
| Tests pass | ✅ 222 green |

## Not done (by constraint)

Avatar models, SadTalker inference, and the benchmark runner/case abstraction
are unchanged. The gate is a pre-generation check + one optional case
`skip_reason`, not an architecture change.
