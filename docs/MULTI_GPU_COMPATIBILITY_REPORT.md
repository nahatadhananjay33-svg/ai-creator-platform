# Multi-GPU Compatibility Report — Phase A3.6

**Date:** 2026-07-05 · Detection **measured** via `nvidia-smi -L` and the
platform hardware probe.

## 1. Detection result

| Property | Value |
|---|---|
| GPUs detected | **1** |
| Device 0 | GeForce GTX 1050, 3 GB, driver 451.67 |
| Multi-GPU present | **No** |
| NVLink / peer access | N/A (single device) |

`nvidia-smi -L` output:

```
GPU 0: GeForce GTX 1050 (UUID: GPU-5ad076db-29bf-014a-7264-cf0bded5fd68)
```

## 2. Verdict

**Multi-GPU inference is not applicable on this host** — there is exactly
one GPU, and (per the hardware compatibility report) it is not CUDA-usable
under the current driver. There is nothing to parallelise across.

Per phase scope, distributed inference is **documented, not implemented.**

## 3. Model-side multi-GPU support (research, for future hardware)

Recorded here so the analysis is ready when multi-GPU hardware exists. This
is **not measured** — it reflects each project's documented capabilities and
must be validated on real multi-GPU hardware before being relied on.

| Model class | Data parallel (N independent streams) | Pipeline/tensor parallel (one job split) |
|---|---|---|
| Small voice (kokoro, melotts, styletts2) | Trivial — run one process per GPU | Not needed (fits one GPU) |
| Mid/large voice (xtts, f5, chatterbox, dia) | Yes — process-per-GPU sharding | Rarely needed; single-GPU inference is the norm |
| LivePortrait / SadTalker / MuseTalk | Yes — batch/stream sharding across GPUs | Not supported upstream out of the box |
| EchoMimic V3 / diffusion avatars | Yes for throughput | Some (e.g. Wan-family) ship multi-GPU/tensor-parallel launchers |
| InfiniteTalk / Hallo3 (14–24 GB class) | Yes | Yes — these are the models that *benefit* from ≥ 2 GPUs |

### Practical recommendation (when multi-GPU hardware is procured)

- The platform's workload is **many short independent jobs** (one avatar
  clip / one voice line per request). The highest-value parallelism is
  therefore **data parallelism**: one model instance per GPU, jobs
  load-balanced across them. This needs no model-internal changes.
- **Pipeline/tensor parallelism** only matters for the largest models
  (InfiniteTalk, Hallo3) that do not fit on a single consumer GPU. These are
  already deprioritised on cost grounds; revisit only if long-form
  unbounded-length generation becomes a hard product requirement.

**Do not implement distributed inference now** (per phase scope, and because
there is no multi-GPU hardware to validate against).
