# Avatar Model Installation

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
| MuseTalk | HF `TMElyralab/MuseTalk` | `download_weights.sh`; also whisper-tiny, sd-vae |
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
