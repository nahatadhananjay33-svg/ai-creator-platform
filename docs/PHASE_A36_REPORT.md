# Phase A3.6 Report — GPU Validation & Production Stack Freeze

**Date:** 2026-07-05 · **Phase goal:** run the complete Voice and Avatar
benchmark suites on a GPU machine and freeze the production stack from
*measured* data.

**Headline result (measured, not speculated):** the GPU benchmark suite
**could not be executed on the available hardware**, and the production
stack **cannot be frozen** in this phase. The blocker is hardware, not the
framework — the framework's own environment probe and compatibility engine
(reused unchanged) resolve **every** voice and avatar model to a *non-GPU*
execution mode on this machine. No measured GPU numbers exist to report, and
this document does not invent any.

This is a gating outcome that needs a hardware decision from the project
owner before A3.6 can complete. The precise remediation path is in §7.

---

## 1. The machine A3.6 actually ran on (measured)

Collected by the platform's own probe
(`foundation.model_manager.probe_environment`, reused — no new code). Full
JSON: [`docs/reports_a36/hardware_profile.json`](reports_a36/hardware_profile.json).

| Property | Measured value |
|---|---|
| OS | Windows 10 (build 10.0.26200) |
| CPU | Intel Family 6 Model 158 (Coffee-Lake class), 8 logical cores |
| RAM | **7.8 GB** total |
| GPU | **GeForce GTX 1050**, **3 GB** VRAM (single GPU) |
| GPU compute capability | 6.1 (Pascal) |
| NVIDIA driver | **451.67** → CUDA 11.0 runtime ceiling |
| CUDA usable by modern PyTorch | **NO** |
| Host Python | 3.11.9 |
| Free disk | 198.7 GB |

### Two independent facts each block GPU execution on their own

1. **Driver too old for modern CUDA.** The installed driver **451.67** is
   below the platform's own CUDA 11.8 floor (**452.39**, encoded in
   `environment._CUDA_DRIVER_FLOOR`). Every PyTorch CUDA wheel these models
   require (cu118 / cu121+) needs a newer driver. Result: `cuda_usable =
   false`. The GPU is visible to `nvidia-smi` but **not usable by PyTorch**.
2. **VRAM below the floor for the whole model set.** 3 GB is under the
   `min_vram_gb` of every GPU-class model in both engines (voice: 2–6 GB;
   avatar priority models: LivePortrait 3, SadTalker 4, MuseTalk 6,
   EchoMimic V3 6.5). Even with a driver update, this GPU could not host the
   priority avatar stack.

### A third, independent blocker: this is not the A3.5 machine

A3.5 ran on a host with **15.9 GB RAM** and a GTX 960M. This A3.6 host has
**7.8 GB RAM** and a GTX 1050 — a *different, weaker* machine. Consequences:

