"""Deterministic thresholds for avatar-dataset evaluation.

Every value that affects a measurement, classification, or reject reason lives
here so runs are reproducible and tunable. Nothing is learned.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}


@dataclass(frozen=True)
class Config:
    # --- sampling -------------------------------------------------------------
    frame_samples: int = 20          # frames analysed per video (evenly spaced)
    detect_min_size_frac: float = 0.06   # Haar minSize as a fraction of frame height
    detect_scale: float = 1.1
    detect_neighbors: int = 5

    # --- reject gates ---------------------------------------------------------
    min_duration_s: float = 2.0                 # "too short"
    no_face_below_pct: float = 15.0             # "no visible face"
    face_too_small_pct: float = 0.8             # avg face area % of frame -> "face too small"
    heavy_blur_below: float = 60.0             # Laplacian variance -> "heavy blur"
    extreme_rotation_profile_pct: float = 75.0  # mostly-profile -> "extreme head rotation"
    occlusion_covered_pct: float = 70.0         # eyes+mouth missing -> "face covered"
    very_dark_below: float = 45.0               # mean luma -> "very dark"
    very_bright_above: float = 215.0            # mean luma -> "very bright"
    low_res_min_side: int = 480                 # "low resolution"
    too_shaky_below: float = 0.40               # stability 0-1 -> "too shaky"

    # --- quality banding (composite 0-100) ------------------------------------
    excellent_min: float = 80.0
    good_min: float = 65.0
    usable_min: float = 45.0
    poor_min: float = 25.0
    accept_min_quality_rank: int = 2            # accept USABLE(2) and up

    # --- motion / speaking heuristics -----------------------------------------
    speaking_mouth_motion: float = 4.0          # mouth-region frame delta -> speaking
    walking_motion_frac: float = 0.06           # global motion fraction -> walking
    scene_change_hist_delta: float = 0.45       # histogram correlation drop -> scene cut

    def base_dir(self) -> Path:
        env = os.environ.get("AVATAR_EVAL_BASE")
        return Path(env) if env else Path(r"D:\AI_CREATOR_DATA\Tanshi")


@dataclass(frozen=True)
class Paths:
    root: Path                       # e.g. D:\AI_CREATOR_DATA\Tanshi
    source: Path                     # raw_videos

    @property
    def out(self) -> Path: return self.root / "avatar_dataset"
    @property
    def accepted(self) -> Path: return self.out / "accepted"
    @property
    def rejected(self) -> Path: return self.out / "rejected"
    @property
    def reports(self) -> Path: return self.out / "reports"
    @property
    def thumbnails(self) -> Path: return self.out / "thumbnails"

    def ensure(self) -> "Paths":
        for p in (self.accepted, self.rejected, self.reports, self.thumbnails):
            p.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def make(cls, root: Path) -> "Paths":
        root = Path(root)
        return cls(root=root, source=root / "raw_videos")
