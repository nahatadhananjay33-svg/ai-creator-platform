# Phase A1.5 Report — Model Integration, Installation & Scientific Validation

**Date:** 2026-07-04 · **Hardware:** Intel i7-6700HQ-class (8 logical cores),
15.9 GB RAM, GTX 960M 4 GB (driver 398.35 — **CUDA unusable**, see below),
Windows 10, 159 GB free disk. All numbers below are **CPU-only** measurements.

Rule enforced throughout: every number in the "Measured" sections comes from
an actual execution archived under `voice_engine/output/` (runs, validation
JSONs, installation reports). Research-based statements are explicitly
labeled *research*.

---

## 1. Installation results (12 candidates)

| Model | Outcome | Evidence |
| --- | --- | --- |
| Kokoro-82M | ✅ installed, validated EN+HI | kokoro-validation.json |
| MeloTTS | ✅ installed (py3.10 venv), validated EN | melotts-validation.json |
| StyleTTS 2 | ✅ installed, validated EN + cloning | styletts2-validation.json |
| XTTS v2 | ✅ installed, validated EN+HI + cloning | xtts-v2-validation.json |
| Chatterbox (multilingual) | ✅ installed, validated EN+HI + cloning | chatterbox-validation.json |
| F5-TTS | ✅ installed, validated EN + cloning | f5-tts-validation.json |
| Dia | ⚠️ installed, import-verified; **inference not attempted** — 1.6B whole-utterance decode is impractical on this CPU; needs GPU | install cache |
| Indic Parler-TTS | ⚠️ installed; **weights gated** — requires the user to accept terms at huggingface.co/ai4bharat/indic-parler-tts and set `HF_TOKEN` | parler_validation_log |
| OpenVoice V2 | ❌ blocked on native Windows: pins faster-whisper 0.9 → av 10.x (no cp310 wheel; source build fails) | install log |
| CosyVoice 2 | ❌ blocked on native Windows (pynini); **the** streaming candidate — must be evaluated under WSL2/GPU in A2 | policy skip |
| Spark-TTS | ⏸ not attempted (license unresolved — A1 research) | policy skip |
| Seed-TTS | ⏸ excluded (no open weights — A1 research) | — |

Six models fully operational = every candidate that *can* run on native
Windows CPU does. Empirically resolved fixes are codified in
[install_specs.py](../voice_engine/models/install_specs.py) and
[INSTALLATION.md](../voice_engine/docs/INSTALLATION.md) (pyarrow 21 pin,
transformers 4.57.1+torchcodec for XTTS, torch 2.5.1 for StyleTTS2, py3.10
venv + UniDic for MeloTTS, FFmpeg 7.1 shared libs for torch 2.9 audio I/O,
PCM_16 output normalization, `webrtcvad-wheels` for resemblyzer).

## 2. Measured benchmark results (merged run `merged-20260704-154713-9e0fc7`)

69 passed cases, 0 failures, real-estate multilingual dataset, all on the
hardware profile above. Similarity = GE2E cosine vs the 10 s reference.

| Model | Cases | Langs | Mean RTF (CPU) | Speaker similarity | Peak RAM | Silence | Clipping |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MeloTTS | 15 | EN | **0.91** | — (no cloning) | 2.36 GB | 0.20 | 0 |
| Kokoro | 30 | EN 1.38 / **HI 0.99** | 1.19 | — (no cloning) | 1.91 GB | 0.25 | 0 |
| StyleTTS 2 | 8 | EN | 2.27 | 0.916 | 3.34 GB | 0.21 | 0 |
| XTTS v2 | 10 | EN 4.23 / HI 4.49 | 4.36 | 0.810 | 3.19 GB | 0.18 | 0 |
| Chatterbox | 4 | EN 13.44 / HI 13.50 | 13.47 | **0.935** | 5.78 GB | 0.22 | 0 |
| F5-TTS | 2 | EN | 53.9 | **0.959** | 2.85 GB | 0.20 | 0 |

