# Production Stack — Phase A3.6

**Status: NOT FROZEN.** ⛔

The production stack **cannot be frozen** in Phase A3.6 because the GPU
benchmark suite could not run on the available hardware. Freezing a
production stack requires measured GPU performance and quality data; none
exists. Freezing it from research assumptions or CPU-era data would defeat
the entire purpose of this phase.

See [`PHASE_A36_REPORT.md`](PHASE_A36_REPORT.md) for the full measured
rationale and [`HARDWARE_COMPATIBILITY_REPORT.md`](HARDWARE_COMPATIBILITY_REPORT.md)
for the blocking hardware facts.

---

## Voice stack

| Slot | Selection | Basis |
|---|---|---|
| Default real-time | **PENDING GPU BENCHMARK** | needs measured RTF, first-audio latency, streaming latency |
| Default quality | **PENDING GPU BENCHMARK** | needs measured similarity + Hindi/Hinglish/Bengali quality |
| Backup lightweight | **kokoro or melotts** (compatibility-only, not quality-ranked) | only CPU-real-time engines that clear this machine's gates |

## Avatar stack

| Slot | Selection | Basis |
|---|---|---|
| Default production | **PENDING GPU BENCHMARK** | no avatar model executed in A3.6 |
| Default lightweight | **PENDING GPU BENCHMARK** | LivePortrait/SadTalker are candidates; unmeasured on GPU |
| High-end rendering | **PENDING GPU BENCHMARK** | EchoMimic V3 is the research candidate; unmeasured |

---

## What must happen before this document can be frozen

1. Provision §7 hardware (see phase report) — a ≥ 24 GB VRAM host with a
   driver ≥ 452.39 clears the whole catalogue in one pass.
2. Reprovision the model venvs there (the current `.venvs/*` are bound to a
   machine that no longer exists and must be rebuilt regardless).
3. Run the existing suites unchanged:
   - `python -m voice_engine.scripts.run_benchmark --adapters <installed> --device cuda --languages en hi hi-en bn`
   - `python -m avatar_engine.scripts.run_benchmark --adapters <installed> --device cuda`
4. Fill the tables above from the measured reports and flip the status to
   **FROZEN**.

Until then, treat every "PENDING" slot as genuinely undecided. No default
model is committed.
