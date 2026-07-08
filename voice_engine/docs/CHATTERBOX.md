# Chatterbox Integration (Phase B2.2)

Chatterbox (`ResembleAI/chatterbox`, **Multilingual v2**) is Resemble AI's
0.5B-parameter, Llama-backbone TTS with **zero-shot voice cloning**, a unique
**emotion-exaggeration** control, and native support for **23 languages
including Hindi**. Code + weights are **MIT** (commercial-friendly); all outputs
carry Resemble's imperceptible **PerTh watermark** (provenance for AI-generated
content — a feature for this platform). It is the platform's **content /
quality-and-cloning tier**, complementing Kokoro's real-time branded-voice tier.
It plugs into the Voice Engine exactly like every other model (thin adapter
behind `BaseVoiceAdapter`, install spec, weight manifest, shared benchmark).
No redesign.

## Architecture

- **Adapter** `voice_engine/adapters/chatterbox.py` — `ChatterboxAdapter`. Runs
  **in-process** (the Voice Engine model, unlike the Avatar Engine's subprocess
  dispatch): loads `ChatterboxMultilingualTTS.from_pretrained(device=...)` and,
  per request, clones from the profile's reference audio and writes a 16-bit PCM
  WAV at 24 kHz. Two production languages: English (`en`) and Hindi (`hi`);
  Hinglish routes through the `hi` path. Emotion maps to the `exaggeration` knob
  (0.7 for excited/happy, else 0.5).
- **Weight manifest** `voice_engine/models/chatterbox_weights.py` — the manifest
  + a presence/size verifier and the install prefetch snippet, mirroring
  `kokoro_weights.py` / the Avatar Engine's `*_weights.py` modules.
- **Registry** — the real adapter is registered for `chatterbox`; it is the head
  of the `quality` and `cloning` router tiers (`tts/defaults.yaml`).

## Required weights (authoritative — from upstream)

Taken from `ChatterboxMultilingualTTS.from_pretrained`, which
`snapshot_download`s exactly this `allow_patterns` set for the default v2 model
from the `ResembleAI/chatterbox` HF repo (**not guessed** — verified against
upstream `mtl_tts.py`). Like Kokoro, Chatterbox pulls weights into the **shared
HF cache**, so the verifier resolves each file against the cache
(`try_to_load_from_cache`, offline). Exact SHA256 is not published upstream, so
verification checks presence + a non-trivial-size floor (catches truncated /
HTML-error downloads).

| File | Purpose | Approx size | Required |
|---|---|---:|:--:|
| `t3_mtl23ls_v2.safetensors` | 23-language T3 backbone (0.5B) | ~2.0 GB | ✓ |
| `s3gen.pt` | S3 codec generator/decoder | ~1.0 GB | ✓ |
| `ve.pt` | voice encoder | ~5.4 MB | ✓ |
| `conds.pt` | built-in default voice conditionals | ~105 KB | ✓ |
| `grapheme_mtl_merged_expanded_v1.json` | multilingual grapheme tokenizer | ~68 KB | ✓ |
| `Cangjie5_TC.json` | Chinese (Cangjie) tokenizer table | ~1.8 MB | ✓ |

Total ~3.2 GB. All are required — `from_pretrained` fetches every one.

```bash
.venvs/chatterbox/bin/python -m voice_engine.scripts.validate_chatterbox_weights
```

## Installation

The install spec (`install_specs.py [chatterbox]`) uses the shared installer:
isolated venv + GPU-aware torch, then `chatterbox-tts`, then the manifest
prefetch.

- **torch pinned to `2.6.0` / `torchaudio 2.6.0`** — chatterbox-tts 0.1.7's exact
  `requires_dist` for Python < 3.14. Pre-installing it with the right index means
  the later `chatterbox-tts` pip call finds the pin already satisfied and never
  downgrades/rebuilds torch.
- **GPU-aware index (`cu124`)** — the installer appends the `cu124` wheel index on
  a GPU host and the CPU index otherwise (Phase A3.8). The **Tesla T4 is `sm_75`**,
  supported by torch 2.6.0's cu124 wheels.
- **Manifest-driven prefetch** — the prefetch downloads every weight straight from
  the manifest (huggingface_hub only; **no pip / ensurepip** — the
  LatentSync/Kokoro pip-less-venv lesson) and hard-validates each size, so a fresh
  install is offline-ready and manifest-verified rather than relying on the
  adapter's lazy first-use `snapshot_download`.
- chatterbox-tts pins its own stack in the isolated venv (`transformers==5.2.0`,
  `diffusers==0.29.0`, `numpy<2`, `librosa==0.11.0`, `s3tokenizer`, `gradio`,
  `resemble-perth`, …); isolation keeps those pins from colliding with other
  models.

```bash
python -m voice_engine.scripts.install_models --models chatterbox
```

## GPU requirements & VRAM

- **GPU strongly recommended.** ~6.5 GB VRAM in fp16; CPU inference is far from
  real time (research tier only). Fits comfortably on the **15 GB Tesla T4**.