Validation timings (model load / first / subsequent inference, seconds):
Kokoro —/33.5/12.2 · MeloTTS 16.8/138(BERT dl)/— · StyleTTS2 18.3/16.1/— ·
XTTS 700(incl. 1.9 GB dl)/16.8/24.7 · Chatterbox 34.5/72.4/69.0 ·
F5 60.2/459.8/—.

**Caveats (integrity):**
- Similarity scores use a **synthetic** (Kokoro-voice) reference — valid as
  a relative cloning-fidelity signal, not as absolute human-voice fidelity.
  Human-recorded references remain an A2 requirement.
- Chatterbox/F5 ran reduced prompt sets (4 and 2 cases) because of CPU cost;
  their RTFs are stable across cases (13.44 vs 13.50; 52.4 vs 55.5).
- **Streaming latency was not measured**: no native-streaming engine was
  runnable here (CosyVoice blocked; XTTS's stream API is pointless at CPU
  RTF 4.4). Streaming numbers must come from the A2 GPU/WSL pass.
- Hinglish and Bengali were **not** benchmarked on real models (Bengali's
  only candidate is gated; Hinglish quality needs the A2 listening test).

## 3. Reference-audio study (measured)

10/20/30/60 s clips, 24 kHz, 0% clipping, ~22% silence: all durations
accepted by every cloning engine; recommendation **20 s** for all engines
(sweet-spot rule). `voice_engine/output/validation/reference_study.json`.

## 4. Rankings (measured where possible)

| Category | Winner | Basis |
| --- | --- | --- |
| Best overall (this hardware) | **Kokoro** | measured: only engine real-time in Hindi AND near-real-time EN with 1.9 GB RAM |
| Best English (quality proxy) | F5-TTS (0.959) / Chatterbox (0.935) | measured similarity; perceptual MOS pending human raters |
| Best Hindi (working today) | XTTS v2 (cloning; license-blocked) / **Kokoro** (deployable) | measured EN+HI runs |
| Best Hinglish | **unmeasured** — A2 listening test (Chatterbox vs IndicF5) | — |
| Best Bengali | **unmeasured** — Indic Parler gated (user action) | — |
| Best streaming | **unmeasured** — CosyVoice 2 (research) pending A2 GPU/WSL | — |
| Best content creation | Chatterbox | highest commercially-usable measured similarity + EN&HI passed |
| Best Voice AI (this hardware) | Kokoro | measured RTF ≤ 1.2, HI voices |
| Best CPU model | MeloTTS (0.91, EN-only) / Kokoro (multilingual) | measured |
| Best GPU model | not measurable here (no usable CUDA) | — |
| Best lightweight | Kokoro (1.9 GB RAM, 0.4 GB disk) | measured |
| Best production model (today, commercial) | Kokoro (voice AI) + Chatterbox (content, GPU needed) | measured + license |

## 5. Known issues (all reproduced and worked around)

1. torch 2.9 audio I/O requires FFmpeg shared libs — auto-pathed via `.venvs/_tools/ffmpeg` (`voice_engine/scripts/__init__.py`).
2. pyarrow 24.0 crashes (access violation) on this CPU/Windows → pin 21.0.0.
3. coqui-tts needs transformers 4.54–4.x (<5) + torchcodec.
4. StyleTTS2 checkpoints incompatible with torch≥2.6 `weights_only` → torch 2.5.1.
5. MeloTTS: py3.10-only deps, UniDic + NLTK tagger downloads.
6. Chatterbox emitted one token-repetition warning with forced EOS on the synthetic reference (alignment analyzer working as designed — monitor with real references).
7. Windows cp1252 console breaks phonemizer output → `PYTHONUTF8=1` for all runs.
8. Kokoro's G2P shells out to `uv` — must run inside an activated venv.

