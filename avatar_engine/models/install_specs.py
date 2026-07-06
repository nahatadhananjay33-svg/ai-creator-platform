"""Installation specifications for avatar model environments.

Consumed by ``foundation.model_manager.installer.InstallationManager`` —
one venv per model, exactly like the voice engine (these stacks pin
conflicting torch/diffusers versions; isolation is the only sane policy).

Avatar models are repo-clone projects, not pip packages: pip_groups install
the dependency stack, and checkout/checkpoint steps are documented in
``avatar_engine/docs/INSTALLATION.md``. All specs assume a CUDA Linux/WSL2
host — this Windows CPU machine is for research/benchmark scaffolding only
(``supported_on_this_platform`` encodes that honestly, mirroring what Phase
A1.5 learned about native-Windows builds).
"""
from __future__ import annotations

import sys

from foundation.model_manager.installer import REPOS_DIR, InstallSpec
from avatar_engine.models.liveportrait_weights import build_prefetch_code as build_liveportrait_prefetch
from avatar_engine.models.musetalk_weights import build_prefetch_code as build_musetalk_prefetch

_IS_WINDOWS = sys.platform == "win32"
_PLATFORM_CORE = ("pyyaml", "psutil", "numpy", "opencv-python", "imageio-ffmpeg")

_SADTALKER_CKPT_DIR = (REPOS_DIR / "sadtalker" / "checkpoints").as_posix()
#: Minimal checkpoint set for --preprocess crop without the GFPGAN enhancer.
_SADTALKER_PREFETCH = (
    # V002rc repo carries the safetensors checkpoints (verified A3.5; the
    # plain vinthony/SadTalker repo only hosts the mapping files).
    "from huggingface_hub import hf_hub_download; import shutil, pathlib\n"
    f"ckpt = pathlib.Path(r'{_SADTALKER_CKPT_DIR}'); ckpt.mkdir(parents=True, exist_ok=True)\n"
    "for f in ('SadTalker_V0.0.2_256.safetensors', 'mapping_00109-model.pth.tar',\n"
    "          'mapping_00229-model.pth.tar'):\n"
    "    shutil.copyfile(hf_hub_download('vinthony/SadTalker-V002rc', f), ckpt / f)\n"
    "print('sadtalker checkpoints ready')\n"
)

