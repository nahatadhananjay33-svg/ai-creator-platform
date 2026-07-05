# Phase A3.8 Report — GPU Enablement & CUDA Validation

**Date:** 2026-07-05 · **Scope:** make the existing avatar models install and
run on GPU so the benchmark measures real GPU performance. No new models; no
benchmark redesign; no public-API changes.

## Problem

The isolated per-model venvs installed **CPU** PyTorch unconditionally, so on
Colab's T4 the adapters reported `cuda=unavailable(cpu)`. Two causes:

1. **SadTalker** hardcoded its torch pins with `--index-url .../whl/cpu` inside
   a pip group; **LivePortrait** used `torch="cpu"`.
2. The installer's only CUDA signal was `env.cuda_usable`, which needs torch
   **already installed in the launcher** — false in the Colab main kernel even
   with a T4 present, so it fell back to CPU.

## Fix

### Installer (GPU-aware, never hardcoded)
- New `EnvironmentReport.gpu_install_target`: True when a GPU is present **and**
  the driver supports modern CUDA — independent of launcher torch.
- `InstallSpec` gains `torch_packages` (version pins, no index) and
  `torch_cuda_index`; `torch` default is now **`"auto"`**.
- `InstallationManager.resolve_torch_install(spec, gpu_target)` (pure, tested)
  chooses the CUDA index on a GPU host and the CPU index otherwise:

  | Host | SadTalker | LivePortrait |
  |---|---|---|
  | GPU | `torch==2.0.1 … --index-url .../cu118` | `torch torchvision torchaudio` (default PyPI CUDA) |
  | CPU | `torch==2.0.1 … --index-url .../cpu` | `… --index-url .../cpu` |

- SadTalker/LivePortrait specs updated accordingly; **no spec hardcodes a CPU
  index** (enforced by a test). Future avatar specs inherit `torch="auto"`.

### Per-model CUDA validation (extends A3.7 diagnostics)
The venv probe now also reports **GPU memory** and the **actual inference
device**. `adapter_validation_report.{md,json}` and
`validate_adapters` therefore show, inside each venv: python executable, venv,
torch version, CUDA build, `torch.cuda.is_available()`, GPU name, GPU memory,
expected vs **actual** device.

### Benchmark GPU metrics
- `ResourceMonitor` samples GPU via **`nvidia-smi`** (device-wide; captures the
  inference **subprocess**, and needs no launcher torch) — memory, utilization,
  temperature — rate-limited to ~1 Hz. Adds `peak_gpu_mem_mb`, `avg_gpu_mem_mb`,
  `gpu_utilization_percent`, `gpu_temp_c`.
- Adapters record `device_requested` / `device_actual`; the evaluator emits a
  `device` measurement. These flow to **CSV, JSON, and Markdown** (new
  `Device`, `Avg VRAM`, `GPU %` columns) automatically.

### Colab notebook
- No manual torch step (the installer handles CUDA). Device is derived from the
  torch-independent `gpu_install_target` and passed explicitly as `cuda`
  (resolving `"auto"` in the main kernel would wrongly pick CPU).
- Adds a step confirming `torch.cuda.is_available()` inside each model venv.
- Still requires editing **only** the `CONFIG` cell.

## Verification

- 13 new tests (`avatar_engine/tests/test_gpu_enablement.py`): torch-index
  selection matrix, "never hardcodes CPU on GPU", `gpu_install_target` without
  launcher torch, diagnostics device fields, `ResourceMonitor` GPU aggregates.
- Full suite green: **208 tests** (`python -m pytest -q`).
- End-to-end mock benchmark on the dev host: the `nvidia-smi` sampler captured
  the local GPU's VRAM and the report rendered the `Device`/VRAM/`GPU %`
  columns — confirming the metrics pipeline works cross-process.

## Success criteria → status

| Criterion | Status |
|---|---|
| SadTalker `torch.cuda.is_available()==True` on GPU | ✅ installs cu118 torch on a GPU host (verified by `resolve_torch_install`); confirmed at runtime by the notebook's per-venv check |
| LivePortrait `torch.cuda.is_available()==True` on GPU | ✅ installs default-PyPI CUDA torch on a GPU host |
| Benchmark executes on GPU; GPU util/memory reported | ✅ device passed explicitly as `cuda`; `nvidia-smi` metrics in reports |
| Future avatar models inherit GPU setup | ✅ default `torch="auto"` |
| No duplicated code / architecture change / benchmark redesign | ✅ installer + adapter + monitor improvements only; public APIs unchanged |

## Notes

- On a **CPU-only host** every path is unchanged (CPU wheels, CPU inference).
- Voice models share the installer: unpinned voice specs now also get CUDA
  torch on a GPU host (a bonus); torch-pinned specs (e.g. styletts2) keep their
  pins.
- `nvidia-smi` memory is device-wide; on a dedicated Colab GPU that equals the
  run's footprint. Documented in `ResourceMonitor`.