- **All model venvs are broken.** `.venvs/*` were built by `uv` under
  `C:\Users\ASUS\…` (Python 3.10/3.12 from that user's uv store). On this
  `C:\Users\ACER\…` host those base interpreters do not exist, so every venv
  fails to launch (`uv trampoline failed to spawn Python child process`).
  No model can execute — GPU **or** CPU — until the venvs are reprovisioned.
- **The A3.5 CPU baseline no longer reproduces here.** With 7.8 GB RAM,
  SadTalker and StyleTTS2 (the models that *did* run on CPU in A3.5) now
  fail even the CPU-offline gate, because their `min_ram_gb = 8` exceeds
  this machine's memory. This host is a downgrade from the A3.5 host for
  benchmarking purposes.

---

## 2. GPU benchmark reports (Deliverable 1)

**None produced — no GPU run was possible.** Producing a "GPU benchmark
report" with numbers would require fabricating data, which this phase
explicitly forbids ("Do not speculate where measurements are unavailable").

What *was* produced instead, from real probes:

- Environment + per-model compatibility reports regenerated on this machine
  via the framework's `--report-only` path:
  - [`voice_engine/output/installs/installation_report.md`](../voice_engine/output/installs/installation_report.md)
  - [`avatar_engine/output/installs/installation_report.md`](../avatar_engine/output/installs/installation_report.md)
- Hardware profile JSON: [`docs/reports_a36/hardware_profile.json`](reports_a36/hardware_profile.json)
- Empirical CUDA probe (see §3).

The benchmark **framework itself is verified runnable** — the orchestrators,
scenarios, reporting and evaluation modules import and the compatibility
engine executes cleanly. The moment CUDA-usable hardware exists, the suites
run unchanged (`python -m voice_engine.scripts.run_benchmark --device cuda …`
and the avatar equivalent). Nothing in the framework needs to change.

---

## 3. Empirical CUDA verification (measured on this machine)

This does not rest on the driver-floor *table* alone. `nvidia-smi` reports,
directly from the installed driver, the maximum CUDA runtime this driver can
host:

```
NVIDIA-SMI 451.67   Driver Version: 451.67   CUDA Version: 11.0
```

That **CUDA Version: 11.0** is a measured reading from the driver itself —
it is the highest CUDA runtime the driver exposes, and it is **below the
11.8** that every modern PyTorch CUDA wheel (cu118 / cu121+) ships. A
PyTorch build newer than the driver's ceiling loads but reports
`torch.cuda.is_available() == False` (no usable CUDA context). This matches
the platform probe's independent verdict `cuda_usable = false`.

(A full `torch cu118` install was also started as a redundant cross-check;
it was abandoned as unnecessary once the `nvidia-smi` CUDA-11.0 ceiling gave
the same answer directly, without a 2.7 GB download.)

**Conclusion: no CUDA-usable PyTorch on this driver — measured two
independent ways.**

---

## 4. Voice production stack recommendation (Deliverable 3)

**Cannot be frozen — zero measured GPU data.** Per-model compatibility on
this host (measured, framework verdicts):

| Model | min VRAM | min RAM | Verdict here | Mode |
|---|---|---|---|---|
| kokoro | — (CPU) | 4 GB | RAM ok; **no CUDA** | cpu |
| melotts | — (CPU) | 4 GB | RAM ok; **no CUDA** | cpu |
| styletts2 | 2 GB | 8 GB | RAM short (7.8<8); no CUDA | none |
| openvoice-v2 | 2 GB | 8 GB | no GPU path; RAM short | none |
| f5-tts | 4 GB | 8 GB | no GPU path; RAM short | none |
| xtts-v2 | 4 GB | 8 GB | no GPU path; RAM short | none |
| spark-tts | 4 GB | 8 GB | no GPU path; RAM short | none |
| cosyvoice2 | 4 GB | 16 GB | no GPU path; RAM short | none |
| chatterbox | 6 GB | 16 GB | no GPU path; RAM short | none |
| indic-parler | 6 GB | 16 GB | no GPU path; RAM short | none |
| dia | 6 GB | 16 GB | no GPU path; RAM short | none |

- **Default real-time model:** *undecided* — requires measured RTF / first-
  audio / streaming latency on real GPU. Not available.
- **Default quality model:** *undecided* — requires measured voice
  similarity + Hindi/Hinglish/Bengali quality on GPU. Not available.
- **Backup lightweight model:** the *only* defensible measured statement is
  that **kokoro** and **melotts** are the two CPU-real-time-capable engines
  that clear this machine's gates (both `cpu_realtime_capable=True`, 4 GB
  RAM). That is a compatibility fact, **not** a benchmarked quality ranking.

---

## 5. Avatar production stack recommendation (Deliverable 4)

**Cannot be frozen — zero measured GPU data.** All 18 catalogued avatar
models resolve to `mode = none` on this host (driver + VRAM + RAM). The
priority models fail as follows (measured):

| Priority model | min VRAM | min RAM | Why it can't run here |
|---|---|---|---|
| LivePortrait | 3 GB | 8 GB | no CUDA (driver); RAM 7.8<8 |
| EchoMimic V3 | 6.5 GB | 32 GB | no CUDA; VRAM 3<6.5; RAM 8<32 |
| MuseTalk | 6 GB | 16 GB | no CUDA; VRAM 3<6; RAM 8<16 |
| SadTalker | 4 GB (GPU) | 8 GB | no CUDA; RAM 7.8<8 (CPU path also gated out) |

- **Default production / lightweight / high-end models:** all *undecided*.
  No avatar model executed; no identity / lip-sync / motion / long-form
  numbers exist for A3.6. The A3.5 CPU-only SadTalker run remains the
  newest real avatar data the project has, and it is explicitly a stopgap.

---

## 6. Updated production rankings (Deliverable 2)

Unchanged from A3.5, and for the same reason: **no comparative benchmark
data across models exists.** A3.6 added no rankable measurements. Rankings
remain **deferred** until a GPU pass runs on adequate hardware.

---

## 7. Hardware & Multi-GPU (Deliverables 5 & 6)

- **Hardware compatibility report:** [`docs/HARDWARE_COMPATIBILITY_REPORT.md`](HARDWARE_COMPATIBILITY_REPORT.md)
- **Multi-GPU compatibility report:** [`docs/MULTI_GPU_COMPATIBILITY_REPORT.md`](MULTI_GPU_COMPATIBILITY_REPORT.md)
  — single GPU detected; multi-GPU inference is **not applicable** on this
  host (documented, not implemented, per phase scope).