INSTALL_SPECS: dict[str, InstallSpec] = {
    "sadtalker": InstallSpec(
        model_id="sadtalker",
        # py3.10 + torch 2.0.1/torchvision 0.15.2 (A3.5): the newest combo where
        # basicsr's `torchvision.transforms.functional_tensor` import still exists.
        python_version="3.10",
        # GPU-aware (A3.8): the installer appends the cu118 index on a GPU host
        # and the CPU index otherwise — no hardcoded flavor. torch 2.0.1 ships
        # cu118 wheels, which run on the Colab T4.
        torch="auto",
        torch_packages=("torch==2.0.1", "torchvision==0.15.2", "torchaudio==2.0.2"),
        torch_cuda_index="https://download.pytorch.org/whl/cu118",
        pip_groups=(
            ("face-alignment==1.3.5", "imageio", "librosa==0.10.1", "numba", "resampy",
             "pydub", "scipy", "kornia", "yacs", "basicsr==1.4.2", "facexlib", "gfpgan",
             "safetensors", "av", "joblib", "scikit-image", "huggingface_hub",
             # numpy 1.23.5 + numba 0.58.1 (A3.5): torch 2.0.1 needs numpy 1.x,
             # and facexlib still uses np.float (removed in numpy 1.24).
             "numpy==1.23.5", "numba==0.58.1", "llvmlite==0.41.1",
             # setuptools<81 (A3.5): librosa 0.10.1 imports pkg_resources,
             # which setuptools 81+ removed.
             "setuptools<81")
            + _PLATFORM_CORE,
        ),
        verify_imports=("face_alignment", "basicsr", "cv2"),
        git_repo="https://github.com/OpenTalker/SadTalker.git",
        prefetch_code=_SADTALKER_PREFETCH,
        approx_download_gb=3.0,
        platform_notes="run-from-clone project; 256 mode, --preprocess crop, no enhancer "
        "on CPU (the only audio-driven candidate that runs without CUDA)",
    ),
    "liveportrait": InstallSpec(
        model_id="liveportrait",
        python_version="3.10",
        pip_groups=(
            ("onnxruntime", "insightface", "tyro", "rich", "lmdb", "imageio",
             "scikit-image", "albumentations", "pykalman", "ffmpeg-python",
             "huggingface_hub") + _PLATFORM_CORE,
        ),
        verify_imports=("insightface", "cv2"),
        git_repo="https://github.com/KwaiVGI/LivePortrait.git",
        # Downloads the humans-mode pretrained weights (~660 MB) from
        # HF KlingTeam/LivePortrait into pretrained_weights/ (A3.9). Resumable,
        # cached, skips already-valid files (see liveportrait_weights.py).
        prefetch_code=build_liveportrait_prefetch(REPOS_DIR / "liveportrait"),
        approx_download_gb=2.7,
        # GPU-aware (A3.8): CUDA wheels on a GPU host, CPU otherwise. torchvision
        # is required by LivePortrait's transforms.
        torch="auto",
        torch_packages=("torch", "torchvision", "torchaudio"),
        platform_notes="insightface pip is an sdist needing MSVC on Windows — install may "
        "fail without build tools. COMMERCIAL BLOCKER: InsightFace models are "
        "research-only; replace detection before production use.",
    ),
    "musetalk": InstallSpec(
        model_id="musetalk",
        python_version="3.10",
        pip_groups=(
            ("diffusers>=0.30", "transformers", "accelerate", "omegaconf", "soundfile",
             "librosa", "einops", "gdown", "requests", "huggingface_hub[cli]",
             "openmim") + _PLATFORM_CORE,
        ),
        # verify_imports runs BEFORE git clone + prefetch_code, so it must only
        # list packages the pip_groups install. mmpose/mmcv are installed by the
        # prefetch (via `mim`), so they are NOT verified here — otherwise the
        # install aborts before cloning the repo and downloading weights. The
        # adapter's IMPORT_PACKAGES still verifies mmpose at runtime.
        verify_imports=("diffusers", "cv2"),
        git_repo="https://github.com/TMElyralab/MuseTalk.git",
        # Installs the MMLab stack (mim) and downloads all weights via the repo's
        # own download_weights.sh (5 HF repos + gdrive + a PyTorch URL). A4.0.
        prefetch_code=build_musetalk_prefetch(REPOS_DIR / "musetalk"),
        approx_download_gb=10.0,
        # GPU-aware (A3.8): CUDA wheels on a GPU host, CPU otherwise.
        torch="auto",
        torch_packages=("torch", "torchvision", "torchaudio"),
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="mmcv/mmpose compile only on Linux/CUDA (Colab). The installer "
        "runs `mim install` for mmengine/mmcv/mmdet/mmpose and the repo's "
        "download_weights.sh; native Windows is unsupported.",
    ),
    "latentsync": InstallSpec(
        model_id="latentsync",
        pip_groups=(
            ("diffusers", "transformers", "accelerate", "decord", "einops",
             "omegaconf", "soundfile", "librosa") + _PLATFORM_CORE,
        ),
        verify_imports=("diffusers", "cv2"),
        approx_download_gb=12.0,
        torch="cuda",
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="clone bytedance/LatentSync; setup_env.sh pulls checkpoints from HF "
        "ByteDance/LatentSync-1.6; needs ffmpeg on PATH",
    ),
    "echomimic-v3": InstallSpec(
        model_id="echomimic-v3",
        pip_groups=(
            ("diffusers", "transformers", "accelerate", "einops", "omegaconf",
             "soundfile", "librosa", "moviepy") + _PLATFORM_CORE,
        ),
        verify_imports=("diffusers", "cv2"),
        approx_download_gb=8.0,
        torch="cuda",
        platform_notes="clone antgroup/echomimic_v3; weights from HF BadToBest/EchoMimicV3; "
        "12 GB VRAM for 768x768, 6.5 GB for 768x512",
    ),
    "echomimic-v2": InstallSpec(
        model_id="echomimic-v2",
        pip_groups=(
            ("diffusers", "transformers", "accelerate", "einops", "omegaconf",
             "soundfile", "librosa", "moviepy") + _PLATFORM_CORE,
        ),
        verify_imports=("diffusers", "cv2"),
        approx_download_gb=15.0,
        torch="cuda",
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="16 GB VRAM practical floor; clone antgroup/echomimic_v2",
    ),
    "ditto": InstallSpec(
        model_id="ditto",
        pip_groups=(
            ("tensorrt", "onnx", "librosa", "soundfile", "einops") + _PLATFORM_CORE,
        ),
        verify_imports=("cv2",),
        approx_download_gb=6.0,
        torch="cuda",
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="TensorRT engines must be built per-GPU; clone "
        "antgroup/ditto-talkinghead; PyTorch fallback exists but loses real-time",
    ),
    "hallo2": InstallSpec(
        model_id="hallo2",
        pip_groups=(
            ("diffusers==0.27.2", "transformers", "accelerate", "insightface",
             "audio-separator", "einops", "omegaconf", "soundfile", "librosa") + _PLATFORM_CORE,
        ),
        verify_imports=("diffusers", "insightface"),
        approx_download_gb=20.0,
        torch="cuda",
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="clone fudan-generative-vision/hallo2; large checkpoint set from HF "
        "fudan-generative-ai/hallo2; 16 GB+ VRAM",
    ),
    "memo": InstallSpec(
        model_id="memo",
        pip_groups=(
            ("diffusers", "transformers", "accelerate", "einops", "omegaconf",
             "soundfile", "librosa") + _PLATFORM_CORE,
        ),
        verify_imports=("diffusers", "cv2"),
        approx_download_gb=20.0,
        torch="cuda",
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="clone memoavatar/memo; weights auto-download from HF memoavatar/memo",
    ),
    "infinitetalk": InstallSpec(
        model_id="infinitetalk",
        pip_groups=(
            ("transformers", "accelerate", "einops", "omegaconf", "soundfile",
             "librosa", "xfuser") + _PLATFORM_CORE,
            ("flash-attn",),  # compiled; Linux only in practice
        ),
        verify_imports=("transformers", "cv2"),
        approx_download_gb=60.0,
        torch="cuda",
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="Wan2.1-I2V-14B stack: clone MeiGen-AI/InfiniteTalk, download "
        "Wan2.1-I2V-14B-480P + chinese-wav2vec2-base + InfiniteTalk weights; "
        "flash-attn requires a CUDA build toolchain",
    ),
    "fantasy-talking": InstallSpec(
        model_id="fantasy-talking",
        pip_groups=(
            ("transformers", "accelerate", "einops", "omegaconf", "soundfile",
             "librosa") + _PLATFORM_CORE,
        ),
        verify_imports=("transformers", "cv2"),
        approx_download_gb=40.0,
        torch="cuda",
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="Wan2.1 stack; low-VRAM offload documented down to ~5 GB "
        "at a heavy speed cost",
    ),
    "omniavatar": InstallSpec(
        model_id="omniavatar",
        pip_groups=(
            ("transformers", "accelerate", "einops", "omegaconf", "soundfile",
             "librosa") + _PLATFORM_CORE,
        ),
        verify_imports=("transformers", "cv2"),
        approx_download_gb=40.0,
        torch="cuda",
        supported_on_this_platform=not _IS_WINDOWS,
        platform_notes="Wan2.1 stack; 1.3B variant lowers VRAM floor to ~8 GB",
    ),
}
