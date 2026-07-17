# Benchmark Setup Pipeline — T1

Generated: 2026-07-16
Entry point: [voice_engine/scripts/setup_benchmark.py](voice_engine/scripts/setup_benchmark.py)

## One command per model

```bash
python -m voice_engine.scripts.setup_benchmark --model f5-tts
python -m voice_engine.scripts.setup_benchmark --model xtts-v2 --languages en hi
python -m voice_engine.scripts.setup_benchmark --model kokoro --device cpu
```

Options: `--languages en|hi|hi-en|bn`, `--device cpu|cuda|mps`,
`--reference-audio/--reference-text` (cloning models default to the checked-in synthetic EN clip),
`--force-install`, `--validation-timeout`.

## What it does (and what it reuses)

| Stage | Behavior | Reused component (no new logic) |
| --- | --- | --- |
| 1. Install | Creates the per-model venv and installs pinned deps **only if missing** — a verified install returns `already-installed` in seconds. CPU vs CUDA torch index chosen from the environment probe. | `foundation.model_manager.InstallationManager` + `voice_engine/models/install_specs.py` |
| 2. Weights | Pretrained weights pull from Hugging Face on first model load into the user cache; cache hits skip the download entirely. | HF `cached_path` inside each adapter (e.g. `f5_tts.api.F5TTS`) |
| 3. Load + smoke | Loads the model and runs one small inference per requested language, **inside the model's own venv** (pins conflict across models, so dispatch matters). | `voice_engine/scripts/validate_models.py` → `ModelValidator` |
| 4. Artifacts | Smoke WAV(s) + validation JSON (timings, peak RSS, per-language pass/fail) + full stdout/stderr log. | `ModelValidator` outputs; the pipeline adds the log capture |
| 5. Report | Writes `<model>_SETUP_REPORT.md` with environment, install status, load/inference timings, artifact paths, and the model's license (commercial-use flag surfaced). | `ModelSpec` metadata on each adapter |

Outputs: `voice_engine/output/benchmark_setup/<model>/` (report + `setup.log`) and
`voice_engine/output/validation/` (`<model>-validation.json`, `<model>-<lang>-smoke.wav`).
Exit code 0 ⇔ model is READY (installed, loads, inference produced audio).

Explicit non-goals, enforced by design: no fine-tuning, no dataset modification, no multi-model
comparison (that is `run_benchmark.py` + `merge_runs.py`, which already exist).

## How future models plug in

The pipeline is model-agnostic; a new model (e.g. Fish Speech) needs exactly two things it would
need anyway:

1. **An adapter** in `voice_engine/adapters/` subclassing `BaseVoiceAdapter` (SPEC + CAPABILITIES +
   `_load_impl` + `_synthesize_impl`), registered in `registry.py`.
2. **An install spec** in `voice_engine/models/install_specs.py` (pip groups + pins + verify imports).

Then `python -m voice_engine.scripts.setup_benchmark --model fish-speech` works with no pipeline
changes. Already-registered models (xtts-v2, cosyvoice2, chatterbox, kokoro, …) work today.

## Verified end-to-end

First real run: **f5-tts** on this machine (see [F5_SETUP_REPORT.md](F5_SETUP_REPORT.md)).
Notes captured along the way (details in [AUDIT_REPORT.md](AUDIT_REPORT.md)):

- Per-model venvs are machine-bound; after a repo move, delete `.venvs/<model>` before
  reinstalling (the stale uv trampoline otherwise short-circuits venv creation).
- `numba>=0.60` added to the f5-tts spec — fresh resolution otherwise backtracks to
  llvmlite 0.36, which cannot build on Python 3.12.
- This machine has no usable CUDA (GTX 1050, driver 451.67 < the 452.39 CUDA 11.8 floor), so
  setup runs validate on CPU; timings are functional checks, not performance benchmarks.