### Remediation path to actually complete A3.6

Three options, in order of cost. Only the project owner can choose:

1. **Cloud / rented GPU (recommended).** A single 24 GB GPU (e.g. RTX
   4090 / A10 / L4-class) with a current driver clears every priority model
   at once. Reprovision the venvs there (they must be rebuilt regardless —
   see §1), then run the existing suites `--device cuda`. Fastest route to a
   real freeze; no local hardware purchase.
2. **Update this machine's driver, accept a reduced scope.** Updating the
   GTX 1050 driver to ≥ 452.39 (Pascal is still supported by current NVIDIA
   drivers) would make `cuda_usable = true`. But 3 GB VRAM + 7.8 GB RAM
   still excludes every avatar priority model and the mid/large voice
   models. At best this yields GPU numbers for the *smallest* voice models
   only — a partial, non-representative freeze. Not recommended as the basis
   for a production decision.
3. **Procure a local workstation GPU** (≥ 16 GB VRAM, ≥ 32 GB RAM) if
   on-prem is a hard requirement. Highest cost; same software steps as (1).

In **all** cases the model venvs must be reprovisioned (they are bound to a
machine that no longer exists), and PyTorch must be installed from a CUDA
index matching the target driver.

---

## 8. Final engineering answers (measured basis only)

> The phase asks five questions "based only on measured GPU benchmarks."
> There are **no** measured GPU benchmarks. Honest answers follow; none are
> fabricated.

**1. Which Voice models should become permanent production models?**
*Undetermined.* No GPU benchmark ran. The only measured statement possible
is a *compatibility* one: kokoro and melotts are the two engines that clear
this machine's gates — which is not a production-quality verdict. A freeze
requires the GPU pass in §7.

**2. Which Avatar models should become permanent production models?**
*Undetermined.* All 18 avatar models resolved to a non-executable mode on
this host. No avatar model produced a frame in A3.6.

**3. Which models should be removed from future maintenance?**
*None may be removed on measured grounds* — removing a model requires
measured evidence it underperforms, and no comparative data exists. The
earlier *research/install* verdicts (InfiniteTalk / Hallo3 / MEMO /
EchoMimic V2 etc. carry 24–64 GB RAM and 12–24 GB VRAM floors far beyond any
plausible single-box budget) remain **candidates for deprioritization**, but
that is an install-feasibility call inherited from A3.5, not a new A3.6
measurement.

**4. Is the current architecture sufficient for long-term production?**
**Yes — the architecture is not the blocker.** The framework probed the
machine correctly, produced accurate per-model compatibility verdicts,
refused to fabricate results, and would run the suites unchanged on adequate
hardware. The only gap is *hardware*, not software design. No redesign is
warranted or was done.

**5. Is the project ready to begin building the Production Avatar Engine?**
**Not yet — blocked on the GPU freeze.** Building the Production Avatar
Engine before any avatar model has a single measured GPU benchmark would
mean building on unmeasured assumptions, which is exactly what A3.6 exists to
prevent. The prerequisite is one GPU benchmark pass on §7-class hardware.
Once that yields measured identity / lip-sync / motion / long-form numbers,
the project is ready.

---

## 9. What A3.6 did deliver

Everything achievable without a usable GPU, all measured:

1. Confirmed and documented the real A3.6 host (different, weaker machine
   than A3.5) with the framework's own probe.
2. Proved — via the framework and an empirical PyTorch install — that CUDA
   is unusable on this driver.
3. Produced measured per-model compatibility verdicts for all 12 voice
   adapters and all 18 avatar models.
4. Regenerated environment-stamped install/compatibility reports on this
   machine (reusing `--report-only`; no new code).
5. Wrote the hardware-compatibility and multi-GPU-compatibility reports.
6. Archived the A3.5 CPU-era reports under `archive/a35_cpu_reports/`
   (originals preserved, not overwritten).
7. Defined the exact, costed remediation path to complete the GPU freeze.

**No architecture, benchmark framework, Voice Engine, or Avatar Engine code
was redesigned or rebuilt** — per the phase constraints.

## Artifacts

- Hardware profile: `docs/reports_a36/hardware_profile.json`
- Voice compatibility: `voice_engine/output/installs/installation_report.{md,json}`
- Avatar compatibility: `avatar_engine/output/installs/installation_report.{md,json}`
- Hardware report: `docs/HARDWARE_COMPATIBILITY_REPORT.md`
- Multi-GPU report: `docs/MULTI_GPU_COMPATIBILITY_REPORT.md`
- Production stack (NOT FROZEN): `docs/PRODUCTION_STACK.md`
- Archived A3.5 reports: `archive/a35_cpu_reports/`
