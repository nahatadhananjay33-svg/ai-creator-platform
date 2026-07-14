"""Phase A1 — viewpoint/category coverage over accepted clips.

ADDITIVE measurement for the incremental evaluation: nothing here feeds the
A0 accept/reject decision or composite score — it only answers "which of the
required avatar viewpoints exist, and for how many usable minutes?".

The twelve categories the phase must measure:

    front, left_20, right_20, looking_up, looking_down, smiling, serious,
    walking, standing, sitting, side_movement, natural_talking

Where A0 already measured a signal (walking, speaking, expression, profile
views) it is reused from the Record. The genuinely new signals are classical
proxies over re-sampled frames, using the same bundled Haar cascades:

- yaw ~20°: horizontal offset of the eye-pair midpoint inside the frontal
  face box (a slight turn shifts the visible eye line off-centre long before
  the profile cascade fires). Left/right are AS SEEN ON CAMERA.
- pitch (up/down): vertical position of the eye line inside the face box
  (eyes sit high in the box with the chin raised, low with the head dropped).
- side movement: phase-correlation shift dominated by the horizontal axis.

All are deterministic, CPU-only, and labelled LOW-CONFIDENCE in reports.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np

from .analyze import _cascade
from .models import Record

CATEGORIES = ["front", "left_20", "right_20", "looking_up", "looking_down",
              "smiling", "serious", "walking", "standing", "sitting",
              "side_movement", "natural_talking"]

CATEGORY_LABELS = {
    "front": "Front", "left_20": "20° Left", "right_20": "20° Right",
    "looking_up": "Looking Up", "looking_down": "Looking Down",
    "smiling": "Smiling", "serious": "Serious", "walking": "Walking",
    "standing": "Standing", "sitting": "Sitting",
    "side_movement": "Side movement", "natural_talking": "Natural talking",
}


@dataclass(frozen=True)
class CoverageConfig:
    frame_samples: int = 12
    detect_min_size_frac: float = 0.06
    yaw_offset_frac: float = 0.06      # |eye-mid offset| / box width => ~20° turn
    pitch_up_below: float = 0.32       # eye line high in box  => looking up
    pitch_down_above: float = 0.50     # eye line low in box   => looking down
    frame_frac: float = 0.20           # fraction of face frames to claim a pose
    front_frac: float = 0.60
    smile_frac: float = 0.20
    horiz_shift_frac: float = 0.0015   # mean |dx|/diag for real side movement
    horiz_dominance: float = 2.0       # |dx| this multiple of |dy|
    sitting_face_pct: float = 8.0      # stationary close-up framing => seated take
    speaking_pct_min: float = 30.0
    min_category_minutes: float = 1.0  # coverage below this counts as missing


@dataclass
class ClipCoverage:
    """Frame-level fractions for one clip (0..1 over frames with a face)."""
    filename: str
    face_frames: int = 0
    frontal_frac: float = 0.0
    left_frac: float = 0.0            # slight-left via yaw proxy
    right_frac: float = 0.0
    up_frac: float = 0.0
    down_frac: float = 0.0
    smile_frac: float = 0.0
    horiz_dominant: bool = False


def analyze_coverage(video: Path, ccfg: CoverageConfig = CoverageConfig()) -> ClipCoverage:
    """Sample frames and measure the coverage proxies for one clip."""
    import cv2

    cov = ClipCoverage(filename=Path(video).name)
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    if n <= 1 or h == 0 or w == 0:
        cap.release()
        return cov
    diag = (w * w + h * h) ** 0.5
    minsize = max(20, int(ccfg.detect_min_size_frac * h))
    front = _cascade("haarcascade_frontalface_default.xml")
    eye = _cascade("haarcascade_eye.xml")
    smile = _cascade("haarcascade_smile.xml")

    frontal = left = right = up = down = smiles = faces = 0
    dxs, dys = [], []
    for i in np.linspace(0, max(0, n - 2), min(ccfg.frame_samples, max(2, n - 1))).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f1 = cap.read()
        if not ok:
            continue
        ok2, f2 = cap.read()
        g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
        if ok2 and f2.shape == f1.shape:
            (dx, dy), _ = cv2.phaseCorrelate(np.float32(g1),
                                             np.float32(cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)))
            dxs.append(abs(dx)); dys.append(abs(dy))

        ff = front.detectMultiScale(g1, 1.1, 5, minSize=(minsize, minsize))
        if not len(ff):
            continue
        faces += 1
        frontal += 1
        x, y, fw, fh = max(ff, key=lambda b: b[2] * b[3])
        roi = g1[y:y + fh, x:x + fw]
        if not roi.size:
            continue
        eyes = eye.detectMultiScale(roi, 1.1, 4)
        if len(eyes):
            pick = sorted(eyes, key=lambda b: -(b[2] * b[3]))[:2]
            mid_x = float(np.mean([ex + ew / 2.0 for ex, ey_, ew, eh in pick])) / fw
            eye_y = float(np.mean([ey_ + eh / 2.0 for ex, ey_, ew, eh in pick])) / fh
            offset = mid_x - 0.5
            if len(pick) == 2 and offset <= -ccfg.yaw_offset_frac:
                left += 1
            elif len(pick) == 2 and offset >= ccfg.yaw_offset_frac:
                right += 1
            if eye_y <= ccfg.pitch_up_below:
                up += 1
            elif eye_y >= ccfg.pitch_down_above:
                down += 1
        lower = roi[fh // 2:, :]
        if lower.size and len(smile.detectMultiScale(lower, 1.7, 15)):
            smiles += 1
    cap.release()

    fc = max(1, faces)
    cov.face_frames = faces
    cov.frontal_frac = frontal / fc
    cov.left_frac = left / fc
    cov.right_frac = right / fc
    cov.up_frac = up / fc
    cov.down_frac = down / fc
    cov.smile_frac = smiles / fc
    if dxs:
        mean_dx, mean_dy = float(np.mean(dxs)), float(np.mean(dys))
        cov.horiz_dominant = (mean_dx / diag >= ccfg.horiz_shift_frac
                              and mean_dx >= ccfg.horiz_dominance * max(mean_dy, 1e-6))
    return cov


def clip_categories(rec: Record, cov: Optional[ClipCoverage],
                    ccfg: CoverageConfig = CoverageConfig()) -> List[str]:
    """Which of the twelve categories this clip contributes to."""
    cats: List[str] = []
    c = cov or ClipCoverage(filename=rec.filename)
    stationary = rec.walking_pct <= 50.0

    if c.face_frames and c.frontal_frac >= ccfg.front_frac:
        cats.append("front")
    if rec.face_view == "left_profile" or c.left_frac >= ccfg.frame_frac:
        cats.append("left_20")
    if rec.face_view == "right_profile" or c.right_frac >= ccfg.frame_frac:
        cats.append("right_20")
    if c.up_frac >= ccfg.frame_frac:
        cats.append("looking_up")
    if c.down_frac >= ccfg.frame_frac:
        cats.append("looking_down")
    if rec.expression == "smiling" or c.smile_frac >= ccfg.smile_frac:
        cats.append("smiling")
    if rec.expression == "neutral":
        cats.append("serious")
    if rec.walking_pct > 50.0:
        cats.append("walking")
    if stationary and rec.avg_face_size_pct < ccfg.sitting_face_pct:
        cats.append("standing")
    if stationary and rec.avg_face_size_pct >= ccfg.sitting_face_pct:
        cats.append("sitting")
    if c.horiz_dominant or (rec.camera_movement >= 0.30 and stationary):
        cats.append("side_movement")
    if rec.speaking_pct >= ccfg.speaking_pct_min and stationary:
        cats.append("natural_talking")
    return cats


def coverage_minutes(records: Iterable[Record],
                     covs: Dict[str, ClipCoverage],
                     ccfg: CoverageConfig = CoverageConfig()) -> Dict[str, dict]:
    """Per category: contributing clips and usable minutes (accepted clips)."""
    out = {cat: {"clips": 0, "minutes": 0.0} for cat in CATEGORIES}
    for rec in records:
        if not rec.accepted:
            continue
        for cat in clip_categories(rec, covs.get(rec.filename), ccfg):
            out[cat]["clips"] += 1
            out[cat]["minutes"] += rec.duration / 60.0
    for v in out.values():
        v["minutes"] = round(v["minutes"], 1)
    return out


def format_coverage(cov_min: Dict[str, dict], ccfg: CoverageConfig = CoverageConfig()) -> str:
    lines = [f"  {'category':<18} {'clips':>6} {'minutes':>8}   status",
             "  " + "-" * 52]
    for cat in CATEGORIES:
        v = cov_min[cat]
        status = ("OK" if v["minutes"] >= ccfg.min_category_minutes
                  else "PARTIAL" if v["minutes"] > 0 else "MISSING")
        lines.append(f"  {CATEGORY_LABELS[cat]:<18} {v['clips']:>6} {v['minutes']:>8.1f}   {status}")
    lines.append("  (pose/pitch/side-movement are low-confidence classical proxies)")
    return "\n".join(lines)
