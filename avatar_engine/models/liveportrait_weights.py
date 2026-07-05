"""LivePortrait pretrained-weight manifest, verification, and download (A3.9).

Single source of truth for *exactly* which weights LivePortrait needs, taken
from upstream (not guessed):

- HF repo: ``KlingTeam/LivePortrait`` (the weights moved here from KwaiVGI).
- Human directory tree from ``assets/docs/directory-structure.md`` and the HF
  file listing. Sizes are the HF-reported values (approximate — used as a
  truncation/corruption guard, not an exact hash). ``liveportrait_animals/`` is
  intentionally excluded: humans mode only.

The manifest drives the installer's download step, the adapter's availability
check, and the diagnostics report — so nothing is hardcoded in three places.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

HF_REPO_ID = "KlingTeam/LivePortrait"
#: Present-but-wrong-size band. HF sizes are display-rounded, so this is a guard
#: against truncated / error-page downloads, not an exact byte check.
_SIZE_MIN_FRACTION = 0.70
_SIZE_MAX_FRACTION = 1.40
_MB = 1_048_576


@dataclass(frozen=True)
class WeightFile:
    """One required pretrained file, relative to ``pretrained_weights/``."""

    relpath: str          # e.g. "liveportrait/base_models/motion_extractor.pth"
    purpose: str
    size_mb: float        # HF-reported size
    sha256: str | None = None  # exact hash when known (verified if present)

    @property
    def expected_bytes(self) -> int:
        return int(self.size_mb * _MB)


#: The complete humans-mode weight set (8 files, ~660 MB).
LIVEPORTRAIT_WEIGHTS: tuple[WeightFile, ...] = (
    WeightFile("liveportrait/base_models/appearance_feature_extractor.pth",
               "appearance feature extractor", 3.39),
    WeightFile("liveportrait/base_models/motion_extractor.pth",
               "motion / keypoint extractor", 113.0),
    WeightFile("liveportrait/base_models/spade_generator.pth",
               "SPADE image generator (decoder)", 222.0),
    WeightFile("liveportrait/base_models/warping_module.pth",
               "warping module", 182.0),
    WeightFile("liveportrait/landmark.onnx",
               "landmark detection (onnx)", 115.0),
    WeightFile("liveportrait/retargeting_models/stitching_retargeting_module.pth",
               "stitching / retargeting module", 2.39),
    WeightFile("insightface/models/buffalo_l/2d106det.onnx",
               "insightface 2D-106 landmarks", 5.03),
    WeightFile("insightface/models/buffalo_l/det_10g.onnx",
               "insightface face detection", 16.9),
)


def pretrained_root(repo_dir: Path) -> Path:
    return Path(repo_dir) / "pretrained_weights"


def required_weight_paths(repo_dir: Path) -> list[Path]:
    root = pretrained_root(repo_dir)
    return [root / w.relpath for w in LIVEPORTRAIT_WEIGHTS]


@dataclass
class WeightStatus:
    relpath: str
    purpose: str
    expected_bytes: int
    actual_bytes: int | None
    status: str   # "validated" | "missing" | "corrupted" | "checksum_mismatch"
    reason: str

    @property
    def ok(self) -> bool:
        return self.status == "validated"

    def to_dict(self) -> dict:
        return {
            "relpath": self.relpath, "purpose": self.purpose,
            "expected_bytes": self.expected_bytes, "actual_bytes": self.actual_bytes,
            "status": self.status, "reason": self.reason, "ok": self.ok,
        }


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_weight(repo_dir: Path, w: WeightFile) -> WeightStatus:
    """Classify one weight: validated / missing / corrupted / checksum_mismatch."""
    path = pretrained_root(repo_dir) / w.relpath
    if not path.exists():
        return WeightStatus(w.relpath, w.purpose, w.expected_bytes, None,
                            "missing", "file not downloaded")
    actual = path.stat().st_size
    lo = int(w.expected_bytes * _SIZE_MIN_FRACTION)
    hi = int(w.expected_bytes * _SIZE_MAX_FRACTION)
    if actual < lo or actual > hi:
        return WeightStatus(w.relpath, w.purpose, w.expected_bytes, actual, "corrupted",
                            f"size {actual/_MB:.1f} MB outside expected "
                            f"~{w.size_mb:.1f} MB (truncated/incomplete download)")
    if w.sha256 is not None and _sha256(path) != w.sha256:
        return WeightStatus(w.relpath, w.purpose, w.expected_bytes, actual,
                            "checksum_mismatch", "sha256 does not match manifest")
    return WeightStatus(w.relpath, w.purpose, w.expected_bytes, actual, "validated",
                        "present and size/hash valid")


def check_weights(repo_dir: Path) -> list[WeightStatus]:
    return [check_weight(repo_dir, w) for w in LIVEPORTRAIT_WEIGHTS]


def all_valid(statuses: list[WeightStatus]) -> bool:
    return bool(statuses) and all(s.ok for s in statuses)


def weights_to_download(repo_dir: Path) -> list[WeightFile]:
    """Only the files that are missing/corrupted — valid files are never
    redownloaded."""
    by_path = {w.relpath: w for w in LIVEPORTRAIT_WEIGHTS}
    return [by_path[s.relpath] for s in check_weights(repo_dir) if not s.ok]


def build_prefetch_code(repo_dir: Path) -> str:
    """Self-contained snippet (run inside the LivePortrait venv) that downloads
    only the humans-mode weights via ``hf_hub_download`` — resumable, cached, and
    skips files already present. Placed as the install spec's ``prefetch_code``.
    """
    root = pretrained_root(repo_dir).as_posix()
    files = [w.relpath for w in LIVEPORTRAIT_WEIGHTS]
    return (
        "from huggingface_hub import hf_hub_download\n"
        "import pathlib\n"
        f"root = pathlib.Path(r'{root}'); root.mkdir(parents=True, exist_ok=True)\n"
        f"files = {files!r}\n"
        f"repo = '{HF_REPO_ID}'\n"
        "for rel in files:\n"
        "    # hf_hub_download resumes partial downloads, verifies the etag, and\n"
        "    # returns instantly if the file is already cached/valid.\n"
        "    hf_hub_download(repo_id=repo, filename=rel, local_dir=str(root))\n"
        "    print('weight ready:', rel)\n"
        "print('liveportrait weights ready')\n"
    )
