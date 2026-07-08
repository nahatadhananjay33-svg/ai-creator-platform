# LatentSync Integration (Phase A4.7)

LatentSync (`bytedance/LatentSync`, **1.6**) is a **video-driven** lip-sync
model: it re-syncs a *template video*'s mouth to driving audio (`driving_video`
+ `driving_audio` → `GenerationResult`) — an end-to-end audio-conditioned
latent-diffusion editor (the accuracy counterpart to MuseTalk's real-time
inpainting). It plugs into the existing avatar stack exactly like MuseTalk /
SadTalker / LivePortrait (isolated venv, subprocess-dispatch adapter, shared
benchmark/evaluation/reporting). No framework redesign.

> **Task shape differs from MuseTalk.** MuseTalk animates a still *portrait*
> (`source_image` + `driving_audio`); LatentSync edits an existing *video*
> (`driving_video` + `driving_audio`). `REQUIRED_INPUTS` reflects this.

## Architecture

- **Adapter** `avatar_engine/models/latentsync.py` — `LatentSyncAdapter`
  (`RUNS_IN_VENV=True`). Runs the repo's `scripts.inference` (stage2) in
  LatentSync's own venv with a sanitized env (`cwd=repo` so `scripts.inference`,
  `configs/`, and relative checkpoint paths resolve), then returns the produced
  mp4 as a `GenerationResult`.
- **Weights** `avatar_engine/models/latentsync_weights.py` — the manifest + a
  presence/size verifier and the install prefetch snippet.
- **Registry** — the real adapter replaces the planned placeholder for
  `latentsync`.

## Required weights (authoritative — from upstream)

The file list traces to upstream's `setup_env.sh` (not guessed); each weight
carries structured download coordinates (HF repo + file) in
`latentsync_weights.py`'s manifest, the single source of truth for the
manifest-driven download (see Installation). Weights live under
`<repo>/checkpoints/`. Exact SHA256 is not published upstream, so verification
checks presence + a non-trivial-size guard (`≥ 100 KB`).

| File (under `checkpoints/`) | Purpose | Source | Required |
|---|---|---|:--:|
| `latentsync_unet.pt` | LatentSync 1.6 lip-sync UNet (~5.1 GB) | `ByteDance/LatentSync-1.6` | ✓ |
| `whisper/tiny.pt` | Whisper-tiny audio features (~75 MB) | `ByteDance/LatentSync-1.6` | ✓ |

Plus the SD VAE `stabilityai/sd-vae-ft-mse`, which inference pulls via
`AutoencoderKL.from_pretrained` at load time — pre-warmed into the HF cache by
the prefetch so a fresh install runs offline. (Face-detection models —
insightface / face-alignment / mediapipe — still auto-download on first
inference, exactly like LivePortrait.)

```bash
python -m avatar_engine.scripts.validate_latentsync_weights   # validated / missing / corrupted
```

## Installation