## 6. Deployment scenarios (recommended)

| Scenario | Engine | Evidence class |
| --- | --- | --- |
| Real-estate phone/WhatsApp voice AI (HI/EN), CPU servers | Kokoro | measured (RTF ≈ 1) |
| English voice AI with Indian accent, minimal footprint | MeloTTS (EN-India speaker) | measured |
| Reels/YouTube narration with cloned voice (EN/HI) | Chatterbox on GPU | measured similarity; GPU RTF from research (~0.3-0.6) pending A2 |
| Maximum-fidelity cloning, non-commercial/internal | F5-TTS | measured similarity 0.959; license NC |
| Fast English cloning on modest hardware | StyleTTS 2 | measured (RTF 2.3, sim 0.916) |
| Quality/latency yardstick (never ship) | XTTS v2 | measured; CPML license |

---

## 7. Final engineering answers (measured data only)

**1. Retain:** Kokoro, MeloTTS, Chatterbox, F5-TTS, StyleTTS 2 (all validated);
XTTS v2 as benchmark baseline only; Indic Parler (pending HF token) and Dia
(pending GPU) stay installed; CosyVoice 2 stays a mandatory A2 evaluation
(streaming candidate — blocked by platform, not by merit).

**2. Discard:** OpenVoice V2 (Windows-blocked, no Indic path, timbre-only
cloning), Spark-TTS (unresolved license, EN/ZH only), Seed-TTS (not open).

**3. Primary content-creation engine:** **Chatterbox** — highest measured
speaker similarity among commercially usable models (0.935), passed EN and
native HI, MIT license. Constraint from measurement: CPU RTF 13.5 → content
generation requires the A2 GPU tier (research expectation RTF 0.3-0.6 on
RTX-class, to be verified). F5-TTS measured better similarity (0.959) but
its weights are non-commercial — IndicF5/licensed-F5 remains the upgrade
path to also cover HI/BN cloning.

**4. Primary low-latency Voice-AI engine:** **Kokoro** — the only validated
engine that is real-time on this CPU in Hindi (RTF 0.99) and near-real-time
in English (1.38) at 1.9 GB RAM. Native-streaming engines could not be
measured on this machine; CosyVoice 2 (research: ~150 ms first packet) is
the A2 GPU/WSL candidate to displace or complement Kokoro for cloned-voice
calls.

**5. Can one model satisfy both use cases?** **No — now confirmed by
measurement, not just research.** The measured quality-latency gap is an
order of magnitude: every cloning-capable engine is 2.3×-54× slower than
real time on CPU (and the best cloner among them is the slowest), while the
real-time engines (Kokoro 1.19, MeloTTS 0.91) have no cloning at all. No
installable model closed both gaps on any axis we measured (speed, memory,
language coverage, license).

**6. Optimal dual-model architecture** (unchanged from A1, now evidence-backed):
- **Quality tier:** Chatterbox (EN/HI content, GPU) + F5-lineage for maximum
  fidelity where licensing permits; batch pipeline, caching, watermark-friendly.
- **Real-time tier:** Kokoro today (CPU-cheap, HI/EN persona voices);
  CosyVoice 2/Orpheus to be measured in A2 for cloned-voice streaming.
- **Shared (already built, unchanged):** interfaces, adapters, installer,
  datasets, evaluation, reporting, reference validation, caching, logging.
  A1.5 added zero benchmark-only model code — every integration fix landed
  in production adapters/installer specs.

## Artifacts index

- Installation report: `voice_engine/output/installs/installation_report.{md,json}`
- Validation JSONs + smoke audio: `voice_engine/output/validation/`
- Per-model runs + merged comparison: `voice_engine/output/runs/`
- Audio samples per model: `voice_engine/output/runs/<run>/audio/*.wav` (69 clips) and `voice_engine/output/validation/*-smoke.wav`
- Reference study: `voice_engine/output/validation/reference_study.json`
