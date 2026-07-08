# Kokoro Integration (Phase B2.1)

Kokoro (`hexgrad/Kokoro-82M`, **v1.0**) is an 82M-parameter, StyleTTS2-derived
TTS model: exceptional quality-per-parameter, **CPU-real-time**, Apache-2.0
(code + weights). It has **no voice cloning** (curated voice packs) but ships
**native Hindi voices**, which makes it the platform's pragmatic real-time
Voice-AI tier where a *branded* (not cloned) voice is acceptable and GPUs are
scarce. It plugs into the Voice Engine exactly like every other model (thin
adapter behind `BaseVoiceAdapter`, install spec, shared benchmark). No redesign.

## Architecture

- **Adapter** `voice_engine/adapters/kokoro.py` — `KokoroAdapter`. Runs
  **in-process** (the Voice Engine model, unlike the Avatar Engine's subprocess
  dispatch): it builds one `KPipeline` per language lazily and writes a 16-bit
  PCM WAV at 24 kHz. Two production languages: English (`a`) and Hindi (`h`).
- **Weight manifest** `voice_engine/models/kokoro_weights.py` — the manifest +
  a presence/size verifier and the install prefetch snippet. **New in B2.1**,
  mirroring the Avatar Engine's `*_weights.py` modules.
- **Registry** — the real adapter is registered for `kokoro`.

## Required weights (authoritative — from upstream)

Taken from the `hexgrad/Kokoro-82M` HF repo (not guessed). Unlike the Avatar
models (which place weights under `<repo>/checkpoints/`), Kokoro pulls its
weights from the HF Hub into the **shared HF cache** on first use, so the
verifier resolves each file against the cache (`try_to_load_from_cache`,
offline). Exact SHA256 is not published upstream, so verification checks
presence + a non-trivial-size floor.

| File | Purpose | Required |
|---|---|:--:|
| `kokoro-v1_0.pth` | Kokoro 82M model weights (~327 MB) | ✓ |
| `config.json` | model config | ✓ |
| `voices/af_heart.pt` | default English voice pack | ✓ |
| `voices/hf_alpha.pt` | default Hindi voice pack | ✓ |
| `voices/hf_beta.pt` · `voices/hm_omega.pt` · `voices/hm_psi.pt` | extra Hindi voices | — |

```bash
.venvs/kokoro/bin/python -m voice_engine.scripts.validate_kokoro_weights   # validated / missing / corrupted
```

## Installation

The install spec (`install_specs.py [kokoro]`) uses the shared installer:
isolated venv, `kokoro>=0.9`, and — **B2.1 fix** — spaCy's English G2P model
`en_core_web_sm` installed as a **pinned wheel in `pip_groups`** rather than a
runtime `spacy download`. The old prefetch ran `spacy download` at inference
time, which shells out to pip and bootstraps it via `ensurepip`; **uv-created
venvs ship neither pip nor ensurepip**, so that aborted with
`ModuleNotFoundError`. Installing the model as a wheel lets uv place it in the
venv at build time (same lesson as LatentSync: never touch pip/ensurepip in a
prefetch). The prefetch then only *verifies* the model loads and pulls every
weight straight from the manifest (huggingface_hub), so a fresh install is
offline-ready and manifest-verified.

```bash
python -m voice_engine.scripts.install_models --models kokoro
```

CPU-first: Kokoro installs CPU-only PyTorch (`torch 2.x+cpu`) and needs no GPU.

## CPU smoke test (B2.1)

The canonical one-command validation after any install — the voice analogue of
the Avatar Engine's `smoke_*.py`. Checks the adapter is importable, synthesizes
one short line per language through the real `KokoroAdapter`, confirms each WAV
decodes, and reports startup / inference / RTF / memory. **CPU by default** (no
GPU, no Colab).

```bash
.venvs/kokoro/bin/python voice_engine/scripts/smoke_kokoro.py
```

- **Expected output:** a `PASSED` banner and readable WAVs at
  `voice_engine/output/smoke/kokoro_smoke_{en,hi}.wav` (24 kHz). **Exit 0** on
  success.
- **Common failures** (non-zero exit, actionable message):
  - `FAIL: Kokoro is not installed` (exit 1) → run the installer above.
  - `FAIL: Kokoro inference failed` / `produced no readable audio` (exit 3).

Flags: `--languages en hi` (default), `--device {cpu,auto}` (default `cpu`),
`--repeats N` (warm runs, default 2), `--output-dir`.

## Measured CPU performance

Measured on a **Colab CPU runtime — 2 logical cores, torch single-threaded,
torch 2.12.1+cpu** (a deliberately constrained box; treat as a floor):

| Language | Cold synth¹ | Warm RTF² | Audio | Sample rate |
|---|---|---|---|---|
| English | ~17.9 s | ~1.06 | 3.62 s | 24 kHz |
| Hindi | ~10.0 s | ~1.32 | 4.22 s | 24 kHz |

- **Startup:** adapter `load()` is ~0 s; the real one-time cost is the **first**
  synthesis per language (builds the `KPipeline`) — the "cold synth" column.
- **Peak RSS:** ~2.05 GB (from ~25 MB at start).
- ¹ First call per language (pipeline build; excludes weight download, which the
  installer prefetches). ² Mean of 2 warm calls on a short utterance.

> **Real-time caveat.** On this 2-core / 1-thread box, warm RTF sits **~1.1–1.3
> on short lines** — marginally around real-time, not comfortably below. The
> Phase A1.5 report measured **Hindi RTF 0.99** on a faster/more-core CPU. RTF
> is hardware- and thread-bound: give Kokoro more cores (`torch.set_num_threads`)
> or a GPU and it drops well under 1.0. Short utterances also inflate RTF via
> fixed per-call overhead (G2P, concat, WAV write); longer narration amortizes it.

## Limitations

- **No voice cloning** — fixed voice packs only. For cloned/persona voices use
  the content tier (Chatterbox, Phase B2.2).
- **No emotion control** — the emotion manager passes it through as a no-op.
- **Real-time is core-bound** — comfortably sub-1.0 RTF needs ≥4 cores or a GPU;
  on a 2-vCPU box it is borderline (see above).
- **Hindi input is Devanagari** — the `h` G2P expects Devanagari text (the smoke
  test uses it); a Hinglish/romanization front-end is a later milestone.

## Validation

```bash
.venvs/kokoro/bin/python -m voice_engine.scripts.validate_kokoro_weights   # per-weight status
.venvs/kokoro/bin/python voice_engine/scripts/smoke_kokoro.py              # end-to-end CPU check
```

The permanent **CPU smoke test** (`smoke_kokoro.py`, B2.1) is the canonical
one-command validation after any install: it checks the adapter + runs the
smallest EN + HI synthesis through the real `KokoroAdapter` and confirms the
output decodes, reporting RTF/memory. Exit 0 on success.
