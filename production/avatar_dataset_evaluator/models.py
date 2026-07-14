"""Enums, the per-video Record, and the shared column order."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class Quality(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    USABLE = "usable"
    POOR = "poor"
    REJECT = "reject"

    @property
    def rank(self) -> int:
        return {"reject": 0, "poor": 1, "usable": 2, "good": 3, "excellent": 4}[self.value]


class Orientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    SQUARE = "square"


class FaceView(str, Enum):
    FRONTAL = "frontal"
    LEFT_PROFILE = "left_profile"
    RIGHT_PROFILE = "right_profile"
    NONE = "none"


@dataclass
class VideoMeta:
    """Objective technical metadata."""
    filename: str
    duration: float          # seconds
    width: int
    height: int
    fps: float
    aspect_ratio: float
    orientation: str
    file_size_mb: float
    codec: str
    bitrate: int
    frame_count: int
    creation_time: str = ""  # from container metadata if present


@dataclass
class VisualAnalysis:
    """Heuristic visual signals (classical CV over sampled frames)."""
    face_visibility_pct: float      # % of sampled frames with a face
    avg_face_size_pct: float        # face bbox area as % of frame
    frontal_pct: float
    profile_pct: float
    face_view: str                  # dominant FaceView
    head_rotation: str              # "near_frontal" | "moderate" | "extreme"
    lighting_mean: float            # 0-255
    lighting_consistency: float     # 0-1 (1 = steady)
    camera_stability: float         # 0-1 (1 = rock steady)
    motion_blur: float              # mean Laplacian variance (higher = sharper)
    occlusion_pct: float            # % faces with eyes/mouth not found
    eye_visibility_pct: float
    mouth_visibility_pct: float
    speaking_pct: float
    walking_pct: float
    stationary_pct: float
    camera_movement: float          # 0-1 (0 = static camera)
    scene_changes: int
    # low-confidence diversity heuristics
    time_of_day: str = "unknown"    # from metadata timestamp
    setting: str = "unknown"        # indoor|outdoor|unknown (weak heuristic)
    expression: str = "neutral"     # neutral|smiling|talking (weak heuristic)


@dataclass
class Record:
    id: int
    filename: str
    source: str
    # technical
    duration: float
    resolution: str
    width: int
    height: int
    fps: float
    aspect_ratio: float
    orientation: str
    file_size_mb: float
    codec: str
    bitrate: int
    frame_count: int
    creation_time: str
    # visual
    face_visibility_pct: float
    avg_face_size_pct: float
    frontal_pct: float
    profile_pct: float
    face_view: str
    head_rotation: str
    lighting_mean: float
    lighting_consistency: float
    camera_stability: float
    motion_blur: float
    occlusion_pct: float
    eye_visibility_pct: float
    mouth_visibility_pct: float
    speaking_pct: float
    walking_pct: float
    stationary_pct: float
    camera_movement: float
    scene_changes: int
    time_of_day: str
    setting: str
    expression: str
    # result
    quality: str
    accepted: bool
    accept_reason: str
    reject_reason: str
    avatar_score: float          # 0-100 per-clip readiness contribution
    thumbnail_path: str

    def as_dict(self) -> dict:
        return asdict(self)


RECORD_COLUMNS = [
    "id", "filename", "source", "duration", "resolution", "width", "height",
    "fps", "aspect_ratio", "orientation", "file_size_mb", "codec", "bitrate",
    "frame_count", "creation_time",
    "face_visibility_pct", "avg_face_size_pct", "frontal_pct", "profile_pct",
    "face_view", "head_rotation", "lighting_mean", "lighting_consistency",
    "camera_stability", "motion_blur", "occlusion_pct", "eye_visibility_pct",
    "mouth_visibility_pct", "speaking_pct", "walking_pct", "stationary_pct",
    "camera_movement", "scene_changes", "time_of_day", "setting", "expression",
    "quality", "accepted", "accept_reason", "reject_reason", "avatar_score",
    "thumbnail_path",
]
