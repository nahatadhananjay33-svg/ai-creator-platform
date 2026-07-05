# Benchmark Operations Guide (Phase A1.5)

End-to-end procedure for producing scientifically valid benchmark results.
Everything below uses production modules; no step fabricates data.

## 1. Probe the machine

```bash
python -m voice_engine.scripts.install_models --report-only
```

Writes `voice_engine/output/installs/installation_report.md` with the full
environment (CPU/RAM/GPU/driver/CUDA/torch/disk) and a per-model
compatibility verdict (`gpu` / `cpu` / `cpu-offline` / `none`).

## 2. Install models

```bash
python -m voice_engine.scripts.install_models --models kokoro f5-tts xtts-v2 chatterbox
```

- One venv per model under `.venvs/<model_id>/` (uv-managed, shared wheel cache).
- Resumable: re-running verifies existing installs and resumes failures.
- Empirically resolved pins live in `voice_engine/models/install_specs.py`,
  each with a comment explaining why it exists.

## 3. Validate models

Run **inside the model's venv** (activate it so tools that shell out, e.g.
kokoro's G2P auto-installs, see the right environment):

```powershell
& .venvs\kokoro\Scripts\Activate.ps1
python -m voice_engine.scripts.validate_models --adapters kokoro --languages en hi
```

Produces `voice_engine/output/validation/<model>-validation.json`: load
status, init time, first/subsequent inference time, peak RSS, per-language
pass/fail, plus smoke-test WAVs.

## 4. Reference audio

```powershell
# generate synthetic 10/20/30/60s clips (kokoro venv)
python -m voice_engine.scripts.generate_reference_clips
# duration study + per-engine recommendation (host python is fine)
python -m voice_engine.scripts.reference_study
```

## 5. Benchmark

Per model, inside its venv. Scope with `--max-items` on CPU-only machines
so slow models still produce a complete category spread:

```powershell
& .venvs\kokoro\Scripts\Activate.ps1
python -m voice_engine.scripts.run_benchmark --adapters kokoro --languages en hi
& .venvs\f5-tts\Scripts\Activate.ps1
python -m voice_engine.scripts.run_benchmark --adapters f5-tts --languages en `
    --max-items 4 --reference-audio <ref.wav> --reference-text "<transcript>"
```

## 6. Merge and compare

```bash
python -m voice_engine.scripts.merge_runs --latest-per-adapter --title "CPU baseline 2026-07"
```

One combined CSV/JSON/Markdown report across all models. Never compare runs
from different machines: every run embeds its hardware profile, and the
merge records each source run's environment.

## Measurement integrity rules

1. One model at a time — no concurrent heavy processes during timed runs.
2. SKIPPED ≠ FAILED: missing deps skip with the install hint; runtime errors fail with the captured exception.
3. `Measurement.source` separates `auto` (measured) from `human` (listening) from `static` (research) — reports must never blend them.
4. RTF/latency numbers are only valid for the hardware profile in the run's `environment` block.
5. Human listening (naturalness/accent/code-switch) follows `voice_engine/evaluation/human_eval.py` — ≥3 native raters, blind sheets.
