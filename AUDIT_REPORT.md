# Voice Engine Architecture Audit — T1 Benchmark Pipeline

Generated: 2026-07-16 (Phase T1, benchmark pipeline preparation)
Scope: `voice_engine/` + the shared `foundation/` layers it builds on, audited before adding any
benchmark-setup code. Goal: reuse everything that exists; implement only what is missing.

## 1. What already exists

### Model installation (fully built, shared)
| Piece | Location | Notes |
| --- | --- | --- |
| Install specs (per-model pins) | [voice_engine/models/install_specs.py](voice_engine/models/install_specs.py) | One `InstallSpec` per model: pip groups, torch flavor, verify-imports, prefetch code. Encodes empirically resolved pins (`pyarrow==21.0.0` for f5-tts, `transformers==4.57.1` for xtts, …). |
| Installation manager | `foundation/model_manager/installer.py` | Idempotent per-model venv installs (uv primary, pip TLS fallback), CPU/CUDA torch index selection, import verification, prefetch hooks. |
| Install CLI driver | `foundation/model_manager/install_cli.py` | Shared by voice + avatar: env probe, compatibility verdicts, install loop, JSON+MD reports. |
| Voice installer entry point | `voice_engine/scripts/install_models.py` | `python -m voice_engine.scripts.install_models --models f5-tts` |
| Environment probing | `foundation/model_manager/environment.py` | GPU/driver/CUDA-floor/RAM/disk checks; produces the compatibility table. |

### Adapters + inference (fully built)
- 12 adapters in `voice_engine/adapters/` behind one `BaseVoiceAdapter` interface, registered in
  [registry.py](voice_engine/adapters/registry.py): mock, **f5-tts**, xtts-v2, openvoice-v2, chatterbox,
  dia, cosyvoice2, melotts, spark-tts, styletts2, indic-parler, kokoro.
- Each adapter carries a `ModelSpec` (license, hardware floors, weights source) and
  `EngineCapabilities` (cloning, streaming, languages).
- **F5-TTS support already exists**: [voice_engine/adapters/f5_tts.py](voice_engine/adapters/f5_tts.py)
  wraps `f5_tts.api.F5TTS` (load + `infer` with reference audio/text). Weights auto-download from
  `SWivid/F5-TTS_v1` on first load (HF cache = download-only-if-missing for free).

### Validation / smoke testing (fully built)
- `voice_engine/models/validation.py` — `ModelValidator`: load → reference acceptance → one smoke
  inference per language → WAV + JSON with init time, first-inference time, peak RSS.
- `voice_engine/scripts/validate_models.py` — CLI, designed to run **inside each model's venv**.

### Benchmarking (fully built — out of scope for T1 but ready)
- `voice_engine/benchmark/` (`VoiceBenchmark` orchestrator, config, scenarios) on top of
  `foundation/benchmarking/` (runner, results, `ResourceMonitor`).
- `voice_engine/scripts/run_benchmark.py` — multi-adapter/multi-language comparison runs.
- `voice_engine/scripts/merge_runs.py` — merges per-venv runs into one report.

### Evaluation + metrics (fully built)
- `voice_engine/evaluation/` (criteria, `SynthesisEvaluator`, human-eval scaffolding).
- `voice_engine/metrics/` (audio stats, performance/RTF, speaker similarity, speech detection, text metrics).

### Reporting (fully built)
- `voice_engine/reporting/` — CSV/JSON/Markdown reporters + `summarize_run`, on top of
  `foundation/reporting/`.
- Installer writes `voice_engine/output/installs/installation_report.{md,json}`.

### Datasets + references (exists; NOT touched in T1)
- Prompt datasets: `voice_engine/datasets/data/*.yaml` (en/hi/hinglish/bn).
- Reference clips: `voice_engine/datasets/reference_audio/` incl. synthetic 10–60 s clips with a
  known transcript (`generate_reference_clips.py`).

### Notebooks
- `notebooks/tanshi_voice_cloning_setup.ipynb` + `tanshi_avatar_training.ipynb` — Colab
  **training** setup (Phase B0 cloud work), not benchmark related. No new notebooks needed.

## 2. What is reusable for the T1 benchmark pipeline

Everything above. Concretely, the pipeline is a thin chain over:
`InstallationManager.install()` (install only if missing) → `validate_models` dispatched into the
model venv (weights only if missing, load, one smoke inference, WAV+JSON) → a report writer.

## 3. What was missing (gap analysis)

1. **A single orchestrated entry point.** Install, validation, and reporting existed as three
   manual steps in two different interpreters (driver Python vs model venv). Nothing chained them
   or produced one setup report. → **Added** [voice_engine/scripts/setup_benchmark.py](voice_engine/scripts/setup_benchmark.py) (~200 lines, zero duplicated logic).
2. **Machine-move recovery.** `InstallationManager._ensure_venv` treats an existing
   `python.exe` as a usable venv; after the repo moved to this machine the stale uv trampoline
   (bound to the old host's Python) made installs fail with
   "No virtual environment … found". Workaround applied: delete `.venvs/<model>` and reinstall.
   (Improvement candidate: recreate the venv when the interpreter fails to spawn.)
3. **Dependency drift for f5-tts.** Fresh resolution now backtracks to `numba 0.53` →
   `llvmlite 0.36`, which cannot build on Python 3.12. → **Fixed** by pinning `numba>=0.60` in the
   f5-tts install spec (same pin indic-parler/dia already used).

## 4. What should be improved (not done in T1 — noted only)

- `_ensure_venv` should verify the interpreter actually spawns (machine-bound trampoline check)
  before reusing an existing venv.
- The compatibility RAM floor is borderline on this 7.8 GB machine ("need 8 GB, have 8 GB" → verdict
  NO). The table is informational-only, so installs still proceed; consider a soft-warn threshold.
- `reference_audio/transcripts.yaml` (referenced by the datasets README) does not exist; the
  synthetic-clip transcript lives only in `generate_reference_clips.py`. Worth extracting.
- Root-level `bench_*.log` / `*_validation_log.txt` files predate `voice_engine/output/` and could
  be archived.

## 5. Duplication check

No new folders, environments, or notebooks were created. New code added in T1:
- `voice_engine/scripts/setup_benchmark.py` (orchestrator; delegates every stage to existing code).
- One-line spec fix in `voice_engine/models/install_specs.py` (`numba>=0.60`).