- Autoregressive token generation → cold start includes weight + codec load.
- CUDA runtime is validated by the smoke test (`torch.cuda.is_available()`,
  device name, total + peak VRAM, and the model's actual device).

## GPU smoke test (B2.2)

The canonical one-command validation after any install — the Voice-Engine GPU
analogue of `smoke_kokoro.py` (CPU) and the Avatar Engine's `smoke_latentsync.py`.
Checks the adapter is importable and CUDA is live, then clones a short line per
language through the real `ChatterboxAdapter`, confirms each WAV decodes, and
reports device / CUDA / VRAM / startup / RTF / output path. Because the human
reference set is gitignored, the smoke test synthesizes its own **self-contained
synthetic reference** (a voice-like multi-harmonic tone) to exercise the voice
encoder + full `generate()` path — quality is not asserted here (that is the
reference-study job), only readability and the GPU path.

```bash
.venvs/chatterbox/bin/python voice_engine/scripts/smoke_chatterbox.py
.venvs/chatterbox/bin/python voice_engine/scripts/smoke_chatterbox.py --languages en
```

- **Expected output:** a `PASSED` banner and readable WAVs at
  `voice_engine/output/smoke/chatterbox_smoke_{en,hi}.wav` (24 kHz). **Exit 0** on
  success.
- **Common failures** (non-zero exit, actionable message):
  - `FAIL: Chatterbox is not installed` (exit 1) → run the installer above.
  - `FAIL: --device cuda requested but torch.cuda.is_available() is False` (exit 1)
    → the venv has a CPU-only torch; reinstall on a GPU host (or pass `--device cpu`).
  - `FAIL: Chatterbox inference failed` / `produced no readable audio` (exit 3).

Flags: `--languages en hi` (default), `--device {cuda,cpu,auto}` (default `cuda`),
`--repeats N` (warm runs, default 1), `--output-dir`.

## Measured GPU performance (Tesla T4)

Measured on the **Colab Tesla T4** (15 GB, driver 580.82, CUDA 13.0) via
`smoke_chatterbox.py`, **torch 2.6.0+cu124**. The synthetic reference exercises
the full clone→generate path; treat these as engineering figures, not a
listening-test result.

| Language | Cold synth¹ | Warm RTF² | Audio | Sample rate |
|---|---|---|---|---|
| English | ~29.3 s | ~1.07 | 5.40 s | 24 kHz |
| Hindi | ~4.1 s | ~1.49 | 3.56 s | 24 kHz |

- **CUDA / device:** `torch.cuda.is_available() == True`; the model's actual
  inference device is **`cuda`** (Tesla T4), not just the requested device.
- **Startup (`adapter.load()`):** **~40 s** cold — loads the 0.5B T3 backbone +
  S3 codec + voice encoder onto the GPU (one-time; includes the first-run
  `spacy_ontonotes` fetch on an un-prefetched machine, now prefetched at install).
- **Peak VRAM:** **~3.5 GB** (`torch.cuda.max_memory_allocated`) — comfortably
  inside the 15 GB T4; matches the ~6.5 GB fp16 research figure once activation
  headroom for longer utterances is included.
- **GPU utilisation:** autoregressive sampling runs at ~22–32 tok/s on the T4
  (see the `Sampling` progress in the smoke log).
- ¹ First call per language (the T3 backbone's first autoregressive run + any
  first-use tokenizer init; excludes weight download, which the installer
  prefetches). ² Mean warm call on a short utterance — Chatterbox is built for
  utterance-scale generation, so fixed per-call overhead inflates RTF on short
  lines; longer narration amortises it (research RTF ~0.3–0.6 on 3060/4070-class).

> **Cloning & emotion quality** are *not* asserted by the smoke test (it clones a
> synthetic tone). The `exaggeration` knob is wired (0.7 for excited/happy, else
> 0.5) and zero-shot cloning runs end-to-end; perceptual quality belongs to the
> reference study / human listening tests (see
> `datasets/reference_audio/README.md`), which need the human reference set.

## Limitations

- **No Bengali** — not in the 23-language list as of early-2026 releases.
- **No official low-latency streaming** — autoregressive generation makes chunked
  streaming *feasible* (community forks), but there is no supported real-time path
  comparable to CosyVoice/XTTS. Treat as a content engine first
  (`StreamingSupport.LIMITED`).
- **Watermark always on** — all outputs carry the PerTh watermark (imperceptible,
  detectable). A provenance feature here, not a bug.
- **Long-form needs sentence chunking** — built for utterance-scale generation.
- **GPU practically required** — ~6.5 GB VRAM; CPU is not production-viable.

## Validation

```bash
.venvs/chatterbox/bin/python -m voice_engine.scripts.validate_chatterbox_weights  # per-weight status
.venvs/chatterbox/bin/python voice_engine/scripts/smoke_chatterbox.py             # end-to-end GPU check
```

The permanent **GPU smoke test** (`smoke_chatterbox.py`, B2.2) is the canonical
one-command validation after any install: it checks the adapter + CUDA and runs
the smallest EN + HI clone through the real `ChatterboxAdapter`, confirming the
output decodes and reporting device / VRAM / RTF. Exit 0 on success.
