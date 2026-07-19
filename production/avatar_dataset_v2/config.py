"""Configuration for the avatar dataset v2 optimizer (smart-crop rebuild)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SRC_ROOT = Path(r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset")
SRC_ACCEPTED = SRC_ROOT / "accepted"
OUT_ROOT = Path(r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset_v2")

# three export variants; the quality report picks the winner
RESOLUTIONS = (768, 1024, 1280)
RENDER_RES = max(RESOLUTIONS)          # render once at the largest, downscale the rest
DEFAULT_RES = 1024

VARIANT_ROOT = {r: OUT_ROOT.parent / f"avatar_dataset_v2_{r}" for r in RESOLUTIONS}


@dataclass(frozen=True)
class CropCfg:
    """Margins are multiples of the detected face-box size."""
    top_hair: float = 1.35          # above face center: hair + forehead headroom
    bottom_shoulders: float = 2.20  # below face center: chin, neck, shoulders
    side_width: float = 3.20        # crop width in face-widths (ears + shoulders)
    height_total: float = 3.55      # minimum crop side in face-heights
    smooth_window_s: float = 1.0    # moving-average window (seconds)
    max_gap_frames: int = 15        # interpolate face track across gaps up to this
    detect_stride: int = 2          # run the detector every Nth frame
    detect_max_dim: int = 960       # detector input downscale


@dataclass(frozen=True)
class AcceptCfg:
    """Per-variant accept/reject thresholds (face sizes in OUTPUT pixels)."""
    min_avg_face: float = 200.0
    min_min_face: float = 140.0
    max_center_jitter: float = 0.020   # per-frame center motion std / crop side
    min_blur_var: float = 25.0         # Laplacian variance @ render res
    min_completeness: float = 0.98     # frames whose required region fit the crop
    max_face_lost_frac: float = 0.05


@dataclass(frozen=True)
class RunCfg:
    workers: int = max(2, min(6, (os.cpu_count() or 4) - 2))
    crf: int = 18
    preset: str = "veryfast"
    audio_bitrate: str = "192k"
    comparison_samples: int = 100
    crop: CropCfg = field(default_factory=CropCfg)
    accept: AcceptCfg = field(default_factory=AcceptCfg)


RUN = RunCfg()

STATE_DIR = OUT_ROOT / "reports" / "state"      # per-clip resume markers
RENDER_DIR = OUT_ROOT / "render_1280"           # master renders before placement

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}


def source_clips() -> list[Path]:
    return sorted(p for p in SRC_ACCEPTED.iterdir()
                  if p.suffix.lower() in VIDEO_EXTS and p.is_file())


def safe_stem(name: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_-]+", "_", Path(name).stem).strip("_")
