# Adapter Validation & Runtime Diagnostics (Phase A3.7)

## The problem this solves

Avatar adapters that run a cloned model repo (SadTalker, LivePortrait, …) do
**not** import their heavy dependencies into the process that launches the
benchmark. Each model lives in its own isolated venv under `.venvs/<model>/`
and inference is dispatched there via subprocess.

The old availability check imported the packages **in the current process**:

```python
def is_available(self):
    return all(importlib.util.find_spec(pkg) is not None for pkg in IMPORT_PACKAGES)
```

That only succeeds if the benchmark is launched from *inside* the model's
venv. On Google Colab (Phase A3.6) the benchmark ran in the main kernel,
where `face_alignment` / `insightface` are not installed — so every adapter
reported `available=False`, with no explanation, even though the venvs were
healthy.

## The fix

Availability and CUDA are now probed **inside the adapter's own venv
interpreter**, and the result is a structured diagnostic instead of a bare
boolean.

- `avatar_engine/models/diagnostics.py`
  - `diagnose(...)` runs a JSON-emitting probe in the target interpreter and
    returns an `AdapterDiagnostic`: python executable, venv dir + existence,
    `sys.path` head, per-package import result (+version or traceback), torch
    version / `cuda.is_available()` / device name, expected-vs-actual device,
    required-file existence, warnings, and a one-line `reason`.
  - `sanitized_subprocess_env(...)` strips `PYTHONPATH` / `PYTHONHOME` /
    `VIRTUAL_ENV` leakage from the launcher so the venv's own packages win.
  - `write_adapter_validation_report(...)` emits the report (below).
- `BaseAvatarAdapter`
  - `RUNS_IN_VENV` (True by default; `mock` sets it False).
  - `venv_python` / `venv_dir` resolve the per-model venv (installer's
    convention; overridable via `config['venv_python']`).
  - `required_paths()` — repo entrypoints / checkpoints an adapter needs;
    SadTalker and LivePortrait declare theirs.
  - `diagnostics()` caches the probe; `is_available()` returns
    `diagnostics().available`; `load()` raises `AdapterNotAvailableError`
    carrying the exact reason (the benchmark records the case **SKIPPED**).
- SadTalker / LivePortrait now dispatch inference to `self.venv_python` (not
  `sys.executable`) with `sanitized_subprocess_env(...)`, so the benchmark
  can be launched from any interpreter and each adapter still uses its own venv.

Nothing in the benchmark orchestrator or the model set changed.

## Generating the report

Run from a single launcher (e.g. the Colab main kernel) — it probes every
adapter's venv without needing to be inside them:

```bash
python -m avatar_engine.scripts.validate_adapters                       # default set
python -m avatar_engine.scripts.validate_adapters --adapters sadtalker liveportrait
python -m avatar_engine.scripts.validate_adapters --all --device cuda
```

Outputs (git-ignored; regenerate as needed):

```
avatar_engine/output/validation/adapter_validation_report.md
avatar_engine/output/validation/adapter_validation_report.json
```

## Reading the report

Each adapter resolves to one of:

| Reason pattern | Meaning | Fix |
|---|---|---|
| `ready (cuda=…; torch=…)` | Available; will run | — |
| `venv not found at …` | Model not installed on this host | `install_models --models <id>` |
| `environment probe failed: …` | venv exists but its interpreter is broken (e.g. moved machine) | rebuild the venv |
| `missing packages: …` | venv present, a dependency failed to import (traceback in JSON) | reinstall that package in the venv |
| `missing files: …` | repo/checkpoint absent | re-run the installer's clone/prefetch |
| `planned model - adapter not implemented yet` | Researched only; no adapter | out of scope until Phase A4 |

The `Device✓` column / `device_matches_expectation` flags the A3.6-class
mismatch where `--device cuda` is requested but the venv's torch is CPU-only
(availability stays True; inference falls back to CPU — a **warning**, not a
blocker).

## Notes on specific adapters

- **LivePortrait** is video-driven (`REQUIRED_INPUTS` includes
  `driving_video`). The audio-driven benchmark dataset provides no driving
  video, so its cases are recorded FAILED with `requires driving_video` even
  when the adapter itself is *available*. That is a dataset/task mismatch, not
  an environment fault — the validation report will still show LivePortrait as
  available once its venv + weights are present.
- **MuseTalk / EchoMimic V3** are `PlannedAvatarAdapter` placeholders — the
  report states this plainly rather than implying an environment problem.
