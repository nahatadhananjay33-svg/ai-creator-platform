# MuseTalk Integration (Phase A4.0)

MuseTalk (`TMElyralab/MuseTalk`, **v1.5**) is an **audio-driven** lip-sync
model: it animates a source portrait's mouth to driving audio — the same task
shape as SadTalker (`source_image` + `driving_audio` → `GenerationResult`). It
plugs into the existing avatar stack exactly like SadTalker/LivePortrait
(isolated venv, subprocess-dispatch adapter, shared benchmark/evaluation/
reporting). No framework redesign.

## Architecture

- **Adapter** `avatar_engine/models/musetalk.py` — `MuseTalkAdapter`
  (`RUNS_IN_VENV=True`). MuseTalk's inference is **config-yaml driven**, so the
  adapter writes a temporary task YAML (`video_path` = the portrait image,
  `audio_path` = the driving audio, optional `bbox_shift`) and runs the repo's
  `scripts.inference` (v1.5) in MuseTalk's own venv with a sanitized env, then
  returns the produced mp4 as a `GenerationResult`.
- **Weights** `avatar_engine/models/musetalk_weights.py` — the manifest + a
  presence/size verifier and the install prefetch snippet.
- **Registry** — the real adapter replaces the planned placeholder for
  `musetalk`.

## Required weights (authoritative — from upstream)

From `download_weights.sh` and the README (not guessed). Weights live under
`<repo>/models/`. Sizes are not published per-file upstream, so verification
checks presence + a non-trivial-size guard.

| File (under `models/`) | Purpose | Source | v1.5 required |
|---|---|---|:--:|
| `musetalkV15/unet.pth` | MuseTalk v1.5 UNet | `TMElyralab/MuseTalk` | ✓ |
| `musetalkV15/musetalk.json` | UNet config | `TMElyralab/MuseTalk` | ✓ |
| `sd-vae/diffusion_pytorch_model.bin` | SD VAE (ft-mse) | `stabilityai/sd-vae-ft-mse` | ✓ |
| `sd-vae/config.json` | VAE config | `stabilityai/sd-vae-ft-mse` | ✓ |
| `whisper/pytorch_model.bin` | Whisper-tiny audio features | `openai/whisper-tiny` | ✓ |
| `whisper/config.json` · `whisper/preprocessor_config.json` | Whisper config | `openai/whisper-tiny` | ✓ |
| `dwpose/dw-ll_ucoco_384.pth` | DWPose | `yzd-v/DWPose` | ✓ |
| `face-parse-bisent/79999_iter.pth` | Face parsing (BiSeNet) | Google Drive | ✓ |
| `face-parse-bisent/resnet18-5c106cde.pth` | BiSeNet backbone | PyTorch models | ✓ |
| `musetalk/pytorch_model.bin` · `musetalk/musetalk.json` | v1.0 UNet | `TMElyralab/MuseTalk` | — |
| `syncnet/latentsync_syncnet.pt` | SyncNet (training) | `ByteDance/LatentSync` | — |

```bash
python -m avatar_engine.scripts.validate_musetalk_weights   # verified / missing / corrupted
```

## Installation

The install spec (`install_specs.py [musetalk]`) reuses the existing installer:
isolated venv (py3.10), GPU-aware PyTorch (`torch="auto"` → CUDA on a GPU host),
clones `TMElyralab/MuseTalk`, and a `prefetch_code` that:

1. bootstraps pip (uv venvs are pip-less),
2. `mim install`s the MMLab stack (`mmengine`, `mmcv==2.0.1`, `mmdet==3.1.0`,
   `mmpose==1.1.0`) — MuseTalk's documented versions,
3. runs the repo's own `download_weights.sh` (5 HF repos + Google Drive + a
   PyTorch URL — resumable, skips valid files).

```bash
python -m avatar_engine.scripts.install_models --models musetalk
```

## Inference command (upstream v1.5 normal)

```
python -m scripts.inference --inference_config <tmp.yaml> --result_dir <dir> \
  --unet_model_path models/musetalkV15/unet.pth \
  --unet_config models/musetalkV15/musetalk.json --version v15
```

## Benchmark & comparison

MuseTalk runs the **same scenarios, portraits, and Kokoro audio** as SadTalker
(no new dataset). `python -m avatar_engine.scripts.compare_models` now includes
MuseTalk (SadTalker vs LivePortrait vs MuseTalk): generation time, RTF, FPS,
VRAM (peak/avg), GPU util/temp, resolution, duration, output size, success
rate, and the framework's evaluation metrics.

## Limitations

- **Linux/CUDA only.** The MMLab stack (mmcv/mmpose) compiles only on
  Linux + CUDA, so `supported_on_this_platform=False` on native Windows. Runs
  on Colab's T4; the dev host cannot execute it.
- Weights ~10 GB across five sources; the download is delegated to the
  upstream `download_weights.sh` for correctness.
- Per-file SHA256 is not published upstream, so verification is presence +
  size-floor (truncation guard), not an exact hash.
