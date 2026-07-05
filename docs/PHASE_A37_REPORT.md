# Phase A3.7 Report — Adapter Validation & Runtime Fixes

**Date:** 2026-07-05 · **Scope:** diagnose and fix why the Colab GPU
validation reported `available=False` for every avatar adapter. No new models;
no benchmark redesign.

## Root cause (confirmed in code)

Real avatar adapters (SadTalker, LivePortrait) run their model **in an
isolated per-model venv** via subprocess — they never import the heavy deps
into the launching process. But availability was checked *in the launcher*:

```python
# avatar_engine/models/base.py (before)
def is_available(self):
    return all(importlib.util.find_spec(pkg) is not None for pkg in IMPORT_PACKAGES)
```

On Colab the benchmark ran in the **main kernel**, where `face_alignment` /
`insightface` / `basicsr` are not installed. `find_spec` returned `None`, so
every adapter reported `available=False` — with no reason — even though the
install report confirmed the venvs installed correctly. The installation was
fine; the **validation** was checking the wrong interpreter.

## Fix (adapter layer only)

- New `avatar_engine/models/diagnostics.py`:
  - `diagnose(...)` probes the adapter's **own venv interpreter** and returns a
    structured `AdapterDiagnostic` (python executable, venv dir/existence,
    `sys.path`, per-package import + version/traceback, torch version /
    `cuda.is_available()` / device name, expected-vs-actual device, required
    files, warnings, one-line reason, probe duration).
  - `sanitized_subprocess_env(...)` strips `PYTHONPATH`/`PYTHONHOME`/
    `VIRTUAL_ENV` leakage so the venv's packages aren't shadowed (requirement:
    subprocesses inherit the correct environment).
  - `write_adapter_validation_report(...)` → `adapter_validation_report.{md,json}`.
- `BaseAvatarAdapter`: `RUNS_IN_VENV`, `venv_python`/`venv_dir`,
  `required_paths()`, cached `diagnostics()`; `is_available()` delegates to it;
  `load()` raises `AdapterNotAvailableError` with the exact reason (→ SKIPPED,
  benchmark continues).
- SadTalker / LivePortrait: declare `required_paths()`; dispatch inference to
  `self.venv_python` (was `sys.executable`) with the sanitized env — so the
  benchmark can be launched from any interpreter and each adapter still runs in
  its own venv.
- `PlannedAvatarAdapter`: reports "planned - not implemented" rather than a
  misleading "venv missing".
- `AvatarModelValidator`: records the full diagnostic + precise reason.
- New script `avatar_engine/scripts/validate_adapters.py` and a diagnostics
  cell added to the Colab notebook.
- `foundation.model_manager.installer.model_venv_python(...)`: single source of
  truth for the per-model venv path, shared by installer and adapters.

## Before / after

```
# before
available=False        (every adapter, no reason)

# after (example, run on the dev host)
[AVAILABLE ] mock         ready (in-process adapter; no external dependencies)
[unavailable] sadtalker   environment probe failed: probe exited 1: uv trampoline
                          failed to spawn Python child process (venv interpreter broken)
[unavailable] musetalk    planned model - adapter not implemented yet (Phase A4)
```

On a healthy Colab venv the SadTalker line instead reports its packages, torch
version, and `cuda.is_available()` — i.e. exactly why it will or won't run.

## Verification

- 18 new regression tests in `avatar_engine/tests/test_diagnostics.py`
  (env sanitation, probe imports/torch, missing venv/package/file, CUDA-mismatch
  warning, planned adapters, validator integration, report writing).
- Full suite green: **195 tests pass** (`python -m pytest -q`).
- `validate_adapters` exercised end-to-end on the dev host; the report correctly
  distinguishes broken-venv vs planned vs available.

## Deliverables

- Venv-aware adapter validation + structured diagnostics
  (`avatar_engine/models/diagnostics.py`, `base.py`, adapters)
- Structured diagnostic logging (`avatar_engine.models.diagnostics` logger)
- `adapter_validation_report.md` / `.json` via `validate_adapters.py`
- Docs: [`avatar_engine/docs/ADAPTER_VALIDATION.md`](../avatar_engine/docs/ADAPTER_VALIDATION.md)
- Full regression tests (18 new)

## What this does *not* claim

The fix makes the framework report the truth per adapter. It does not make
MuseTalk/EchoMimic V3 runnable (no adapters — Phase A4) and does not change that
LivePortrait is video-driven while the dataset is audio-driven. Those are
recorded honestly, not worked around.
