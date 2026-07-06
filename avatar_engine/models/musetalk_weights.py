"""MuseTalk pretrained-weight manifest, verification, and download (A4.0).

Single source of truth for the weights MuseTalk needs, taken from upstream (not
guessed): the file list and sources come from `TMElyralab/MuseTalk`'s
`download_weights.sh` and README (v1.5). Mirrors `liveportrait_weights.py`.

Weights live under `<repo>/models/` and come from several sources (five HF
repos + Google Drive + a PyTorch URL), so the download is delegated to the
repo's own authoritative `download_weights.sh` (via `build_prefetch_code`).
This module owns the **manifest + verification** used by the adapter, the
diagnostics, and `validate_musetalk_weights.py`.

Exact SHA256 is not published upstream, so verification checks presence + a
non-trivial-size guard against truncated/error downloads (like LivePortrait's
size-band guard).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Minimum bytes a real weight file (.pth/.bin/.pt) must have — catches
#: truncated / HTML-error downloads without needing exact sizes.
_WEIGHT_MIN_BYTES = 100_000
_WEIGHT_EXTS = (".pth", ".bin", ".pt", ".safetensors")


@dataclass(frozen=True)
class WeightFile:
    """One MuseTalk weight, relative to `<repo>/models/`."""

    relpath: str
    purpose: str
    source: str            # HF repo id / URL it is fetched from (documentation)
    required_for_v15: bool  # part of the v1.5 inference set the adapter checks


#: Full weight set from download_weights.sh. `required_for_v15` marks the files
#: the v1.5 inference path (the one the adapter runs) actually loads.
MUSETALK_WEIGHTS: tuple[WeightFile, ...] = (
    # MuseTalk v1.5 core (what the adapter's --version v15 inference uses)
    WeightFile("musetalkV15/unet.pth", "MuseTalk v1.5 UNet",
               "TMElyralab/MuseTalk", True),
    WeightFile("musetalkV15/musetalk.json", "MuseTalk v1.5 UNet config",
               "TMElyralab/MuseTalk", True),
    # VAE / audio / pose / face-parsing dependencies
    WeightFile("sd-vae/diffusion_pytorch_model.bin", "SD VAE (ft-mse)",
               "stabilityai/sd-vae-ft-mse", True),
    WeightFile("sd-vae/config.json", "SD VAE config",
               "stabilityai/sd-vae-ft-mse", True),
    WeightFile("whisper/pytorch_model.bin", "Whisper-tiny audio features",
               "openai/whisper-tiny", True),
    WeightFile("whisper/config.json", "Whisper config",
               "openai/whisper-tiny", True),
    WeightFile("whisper/preprocessor_config.json", "Whisper preprocessor config",
               "openai/whisper-tiny", True),
    WeightFile("dwpose/dw-ll_ucoco_384.pth", "DWPose body/face pose",
               "yzd-v/DWPose", True),
    WeightFile("face-parse-bisent/79999_iter.pth", "Face parsing (BiSeNet)",
               "Google Drive (154JgKpzCPW82qINcVieuPH3fZ2e0P812)", True),
    WeightFile("face-parse-bisent/resnet18-5c106cde.pth", "BiSeNet ResNet-18 backbone",
               "https://download.pytorch.org/models/resnet18-5c106cde.pth", True),
    # v1.0 + training weights (present after download_weights.sh; not needed by v15 infer)
    WeightFile("musetalk/pytorch_model.bin", "MuseTalk v1.0 UNet",
               "TMElyralab/MuseTalk", False),
    WeightFile("musetalk/musetalk.json", "MuseTalk v1.0 config",
               "TMElyralab/MuseTalk", False),
    WeightFile("syncnet/latentsync_syncnet.pt", "SyncNet (training/eval)",
               "ByteDance/LatentSync", False),
)


def weights_root(repo_dir: Path) -> Path:
    return Path(repo_dir) / "models"


def required_weight_paths(repo_dir: Path) -> list[Path]:
    """Paths the v1.5 inference needs (used by the adapter's availability check)."""
    root = weights_root(repo_dir)
    return [root / w.relpath for w in MUSETALK_WEIGHTS if w.required_for_v15]


@dataclass
class WeightStatus:
    relpath: str
    purpose: str
    required: bool
    actual_bytes: int | None
    status: str   # "validated" | "missing" | "corrupted"
    reason: str

    @property
    def ok(self) -> bool:
        return self.status == "validated"

    def to_dict(self) -> dict:
        return {
            "relpath": self.relpath, "purpose": self.purpose, "required": self.required,
            "actual_bytes": self.actual_bytes, "status": self.status,
            "reason": self.reason, "ok": self.ok,
        }


def check_weight(repo_dir: Path, w: WeightFile) -> WeightStatus:
    path = weights_root(repo_dir) / w.relpath
    if not path.exists():
        return WeightStatus(w.relpath, w.purpose, w.required_for_v15, None,
                            "missing", "file not downloaded")
    actual = path.stat().st_size
    is_weight = path.suffix.lower() in _WEIGHT_EXTS
    if is_weight and actual < _WEIGHT_MIN_BYTES:
        return WeightStatus(w.relpath, w.purpose, w.required_for_v15, actual, "corrupted",
                            f"{actual} bytes < {_WEIGHT_MIN_BYTES} (truncated/incomplete)")
    if not is_weight and actual == 0:
        return WeightStatus(w.relpath, w.purpose, w.required_for_v15, actual, "corrupted",
                            "empty config file")
    return WeightStatus(w.relpath, w.purpose, w.required_for_v15, actual, "validated",
                        "present and non-trivial size")


def check_weights(repo_dir: Path) -> list[WeightStatus]:
    return [check_weight(repo_dir, w) for w in MUSETALK_WEIGHTS]


def all_required_valid(statuses: list[WeightStatus]) -> bool:
    req = [s for s in statuses if s.required]
    return bool(req) and all(s.ok for s in req)


def build_prefetch_code(repo_dir: Path) -> str:
    """Self-contained snippet (run inside the MuseTalk venv, Linux/Colab) that
    installs the MMLab stack via openmim and downloads all weights via the
    repo's own authoritative `download_weights.sh`.

    uv venvs ship no pip, so pip is bootstrapped first. Delegating the download
    to the upstream script (5 HF repos + Google Drive + a PyTorch URL) avoids
    re-implementing multi-source download logic.
    """
    repo = Path(repo_dir).as_posix()
    return (
        "import os, sys, subprocess, importlib.util, pathlib\n"
        f"repo = pathlib.Path(r'{repo}')\n"
        "os.chdir(repo)\n"
        "if importlib.util.find_spec('pip') is None:\n"
        "    import ensurepip; ensurepip.bootstrap()\n"
        # MMLab stack (MuseTalk's documented versions) via openmim.
        "subprocess.run([sys.executable, '-m', 'pip', 'install', '-U', 'openmim'], check=True)\n"
        "for pkg in ('mmengine', 'mmcv==2.0.1', 'mmdet==3.1.0', 'mmpose==1.1.0'):\n"
        "    subprocess.run([sys.executable, '-m', 'mim', 'install', pkg], check=True)\n"
        # Authoritative weight download (idempotent; hf/gdown skip valid files).
        "dl = repo / 'download_weights.sh'\n"
        "if dl.exists():\n"
        "    subprocess.run(['bash', str(dl)], check=True)\n"
        "else:\n"
        "    print('WARNING: download_weights.sh not found in repo')\n"
        "print('musetalk setup complete')\n"
    )
