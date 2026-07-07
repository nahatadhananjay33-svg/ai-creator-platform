"""MuseTalk pretrained-weight manifest, verification, and download (A4.0).

Single source of truth for the weights MuseTalk needs, taken from upstream (not
guessed): the file list and sources come from `TMElyralab/MuseTalk`'s
`download_weights.sh` and README (v1.5). Mirrors `liveportrait_weights.py`.

Weights live under `<repo>/models/` and come from several sources (five HF
repos + Google Drive + a PyTorch URL). This module owns the **manifest,
download, and verification** used by the adapter, the diagnostics, and
`validate_musetalk_weights.py`: each `WeightFile` carries structured download
coordinates, and `build_prefetch_code` fetches every file directly from them
(pinned `hf_hub_download` + `gdown` + `urllib`). The mapping still traces to
upstream's `download_weights.sh`, but we no longer *run* that script — it
upgraded `huggingface_hub` past our runtime pin, forced an unreliable mirror,
and swallowed failures (A4.4).

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
    """One MuseTalk weight, relative to `<repo>/models/`.

    Download coordinates (``repo_id``/``hf_filename`` | ``gdrive_id`` | ``url``)
    make this manifest the single source of truth for the prefetch download,
    which owns the fetch itself (A4.4) rather than delegating to upstream's
    ``download_weights.sh`` — that script upgraded ``huggingface_hub`` past our
    runtime pin, forced an unreliable mirror, and swallowed failures.
    ``hf_filename`` is the file's path *within* the HF repo; ``relpath`` (its
    path under ``models/``) always ends with ``hf_filename`` so the prefetch can
    derive ``hf_hub_download``'s ``local_dir``.
    """

    relpath: str
    purpose: str
    source: str            # HF repo id / URL it is fetched from (documentation)
    required_for_v15: bool  # part of the v1.5 inference set the adapter checks
    repo_id: str | None = None      # HF repo for hf_hub_download
    hf_filename: str | None = None  # path within the HF repo (relpath ends with this)
    gdrive_id: str | None = None    # Google Drive file id (gdown)
    url: str | None = None          # direct download URL (urllib)


#: Full weight set from download_weights.sh. `required_for_v15` marks the files
#: the v1.5 inference path (the one the adapter runs) actually loads.
MUSETALK_WEIGHTS: tuple[WeightFile, ...] = (
    # MuseTalk v1.5 core (what the adapter's --version v15 inference uses)
    WeightFile("musetalkV15/unet.pth", "MuseTalk v1.5 UNet",
               "TMElyralab/MuseTalk", True,
               repo_id="TMElyralab/MuseTalk", hf_filename="musetalkV15/unet.pth"),
    WeightFile("musetalkV15/musetalk.json", "MuseTalk v1.5 UNet config",
               "TMElyralab/MuseTalk", True,
               repo_id="TMElyralab/MuseTalk", hf_filename="musetalkV15/musetalk.json"),
    # VAE / audio / pose / face-parsing dependencies
    WeightFile("sd-vae/diffusion_pytorch_model.bin", "SD VAE (ft-mse)",
               "stabilityai/sd-vae-ft-mse", True,
               repo_id="stabilityai/sd-vae-ft-mse", hf_filename="diffusion_pytorch_model.bin"),
    WeightFile("sd-vae/config.json", "SD VAE config",
               "stabilityai/sd-vae-ft-mse", True,
               repo_id="stabilityai/sd-vae-ft-mse", hf_filename="config.json"),
    WeightFile("whisper/pytorch_model.bin", "Whisper-tiny audio features",
               "openai/whisper-tiny", True,
               repo_id="openai/whisper-tiny", hf_filename="pytorch_model.bin"),
    WeightFile("whisper/config.json", "Whisper config",
               "openai/whisper-tiny", True,
               repo_id="openai/whisper-tiny", hf_filename="config.json"),
    WeightFile("whisper/preprocessor_config.json", "Whisper preprocessor config",
               "openai/whisper-tiny", True,
               repo_id="openai/whisper-tiny", hf_filename="preprocessor_config.json"),
    WeightFile("dwpose/dw-ll_ucoco_384.pth", "DWPose body/face pose",
               "yzd-v/DWPose", True,
               repo_id="yzd-v/DWPose", hf_filename="dw-ll_ucoco_384.pth"),
    WeightFile("face-parse-bisent/79999_iter.pth", "Face parsing (BiSeNet)",
               "Google Drive (154JgKpzCPW82qINcVieuPH3fZ2e0P812)", True,
               gdrive_id="154JgKpzCPW82qINcVieuPH3fZ2e0P812"),
    WeightFile("face-parse-bisent/resnet18-5c106cde.pth", "BiSeNet ResNet-18 backbone",
               "https://download.pytorch.org/models/resnet18-5c106cde.pth", True,
               url="https://download.pytorch.org/models/resnet18-5c106cde.pth"),
    # v1.0 + training weights (fetched too; not needed by v15 inference)
    WeightFile("musetalk/pytorch_model.bin", "MuseTalk v1.0 UNet",
               "TMElyralab/MuseTalk", False,
               repo_id="TMElyralab/MuseTalk", hf_filename="musetalk/pytorch_model.bin"),
    WeightFile("musetalk/musetalk.json", "MuseTalk v1.0 config",
               "TMElyralab/MuseTalk", False,
               repo_id="TMElyralab/MuseTalk", hf_filename="musetalk/musetalk.json"),
    WeightFile("syncnet/latentsync_syncnet.pt", "SyncNet (training/eval)",
               "ByteDance/LatentSync", False,
               repo_id="ByteDance/LatentSync", hf_filename="latentsync_syncnet.pt"),
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


def _download_specs() -> list[dict]:
    """Flat, JSON-safe download coordinates embedded into the prefetch snippet."""
    return [
        {"relpath": w.relpath, "required": w.required_for_v15,
         "repo_id": w.repo_id, "hf_filename": w.hf_filename,
         "gdrive_id": w.gdrive_id, "url": w.url}
        for w in MUSETALK_WEIGHTS
    ]


def build_prefetch_code(repo_dir: Path) -> str:
    """Self-contained snippet (run inside the MuseTalk venv, Linux/Colab) that
    installs the MMLab stack via openmim and downloads every weight straight from
    this module's manifest.

    We deliberately do NOT delegate to the repo's ``download_weights.sh`` (A4.4):
    that script runs ``pip install -U "huggingface_hub[cli]"`` — which upgrades
    ``huggingface_hub`` past our pinned 0.30.2 (renaming ``huggingface-cli`` to
    ``hf`` so every download exits 1, and breaking the transformers/diffusers
    runtime pin) — forces ``HF_ENDPOINT=hf-mirror.com`` (which fails to serve the
    files here), and lacks ``set -e`` so it exits 0 after downloading nothing.
    Instead we fetch each file with the pinned hub's ``hf_hub_download`` (default
    huggingface.co), ``gdown`` for the Google-Drive file, and ``urllib`` for the
    PyTorch URL — idempotent (skips already-valid files) and hard-validated
    (raises if any required weight is missing, so a partial download can never be
    reported as success). uv venvs ship no pip, so pip is bootstrapped first.
    """
    repo = Path(repo_dir).as_posix()
    specs_literal = repr(_download_specs())
    return (
        "import os, sys, subprocess, importlib.util, pathlib, urllib.request\n"
        f"repo = pathlib.Path(r'{repo}')\n"
        "os.chdir(repo)\n"
        # uv venvs aren't activated, so the venv console scripts (mim) aren't on
        # PATH. Put the venv bin first so `mim` resolves.
        "bindir = str(pathlib.Path(sys.executable).parent)\n"
        "env = dict(os.environ)\n"
        "env['PATH'] = bindir + os.pathsep + env.get('PATH', '')\n"
        "if importlib.util.find_spec('pip') is None:\n"
        "    import ensurepip; ensurepip.bootstrap()\n"
        # MMLab stack (MuseTalk's documented versions) via openmim.
        "subprocess.run([sys.executable, '-m', 'pip', 'install', '-U', 'openmim'], check=True, env=env)\n"
        # mmpose 1.1.0 hard-depends on chumpy 0.70, whose sdist has no wheel and
        # whose setup.py does `from pip._internal.req import parse_requirements`
        # at build time. Under PEP517 build isolation the build env carries only
        # setuptools+wheel (never pip), so the import raises and `mim install
        # mmpose` dies with "ModuleNotFoundError: No module named 'pip'" — masked
        # by pip 26 as "checkpoint prefetch failed: ... No available output".
        # Pre-install chumpy with --no-build-isolation so its setup.py sees the
        # venv's pip; that path also needs `wheel` in the venv (uv venvs omit it,
        # and setuptools<70 is already pinned in the pip_groups). Once chumpy is
        # present, `mim install mmpose==1.1.0` finds it satisfied and skips the
        # broken build. (A4.4)
        "subprocess.run([sys.executable, '-m', 'pip', 'install', 'wheel'], check=True, env=env)\n"
        "subprocess.run([sys.executable, '-m', 'pip', 'install', 'chumpy==0.70',\n"
        "                '--no-build-isolation'], check=True, env=env)\n"
        "mim = os.path.join(bindir, 'mim')\n"
        "for pkg in ('mmengine', 'mmcv==2.0.1', 'mmdet==3.1.0', 'mmpose==1.1.0'):\n"
        "    subprocess.run([mim, 'install', pkg], check=True, env=env)\n"
        # ---- manifest-driven weight download (idempotent + hard-validated) ----
        "from huggingface_hub import hf_hub_download\n"
        "try:\n"
        "    import gdown\n"
        "except Exception:\n"
        "    gdown = None\n"
        "models = repo / 'models'\n"
        "models.mkdir(parents=True, exist_ok=True)\n"
        f"specs = {specs_literal}\n"
        "_MIN = 100000\n"
        "_WEXT = ('.pth', '.bin', '.pt', '.safetensors')\n"
        "def _ok(p):\n"
        "    if not p.exists():\n"
        "        return False\n"
        "    sz = p.stat().st_size\n"
        "    return sz >= _MIN if p.suffix.lower() in _WEXT else sz > 0\n"
        "for s in specs:\n"
        "    dest = models / s['relpath']\n"
        "    if _ok(dest):\n"
        "        print('skip (present):', s['relpath']); continue\n"
        "    dest.parent.mkdir(parents=True, exist_ok=True)\n"
        "    if s['repo_id']:\n"
        # relpath always ends with hf_filename, so this local_dir lands the file
        # exactly at models/<relpath> (see WeightFile docstring).
        "        rel, hf = s['relpath'], s['hf_filename']\n"
        "        assert rel.endswith(hf), (rel, hf)\n"
        "        local_dir = models / rel[:len(rel) - len(hf)].rstrip('/')\n"
        "        local_dir.mkdir(parents=True, exist_ok=True)\n"
        "        hf_hub_download(repo_id=s['repo_id'], filename=hf, local_dir=str(local_dir))\n"
        "    elif s['gdrive_id']:\n"
        "        if gdown is None:\n"
        "            raise RuntimeError('gdown not installed for ' + s['relpath'])\n"
        "        gdown.download(id=s['gdrive_id'], output=str(dest), quiet=False)\n"
        "    elif s['url']:\n"
        "        urllib.request.urlretrieve(s['url'], str(dest))\n"
        "    else:\n"
        "        raise RuntimeError('no download source for ' + s['relpath'])\n"
        "    print('downloaded:', s['relpath'])\n"
        "missing = [s['relpath'] for s in specs if s['required'] and not _ok(models / s['relpath'])]\n"
        "if missing:\n"
        "    raise RuntimeError('required MuseTalk weights missing after download: ' + ', '.join(missing))\n"
        "print('musetalk setup complete')\n"
    )
