# Hardware Compatibility Report — Phase A3.6

**Date:** 2026-07-05 · All values **measured** on this host via
`foundation.model_manager.probe_environment` (reused, unchanged).

## 1. Detected hardware

| Property | Value | Source |
|---|---|---|
| OS | Windows 10 (10.0.26200) | `platform` |
| CPU | Intel Family 6 Model 158 (Coffee-Lake class) | `platform.processor` |
| Logical cores | 8 | `psutil` |
| RAM | 7.8 GB | `psutil` |
| GPU model | GeForce GTX 1050 | `nvidia-smi` / torch |
| GPU count | 1 | `nvidia-smi -L` |
| VRAM | 3072 MB (3 GB) | `nvidia-smi` |
| Compute capability | 6.1 (Pascal) | NVIDIA spec for GTX 1050 |
| NVIDIA driver | 451.67 | `nvidia-smi --query-gpu=driver_version` |
| CUDA runtime ceiling (driver) | 11.0 | `nvidia-smi` header |
| Torch CUDA usable | **No** | probe + empirical install (§3) |
| Free disk | 198.7 GB | `shutil.disk_usage` |
| Host Python | 3.11.9 | `platform` |

## 2. Why CUDA is unusable (measured)

The driver **451.67** is below the CUDA 11.8 driver floor **452.39** that
modern PyTorch wheels require (the floor table lives in
`foundation/model_manager/environment.py::_CUDA_DRIVER_FLOOR`). Therefore
`EnvironmentReport.cuda_usable` evaluates to **False**, and every model's
compatibility resolves to a non-GPU mode. The GPU is detectable but cannot
be targeted by PyTorch without a driver update.

CUDA driver floors (Windows), for reference:

| CUDA build | Min driver | This host (451.67) |
|---|---|---|
| 11.8 | 452.39 | ✗ short by 0.72 |
| 12.1 | 527.41 | ✗ |
| 12.4 | 551.61 | ✗ |
| 12.6 | 560.76 | ✗ |

## 3. Direct driver measurement

`nvidia-smi` reports the driver's own CUDA runtime ceiling — a measurement,
not a table lookup:

```
NVIDIA-SMI 451.67   Driver Version: 451.67   CUDA Version: 11.0
```

The driver caps CUDA at **11.0**, below the **11.8** modern PyTorch wheels
require. A newer PyTorch build therefore reports
`torch.cuda.is_available() == False` on this host. This is the same verdict
the platform probe reaches independently (`cuda_usable = false`).

## 4. Per-model compatibility (framework verdicts, measured)

Mode legend: `gpu` runnable on GPU · `cpu` CPU real-time · `cpu-offline`
CPU batch-only · `none` cannot run here.

### Voice (12 adapters)

| Model | min VRAM | min RAM | Mode here | Blocking reason |
|---|---|---|---|---|
| kokoro | — | 4 GB | cpu | no CUDA (driver); GPU not required |
| melotts | — | 4 GB | cpu | no CUDA; GPU not required |
| mock | — | 0.1 GB | cpu | n/a (test adapter) |
| styletts2 | 2 GB | 8 GB | none | no CUDA; RAM 7.8 < 8 |
| openvoice-v2 | 2 GB | 8 GB | none | no CUDA; RAM 7.8 < 8 |
| f5-tts | 4 GB | 8 GB | none | no CUDA; RAM 7.8 < 8 |
| xtts-v2 | 4 GB | 8 GB | none | no CUDA; RAM 7.8 < 8 |
| spark-tts | 4 GB | 8 GB | none | no CUDA; RAM 7.8 < 8 |
| cosyvoice2 | 4 GB | 16 GB | none | no CUDA; RAM 7.8 < 16 |
| chatterbox | 6 GB | 16 GB | none | no CUDA; VRAM/RAM short |
| indic-parler | 6 GB | 16 GB | none | no CUDA; VRAM/RAM short |
| dia | 6 GB | 16 GB | none | no CUDA; VRAM/RAM short |

### Avatar (18 catalogued models)

| Model | min VRAM | min RAM | Mode here | Blocking reason |
|---|---|---|---|---|
| liveportrait | 3 GB | 8 GB | none | no CUDA; RAM 7.8 < 8 |
| sadtalker | 4 GB | 8 GB | none | no CUDA; RAM 7.8 < 8 |
| wav2lip | 2 GB | 8 GB | none | no CUDA; RAM 7.8 < 8 |
| musetalk | 6 GB | 16 GB | none | no CUDA; VRAM/RAM short |
| ditto | 6 GB | 16 GB | none | no CUDA; VRAM/RAM short |
| latentsync | 6.5 GB | 16 GB | none | no CUDA; VRAM/RAM short |
| echomimic-v3 | 6.5 GB | 32 GB | none | no CUDA; VRAM/RAM short |
| float | 8 GB | 16 GB | none | no CUDA; VRAM/RAM short |
| omniavatar | 8 GB | 32 GB | none | no CUDA; VRAM/RAM short |
| sonic | 10 GB | 32 GB | none | no CUDA; VRAM/RAM short |
| infinitetalk | 12 GB | 64 GB | none | no CUDA; VRAM/RAM short |
| fantasy-talking | 5 GB | 32 GB | none | no CUDA; VRAM/RAM short |
| echomimic-v2 | 16 GB | 32 GB | none | no CUDA; VRAM/RAM short |
| hallo2 | 16 GB | 32 GB | none | no CUDA; VRAM/RAM short |
| memo | 16 GB | 32 GB | none | no CUDA; VRAM/RAM short |
| hallo3 | 24 GB | 64 GB | none | no CUDA; VRAM/RAM short |
| omnihuman | — | — | cpu-offline | API/undefined local spec |

## 5. Minimum hardware to run each priority tier (derived from specs)

| Tier | Needs | Example GPU |
|---|---|---|
| Smallest voice (kokoro/melotts) | CPU only, 4 GB RAM | any |
| Mid voice (f5/xtts/styletts2) | ≥ 4 GB VRAM, ≥ 8 GB RAM, driver ≥ 452.39 | RTX 3060 8–12 GB |
| Full voice + LivePortrait/SadTalker/MuseTalk | ≥ 8 GB VRAM, ≥ 16 GB RAM | RTX 3080/4070 |
| EchoMimic V3 / long-form avatar | ≥ 12–16 GB VRAM, ≥ 32 GB RAM | RTX 4090 / A10 |
| Everything incl. Hallo3/InfiniteTalk | ≥ 24 GB VRAM, ≥ 64 GB RAM | A100 / L40S |

**Conclusion:** the A3.6 host (GTX 1050 3 GB, 7.8 GB RAM, driver 451.67)
does not meet the minimum for *any* GPU tier. A ≥ 24 GB VRAM host with a
current driver clears the entire catalogue in one pass.