The install spec (`install_specs.py [latentsync]`) reuses the existing
installer: isolated venv (py3.10), GPU-aware PyTorch (`torch="auto"` → the cu121
index on a GPU host), `torch==2.5.1 / torchvision==0.20.1` (upstream's
`requirements.txt` pins — the T4's sm_75 runs those cu121 wheels),
`huggingface_hub==0.30.2` pinned (transformers 4.48 / diffusers 0.32 API),
`setuptools<81` (librosa 0.10.1 imports `pkg_resources`, and uv venvs ship no
setuptools), clones `bytedance/LatentSync`, and a `prefetch_code` that:

1. downloads every inference checkpoint **directly from the manifest** via the
   pinned hub's `hf_hub_download` (default `huggingface.co`),
2. pre-warms the SD VAE with `snapshot_download`,

both idempotent (skips already-valid files) and **hard-validated** (raises if
any required checkpoint is missing, so a partial download can never be reported
as success). No pip is touched — `huggingface_hub` is installed by the pip
groups, and uv venvs ship neither pip nor ensurepip.

> **Why not the repo's `setup_env.sh`?** It uses the deprecated
> `huggingface-cli` and a conda flow. Owning the download from the manifest
> (like MuseTalk A4.4) avoids the CLI-rename / pin-drift breakage.

```bash
python -m avatar_engine.scripts.install_models --models latentsync
```

Downloads ~5.5 GB of checkpoints plus the torch cu121 wheels.

## GPU smoke test (M4)

The canonical one-command GPU validation after any install — checks the
GPU/CUDA runtime, that the adapter + weights are present, then runs the
*smallest possible* inference (the demo template video re-synced to ~1 s of its
own audio, at a low step count) through the real `LatentSyncAdapter` and
confirms the output decodes.

```bash
python avatar_engine/scripts/smoke_latentsync.py
```

- **Expected runtime:** ~2–2.5 min on a Colab T4 (model load + the 256²
  diffusion over ~27 frames; measured ~131 s).
- **Expected output:** a `PASSED` banner and a readable mp4 at
  `avatar_engine/output/smoke/latentsync_smoke.mp4` (~1080×1920 — the mouth is
  diffused at 256² and composited back into the source's native resolution — 25
  fps, ~27 frames), with `device_actual: cuda`. **Exit code 0** on success.
- **Common failures** (non-zero exit, actionable message):
  - `FAIL: LatentSync is not installed — missing repo entrypoint / weights`
    (exit 1) → run the installer above.
  - `FAIL: a CUDA GPU is required but torch.cuda.is_available() is False`
    (exit 1) → no GPU / wrong runtime; select a GPU runtime.
  - `FAIL: LatentSync demo assets not found ...` (exit 2) → the cloned repo is
    incomplete; re-run the installer.
  - `FAIL: LatentSync inference failed: ...` / `output video not decodable`
    (exit 3) → inference ran but produced no readable video.

Flags: `--device {cuda,auto}` (default `cuda`), `--audio-seconds N` (default
`1.0`), `--inference-steps N` (default `4`, low for speed), `--repo-dir`,
`--output-dir`.

## Resolution / precision on the T4 (important)

LatentSync's `scripts/inference.py` gates fp16 on
`torch.cuda.get_device_capability()[0] > 7`, which is **False** for the T4
(compute capability **7.5**), so it forces **fp32**. Upstream's default
`stage2_512` config (512² × 16 frames) in fp32 peaks **>15.7 GB** and OOMs the
T4's 14.56 GB.

The adapter therefore defaults its UNet config to upstream's 256²
`stage2_efficient.yaml` (same 1.6 UNet — `cross_attention_dim 384`,
`sample_size 64`), whose ¼-size activations fit the T4 in fp32. A larger,
fp16-capable GPU (compute ≥ 8) can run the full 512² config:

```python
LatentSyncAdapter(config={"unet_config": "configs/unet/stage2_512.yaml"})
```

## Inference command (upstream stage2)

```
python -m scripts.inference \
  --unet_config_path configs/unet/stage2_efficient.yaml \
  --inference_ckpt_path checkpoints/latentsync_unet.pt \
  --inference_steps 20 --guidance_scale 1.5 --enable_deepcache \
  --video_path <video> --audio_path <audio> --video_out_path <out.mp4>
```

`inference_steps` and `guidance_scale` are configurable via the adapter config
(the smoke test lowers steps for speed).

## Benchmark & comparison

LatentSync runs the **same scenarios and driving inputs** as the other avatar
models via the shared benchmark/evaluation harness — generation time, RTF, FPS,
VRAM (peak/avg), GPU util/temp, resolution, duration, output size, success
rate, and the framework's evaluation metrics.

## Limitations

- **Linux/CUDA only**, and **needs a CUDA GPU** (no CPU inference).
  `supported_on_this_platform=False` on native Windows; the dev host cannot
  execute it — runs on Colab's T4.
- **Not real-time** — a latent-diffusion editor: roughly minutes per minute of
  footage. MuseTalk wins on speed; LatentSync wins on sync accuracy.
- **Mouth-region editor** — it re-syncs an existing video's mouth, it does not
  animate a still portrait.
- **fp32 on the T4** at 256² (see Resolution / precision) — 512² needs an
  fp16-capable GPU.
- **OpenRAIL++ weights** (`ByteDance/LatentSync-1.6`): commercial use allowed,
  subject to responsible-AI restrictions (no deception / impersonation / rights
  violations) — the product needs a documented compliance position.
- Per-file SHA256 is not published upstream, so verification is presence +
  size-floor (truncation guard), not an exact hash.

## Validation

```bash
python -m avatar_engine.scripts.validate_latentsync_weights   # per-weight status
python avatar_engine/scripts/smoke_latentsync.py              # end-to-end GPU check
```

The permanent **GPU smoke test** (`smoke_latentsync.py`, M4) is the canonical
one-command validation after any install: it checks GPU/CUDA + adapter/weights,
runs the smallest inference (demo template video + ~1 s audio) through the real
`LatentSyncAdapter`, and confirms the output decodes. Exit 0 on success. See the
[GPU smoke test](#gpu-smoke-test-m4) section for runtime, output, and failure
messages.
