# Avatar Model Installation

> **MuseTalk (Phase A4.0, download hardened A4.4).** `install_models --models
> musetalk` clones `TMElyralab/MuseTalk`, pre-installs `chumpy` +
> `mim install`s the MMLab stack, and downloads ~10 GB of weights **from the
> manifest** — pinned `huggingface_hub==0.30.2` `hf_hub_download` (default
> `huggingface.co`) + `gdown` + `urllib`, idempotent and hard-validated (not the
> repo's `download_weights.sh`, which corrupted the hub pin and forced a broken
> mirror). Verify weights with
> `python -m avatar_engine.scripts.validate_musetalk_weights`, then validate the
> GPU end-to-end with `python avatar_engine/scripts/smoke_musetalk.py` (smallest
> inference → mp4; exit 0 on success — see
> [`MUSE_TALK.md`](MUSE_TALK.md#gpu-smoke-test-phase-a45)).
> **Linux/CUDA only** (mmcv/mmpose) — runs on Colab, not native Windows. It is
> audio-driven like SadTalker (portrait + audio). See
> [`MUSE_TALK.md`](MUSE_TALK.md).

> **LivePortrait weights (Phase A3.9).** The installer now auto-downloads
> LivePortrait's 8 humans-mode pretrained weights (~660 MB) from HF
> `KlingTeam/LivePortrait` into `pretrained_weights/` via the spec's
> `prefetch_code` (resumable, cached, skips already-valid files). The manifest
> (filenames, purpose, size) lives in `avatar_engine/models/liveportrait_weights.py`.
> Verify per-weight status with
> `python -m avatar_engine.scripts.validate_liveportrait_weights`
> (validated / missing / corrupted / checksum_mismatch). LivePortrait is
> **video-driven**: it needs a `driving_video.mp4` in the assets dir (the Colab
> notebook seeds one from LivePortrait's example clips); without it the
> benchmark records those scenarios SKIPPED with a clear reason.

> **GPU enablement (Phase A3.8).** The installer now auto-selects the PyTorch
> flavor per host: **CUDA wheels when a capable GPU is present** (a detected
> GPU + a driver ≥ the CUDA 11.8 floor), **CPU wheels otherwise** — decided by
> `EnvironmentReport.gpu_install_target`, which does not need torch in the
> launcher (so it works in the Colab main kernel). No spec hardcodes a CPU
> index anymore; version-pinned models (SadTalker: torch 2.0.1) carry a
> `torch_cuda_index` (cu118) the installer appends on a GPU host. New avatar
> specs inherit this automatically (default `torch="auto"`). Verify with
> `python -m avatar_engine.scripts.validate_adapters` — it reports
> `torch.cuda.is_available()`, the GPU name, and VRAM inside each venv.

> **Phase A3.5 verified status (this Windows/CPU host).** Install with
> `python -m avatar_engine.scripts.install_models --models <ids>` — repo
> clones and checkpoint prefetch are now automated (`git_repo` +
> `prefetch_code` in install_specs.py; shared CLI in
> `foundation.model_manager.install_cli`).
>
> | Model | Verified outcome |
> |---|---|
> | SadTalker | ✅ installed + **generates video on CPU** (256², validated). Pins found empirically: torch 2.0.1/tv 0.15.2, numpy 1.23.5 + numba 0.58.1 (facexlib `np.float`), setuptools<81 (librosa needs pkg_resources), checkpoints from HF `vinthony/SadTalker-V002rc` |
> | LivePortrait | ⚠️ installed (insightface built OK); CPU generation **timed out at 60 min** for a ~5 s clip — GPU required |
> | EchoMimic V3 | ⏸ deps installable, inference Not Tested — video-diffusion DiT is not CPU-viable; needs the A4 GPU box |
> | MuseTalk, LatentSync, EchoMimic V2, Ditto, Hallo2, MEMO, InfiniteTalk, FantasyTalking, OmniAvatar | ❌ Not Supported on native Windows (compiled deps / Wan-14B VRAM floor) — WSL2/Linux GPU |
>
> All model repos and venvs live under `.venvs/_repos/` and `.venvs/`;
> FFmpeg is auto-pathed by `foundation.shared_utils.ffmpeg`.

One venv per model under `.venvs/`, driven by
`foundation.model_manager.InstallationManager` with the specs in
`avatar_engine/models/install_specs.py` — the exact policy Phase A1.5
proved out for voice models (conflicting torch/diffusers pins make shared
environments impossible).

## Platform reality check

Almost every avatar candidate is **Linux/WSL2-first**:

- `mmcv/mmpose` (MuseTalk), `flash-attn` (Wan family), TensorRT (Ditto)
  are compiled dependencies that fail or fight on native Windows.
- Specs encode this via `supported_on_this_platform` so the installer
  reports blockers honestly instead of burning hours (the A1.5 lesson).
- On this machine only SadTalker and LivePortrait have realistic native
  Windows paths; everything else expects WSL2 or a Linux GPU box.

## Install flow (GPU machine, Phase A4)

```python
from foundation.model_manager.installer import InstallationManager
from avatar_engine.models.install_specs import INSTALL_SPECS

manager = InstallationManager()
result = manager.install(INSTALL_SPECS["echomimic-v3"])
print(result.status, result.error)
```

Unlike voice models (pip packages), avatar models are **repo-clone
projects**: the venv carries the dependency stack; the repo checkout and
checkpoint downloads are separate steps listed in each spec's
`platform_notes`. Keep checkouts under `.venvs/_repos/<model-id>/`.

## Checkpoint logistics

| Model | Weights source | Notes |
|---|---|---|
| SadTalker | HF `vinthony/SadTalker` | `scripts/download_models.sh` |
| LivePortrait | HF `KwaiVGI/LivePortrait` | InsightFace models auto-fetched — research-only, replace for production |
| MuseTalk | HF `TMElyralab/MuseTalk` | manifest-driven download (pinned `hf_hub_download` + gdown + urllib, hard-validated); also sd-vae, whisper-tiny, DWPose, BiSeNet |
| LatentSync | HF `ByteDance/LatentSync-1.6` | `setup_env.sh` |
| EchoMimic v2/v3 | HF `BadToBest/EchoMimicV2` / `V3` | plus base SD/Wan components per README |
| Ditto | HF `digital-avatar/ditto-talkinghead` | TensorRT engine build per GPU |
| Hallo2 | HF `fudan-generative-ai/hallo2` | large multi-checkpoint set |
| MEMO | HF `memoavatar/memo` | auto-download on first run |
| InfiniteTalk | HF `MeiGen-AI/InfiniteTalk` + `Wan-AI/Wan2.1-I2V-14B-480P` + `TencentGameMate/chinese-wav2vec2-base` | ~60 GB total |

## Disk budget

Full roster ≈ **190 GB** of weights/repos. Prioritize: SadTalker,
EchoMimicV3, LatentSync, MuseTalk, LivePortrait (~35 GB) cover the
recommended shortlist; add InfiniteTalk only on the hero-content track.
