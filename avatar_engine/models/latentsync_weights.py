"""LatentSync pretrained-weight manifest, verification, and download (A4.7).

Single source of truth for the checkpoints LatentSync 1.6 needs, taken from
upstream (not guessed): the file list comes from `bytedance/LatentSync`'s
`setup_env.sh`. Mirrors `musetalk_weights.py` — the module owns the **manifest,
download, and verification**, and `build_prefetch_code` fetches every file via
the pinned `huggingface_hub` API (default huggingface.co), idempotent and
hard-validated.

Weights live under `<repo>/checkpoints/`. LatentSync's inference (`stage2_512`,
`cross_attention_dim=384`) loads exactly two explicit checkpoints:

    checkpoints/latentsync_unet.pt   — the lip-sync UNet
    checkpoints/whisper/tiny.pt      — Whisper-tiny audio features

plus a SD VAE it pulls with ``AutoencoderKL.from_pretrained("stabilityai/
sd-vae-ft-mse")`` at load time. We pre-warm that VAE into the HF cache during
the prefetch so a fresh install runs offline. (Face-detection models —
insightface / face-alignment / mediapipe — still auto-download on first
inference, exactly like LivePortrait.)

Exact SHA256 is not published upstream, so verification checks presence + a
non-trivial-size guard against truncated/error downloads.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Minimum bytes a real weight file (.pt/.bin/...) must have — catches
#: truncated / HTML-error downloads without needing exact sizes.
_WEIGHT_MIN_BYTES = 100_000
_WEIGHT_EXTS = (".pth", ".bin", ".pt", ".safetensors")

#: SD VAE that LatentSync loads via AutoencoderKL.from_pretrained at runtime;
#: pre-warmed into the HF cache by the prefetch (not path-validated here).
VAE_REPO_ID = "stabilityai/sd-vae-ft-mse"


@dataclass(frozen=True)
class WeightFile:
    """One LatentSync weight, relative to `<repo>/checkpoints/`.

    ``hf_filename`` is the file's path within the HF repo; ``relpath`` (its path
    under ``checkpoints/``) always ends with ``hf_filename`` so the prefetch can
    derive ``hf_hub_download``'s ``local_dir``.
    """

    relpath: str
    purpose: str
    source: str            # HF repo id it is fetched from (documentation)
    required: bool         # part of the inference set the adapter loads
    repo_id: str | None = None      # HF repo for hf_hub_download
    hf_filename: str | None = None  # path within the HF repo (relpath ends with this)


#: Full inference weight set from setup_env.sh.
LATENTSYNC_WEIGHTS: tuple[WeightFile, ...] = (
    WeightFile("latentsync_unet.pt", "LatentSync 1.6 lip-sync UNet",
               "ByteDance/LatentSync-1.6", True,
               repo_id="ByteDance/LatentSync-1.6", hf_filename="latentsync_unet.pt"),
    WeightFile("whisper/tiny.pt", "Whisper-tiny audio features",
               "ByteDance/LatentSync-1.6", True,
               repo_id="ByteDance/LatentSync-1.6", hf_filename="whisper/tiny.pt"),
)


def weights_root(repo_dir: Path) -> Path:
    return Path(repo_dir) / "checkpoints"


def required_weight_paths(repo_dir: Path) -> list[Path]:
    """Paths the inference needs (used by the adapter's availability check)."""
    root = weights_root(repo_dir)
    return [root / w.relpath for w in LATENTSYNC_WEIGHTS if w.required]


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
        return WeightStatus(w.relpath, w.purpose, w.required, None,
                            "missing", "file not downloaded")
    actual = path.stat().st_size
    is_weight = path.suffix.lower() in _WEIGHT_EXTS
    if is_weight and actual < _WEIGHT_MIN_BYTES:
        return WeightStatus(w.relpath, w.purpose, w.required, actual, "corrupted",
                            f"{actual} bytes < {_WEIGHT_MIN_BYTES} (truncated/incomplete)")
    if not is_weight and actual == 0:
        return WeightStatus(w.relpath, w.purpose, w.required, actual, "corrupted",
                            "empty file")
    return WeightStatus(w.relpath, w.purpose, w.required, actual, "validated",
                        "present and non-trivial size")


def check_weights(repo_dir: Path) -> list[WeightStatus]:
    return [check_weight(repo_dir, w) for w in LATENTSYNC_WEIGHTS]


def all_required_valid(statuses: list[WeightStatus]) -> bool:
    req = [s for s in statuses if s.required]
    return bool(req) and all(s.ok for s in req)


def _download_specs() -> list[dict]:
    """Flat, JSON-safe download coordinates embedded into the prefetch snippet."""
    return [
        {"relpath": w.relpath, "required": w.required,
         "repo_id": w.repo_id, "hf_filename": w.hf_filename}
        for w in LATENTSYNC_WEIGHTS
    ]


def build_prefetch_code(repo_dir: Path) -> str:
    """Self-contained snippet (run inside the LatentSync venv, Linux/Colab) that
    downloads every inference checkpoint straight from this module's manifest.

    Like MuseTalk (A4.4) we do NOT run the repo's ``setup_env.sh`` — it uses the
    deprecated ``huggingface-cli`` and a conda flow. Instead we fetch each file
    with the pinned hub's ``hf_hub_download`` (default huggingface.co) and
    pre-warm the SD VAE with ``snapshot_download`` — idempotent (skips
    already-valid files) and hard-validated (raises if any required checkpoint
    is missing, so a partial download can never be reported as success). uv
    venvs ship no pip, so pip is bootstrapped first.
    """
    repo = Path(repo_dir).as_posix()
    specs_literal = repr(_download_specs())
    return (
        "import os, sys, importlib.util, pathlib\n"
        f"repo = pathlib.Path(r'{repo}')\n"
        "if importlib.util.find_spec('pip') is None:\n"
        "    import ensurepip; ensurepip.bootstrap()\n"
        "from huggingface_hub import hf_hub_download, snapshot_download\n"
        "ckpt = repo / 'checkpoints'\n"
        "ckpt.mkdir(parents=True, exist_ok=True)\n"
        f"specs = {specs_literal}\n"
        f"vae_repo = {VAE_REPO_ID!r}\n"
        "_MIN = 100000\n"
        "_WEXT = ('.pth', '.bin', '.pt', '.safetensors')\n"
        "def _ok(p):\n"
        "    if not p.exists():\n"
        "        return False\n"
        "    sz = p.stat().st_size\n"
        "    return sz >= _MIN if p.suffix.lower() in _WEXT else sz > 0\n"
        "for s in specs:\n"
        "    dest = ckpt / s['relpath']\n"
        "    if _ok(dest):\n"
        "        print('skip (present):', s['relpath']); continue\n"
        "    dest.parent.mkdir(parents=True, exist_ok=True)\n"
        # relpath always ends with hf_filename, so this local_dir lands the file
        # exactly at checkpoints/<relpath> (see WeightFile docstring).
        "    rel, hf = s['relpath'], s['hf_filename']\n"
        "    assert rel.endswith(hf), (rel, hf)\n"
        "    local_dir = ckpt / rel[:len(rel) - len(hf)].rstrip('/')\n"
        "    local_dir.mkdir(parents=True, exist_ok=True)\n"
        "    hf_hub_download(repo_id=s['repo_id'], filename=hf, local_dir=str(local_dir))\n"
        "    print('downloaded:', s['relpath'])\n"
        # Pre-warm the SD VAE into the HF cache (inference loads it via
        # AutoencoderKL.from_pretrained, which reads that cache).
        "snapshot_download(vae_repo, allow_patterns=['config.json',\n"
        "    'diffusion_pytorch_model.safetensors', 'diffusion_pytorch_model.bin'])\n"
        "print('pre-warmed VAE:', vae_repo)\n"
        "missing = [s['relpath'] for s in specs if s['required'] and not _ok(ckpt / s['relpath'])]\n"
        "if missing:\n"
        "    raise RuntimeError('required LatentSync weights missing after download: ' + ', '.join(missing))\n"
        "print('latentsync setup complete')\n"
    )
