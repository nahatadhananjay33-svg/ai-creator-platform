# Voice Engine Installation Guide

> **GPU note (A3.6, 2026-07-05):** CUDA model installs require an NVIDIA
> driver **≥ 452.39** (the CUDA 11.8 floor). On older drivers the framework
> reports `CUDA usable: no` and every GPU-class model resolves to `mode:
> none` — check with `python -m voice_engine.scripts.install_models --all
> --report-only` before installing. Install PyTorch from the CUDA index that
> matches your driver (e.g. `--index-url https://download.pytorch.org/whl/cu118`).
> Model venvs are machine-bound (built by `uv` against a specific base
> Python) and must be rebuilt if the project is moved to a new machine.

## Platform core (always)

```bash
# from repo root, Python 3.10+
pip install -e .[dev]
pytest                                   # verify: all tests green, no GPU needed
python -m voice_engine.scripts.run_benchmark --adapters mock --languages en
```

The core has no ML dependencies. Model adapters detect their own optional
packages; missing ones show up as SKIPPED benchmark cases with the exact
install command in the report.

## GPU prerequisite for heavy adapters

NVIDIA driver + CUDA-enabled PyTorch first:

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
python -c "import torch; print(torch.cuda.is_available())"
```

## Per-model installation

**Preferred method:** `python -m voice_engine.scripts.install_models --models <ids>`
— it creates the per-model venv, applies every empirically resolved pin below,
runs prefetch steps, and verifies imports. The table records what Phase A1.5
actually verified on native Windows (CPU, Python 3.12 venvs via uv).

| Adapter | Verified status (A1.5, Windows/CPU) | Difficulty | Key fixes encoded in install_specs.py |
| --- | --- | --- | --- |
| `kokoro` | ✅ installed + validated (EN, HI) | ● Easy | run inside activated venv (its G2P shells out to uv) |
| `f5-tts` | ✅ installed + validated (EN cloning) | ●● Moderate | `pyarrow==21.0.0` (24.0 DLL crash); FFmpeg shared libs for torchcodec |
| `xtts-v2` | ✅ installed + validated (EN+HI cloning) | ●● Moderate | `transformers==4.57.1` + `torchcodec`; `COQUI_TOS_AGREED=1` |
| `chatterbox` | ✅ installed + validated (EN+HI cloning) | ●● Moderate | write PCM_16 via soundfile (torch 2.9 saves float32) |
| `styletts2` | ✅ installed + validated (EN cloning) | ●●● Fiddly | `torch==2.5.1` (weights_only pickle), nltk punkt_tab, `PYTHONUTF8=1` |
| `melotts` | ✅ installed + validated (EN) | ●●● Fiddly | py3.10 venv (tokenizers 0.13.3 has no cp312 wheel), unidic download, nltk taggers |
| `indic-parler` | ⚠️ installed; **weights gated** | ●● Moderate | `numba>=0.60` pin; requires HF account acceptance + `HF_TOKEN` |
| `dia` | ⚠️ installed; inference unvalidated (1.6B on CPU) | ●● Moderate | `numba>=0.60` pin; ~6.4 GB weights on first use |
| `openvoice-v2` | ❌ blocked on native Windows | ●●●● | faster-whisper 0.9 → av 10.x: no cp310 Windows wheel, source build fails. Use WSL2 |
| `cosyvoice2` | ❌ blocked on native Windows | ●●●● Hard | pynini/WeTextProcessing don't build; use WSL2/Linux |
| `spark-tts` | ⏸ not attempted | — | deprioritized pending license clarification |

**Environment isolation rule:** heavy adapters with conflicting pins
(CosyVoice especially) go in separate virtualenvs/containers. The benchmark
supports this: run per-adapter with `--adapters <id>` in each env and merge
runs — every report embeds run/environment metadata, and CSV/JSON outputs
concatenate cleanly.

## FFmpeg requirement (torch 2.9+)

torchaudio 2.9 routes audio I/O through **torchcodec**, which needs FFmpeg
*shared libraries* (DLLs, versions 4-8 — release builds, not master). The
platform installs them once under `.venvs/_tools/ffmpeg/`; every
`voice_engine.scripts.*` entry point auto-prepends it to PATH
(`voice_engine/scripts/__init__.py`). To provision manually:

```powershell
# BtbN n7.1 shared build (Windows)
Invoke-WebRequest https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n7.1-latest-win64-gpl-shared-7.1.zip -OutFile ff.zip
Expand-Archive ff.zip .venvs\_tools; Rename-Item .venvs\_tools\ffmpeg-n7.1-latest-win64-gpl-shared-7.1 ffmpeg
```

## Windows notes (this workstation)

- Prefer WSL2 for `cosyvoice2`, `openvoice-v2`, `melotts` (pynini and
  unidic are painful on native Windows).
- `kokoro`, `f5-tts`, `chatterbox`, `coqui-tts` work on native Windows with
  CUDA torch.
- The core platform + mock benchmark runs natively (verified in CI-style on
  this machine, Python 3.14).

## Verifying an install

```bash
python -m voice_engine.scripts.run_benchmark --adapters kokoro --languages en hi \
    --categories pricing conversation
```

A correct install produces PASSED cases and a `report.md` with measured RTF;
a broken one produces SKIPPED (missing package) or FAILED (runtime error)
cases with the captured error — nothing crashes the run.
